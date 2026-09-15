"""OKX 逐笔强平读取器回归（scripts/liquidation_flow.py）。

只锁**离线可复现**的部分：方向归一化、增量合并去重、窗口统计、覆盖标注、三态文本。
真网络请求不进单测（依赖交易所接口与代理，会红）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import liquidation_flow as lf  # noqa: E402

NOW_MS = 1_789_470_570_125


def _row(pos_side="long", side="sell", px="77000", sz="10", ts=NOW_MS):
    return {"posSide": pos_side, "side": side, "bkPx": px, "sz": sz, "ts": str(ts)}


def test_normalize_keeps_liquidated_side_not_order_side():
    """卡面要的是「谁被强平」：posSide=long, side=sell → 记录 long。"""
    out = lf.normalize([_row()], ct_val=0.01)
    assert out == [[NOW_MS, "long", 77000.0, 10.0]]


def test_normalize_skips_rows_without_side_or_positive_values():
    bad = [{"posSide": "", "bkPx": "1", "sz": "1", "ts": str(NOW_MS)},
           _row(px="0"),
           _row(sz="0"),
           {"posSide": "long", "bkPx": "1", "sz": "1"}]  # 缺 ts
    assert lf.normalize(bad, ct_val=0.01) == []


def test_merge_dedupes_sorts_and_trims_window():
    dup = [NOW_MS - 1000, "long", 1.0, 1.0]
    out_of_window = [NOW_MS - (lf.WINDOW_S + 60) * 1000, "long", 3.0, 3.0]
    newer = [NOW_MS - 2000, "short", 2.0, 2.0]
    merged = lf.merge_events([dup, dup], [newer, out_of_window], NOW_MS)
    assert merged == [newer, dup]


def test_stats_computes_notional_from_contract_value():
    events = [[NOW_MS - 60_000, "long", 70_000.0, 100.0],
              [NOW_MS - 3600_000, "short", 80_000.0, 50.0]]
    st = lf.stats(events, ct_val=0.01, now_ms=NOW_MS)
    assert st["w1h"]["long_usd"] == 70_000.0          # 100 张 × 0.01 BTC × 70,000
    assert st["w1h"]["short_usd"] == 40_000.0
    assert st["w1h"]["net_usd"] == 30_000.0
    assert st["w24h"]["count"] == 2
    assert st["events"] == 2
    assert "估算" in st["notional_note"]


def test_stats_biggest_and_last_are_independent():
    events = [[NOW_MS - 10_000, "long", 70_000.0, 100.0],
              [NOW_MS - 5_000, "short", 70_000.0, 1.0]]
    st = lf.stats(events, ct_val=0.01, now_ms=NOW_MS)
    assert st["biggest"]["side"] == "long"
    assert st["last"]["side"] == "short"


def test_span_label_never_calls_partial_coverage_a_full_window():
    """4 小时的数据不许标成「近24h」——覆盖不足必须写在标签里。"""
    assert lf._span_label(4.3, 24) == "窗4.3h"
    assert lf._span_label(23.9, 24) == "近24h"
    assert lf._span_label(0.5, 1) == "窗30m"
    assert lf._span_label(1.0, 1) == "近1h"


def _write_cache(path: Path, events, *, fetched_at, ct_val=0.01, stale=False):
    path.write_text(json.dumps({
        "source": "okx_public", "fetched_at": fetched_at, "status": "live",
        "error": None,
        "coins": {"BTC": {"ct_val": ct_val, "events": events, "stale": stale}},
    }, ensure_ascii=False), encoding="utf-8")


def test_flow_text_is_unavailable_without_cache(tmp_path):
    assert lf.flow_text("BTC", cache_path=str(tmp_path / "missing.json")) == "清算流 不可用"


def test_flow_text_marks_stale_cache(tmp_path):
    p = tmp_path / "c.json"
    _write_cache(p, [[NOW_MS - 1000, "long", 70_000.0, 10.0]], fetched_at=1000)
    assert lf.flow_text("BTC", cache_path=str(p), now=NOW_MS / 1000).startswith("清算流 陈旧")


def test_flow_text_reports_coverage_and_estimate(tmp_path):
    p = tmp_path / "c.json"
    events = [[NOW_MS - i * 60_000, "long", 70_000.0, 10.0] for i in range(1, 241)]  # 覆盖 4h
    now_s = NOW_MS / 1000
    _write_cache(p, events, fetched_at=now_s - 10)
    text = lf.flow_text("BTC", cache_path=str(p), now=now_s)
    assert "窗4.0h" in text          # 24h 段必须标真实覆盖
    assert "近24h" not in text
    assert "估算" in text


def test_flow_text_empty_events_is_unavailable(tmp_path):
    p = tmp_path / "c.json"
    _write_cache(p, [], fetched_at=NOW_MS / 1000)
    assert lf.flow_text("BTC", cache_path=str(p), now=NOW_MS / 1000) == "清算流 不可用"


def test_refresh_cache_keeps_previous_events_on_source_failure(tmp_path, monkeypatch):
    p = tmp_path / "c.json"
    now_s = int(NOW_MS / 1000)
    _write_cache(p, [[NOW_MS - 60_000, "long", 70_000.0, 10.0]], fetched_at=now_s)

    def boom(*_a, **_k):
        raise RuntimeError("network down")

    monkeypatch.setattr(lf, "fetch_recent", boom)
    rec = lf.refresh_cache(("BTC",), cache_path=str(p))
    assert rec["status"] == "stale_cache"
    assert rec["coins"]["BTC"]["stale"] is True
    assert len(rec["coins"]["BTC"]["events"]) == 1


def test_flow_text_flags_reused_previous_round(tmp_path):
    p = tmp_path / "c.json"
    now_s = NOW_MS / 1000
    _write_cache(p, [[NOW_MS - 60_000, "long", 70_000.0, 10.0]], fetched_at=now_s, stale=True)
    assert "沿用上轮" in lf.flow_text("BTC", cache_path=str(p), now=now_s)


def test_module_reads_no_secrets_and_no_heavy_deps():
    """模块必须自包含：不读凭据、不依赖 pandas/requests（只准用标准库）。"""
    src = (ROOT / "scripts" / "liquidation_flow.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]
    for banned in ("secrets", "credential_store", "import pandas", "import requests"):
        assert banned not in body


def test_okx_page_limit_is_capped_at_exchange_maximum():
    """OKX limit>100 回 HTTP 400 —— 翻页上限必须被代码夹住。"""
    assert lf.PAGE_LIMIT == 100
