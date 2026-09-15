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


# ── 多源聚合（OKX 逐笔 + 币安 WS 快照）2026-09-15 ──────────────────────────


def test_okx_usd_events_apply_contract_value():
    """OKX 第 4 列是张数：必须 ×ctVal×价格 才折成 USD。"""
    out = lf.okx_usd_events([[NOW_MS, "long", 70_000.0, 100.0]], ct_val=0.01)
    assert out == [[NOW_MS, "long", 70_000.0, 70_000.0]]


def test_stats_usd_takes_notional_as_given():
    """USD 事件表不再乘面值，避免二重换算。"""
    st = lf.stats_usd([[NOW_MS, "long", 70_000.0, 1_000_000.0]], now_ms=NOW_MS)
    assert st["w1h"]["long_usd"] == 1_000_000.0
    assert st["coverage_hours"] == 0.0


def _write_okx_cache(path, events, *, fetched_at, ct_val=0.01):
    path.write_text(json.dumps({
        "source": "okx_public", "fetched_at": fetched_at, "updated_epoch": int(fetched_at),
        "status": "live", "error": None,
        "coins": {"BTC": {"ct_val": ct_val, "events": events, "stale": False}},
    }, ensure_ascii=False), encoding="utf-8")


def _write_ws_cache(path, events, *, updated_epoch, status="live"):
    path.write_text(json.dumps({
        "source": "binance_ws", "updated_epoch": updated_epoch, "status": status,
        "error": None,
        "coins": {"BTC": {"events": events, "coverage_from": 0, "coverage_to": 0}},
    }, ensure_ascii=False), encoding="utf-8")


def test_multi_source_text_keeps_binance_out_of_scale(tmp_path):
    """币安快照只作存在性附注，绝不并进规模合计 —— 否则系统性低估。

    币安流自 2021-04-27 起只推 ≤1 条/秒快照（官方变更日志）。这里给币安一笔
    $5,000,000 的快照，规模读数必须仍等于 OKX 的 $70,000。
    """
    okx = tmp_path / "okx.json"
    ws = tmp_path / "ws.json"
    now_s = NOW_MS / 1000
    _write_okx_cache(okx, [[NOW_MS - 60_000, "long", 70_000.0, 100.0]], fetched_at=now_s - 5)
    _write_ws_cache(ws, [[NOW_MS - 30_000, "short", 70_000.0, 71.4286]], updated_epoch=int(now_s - 5))

    text = lf.multi_source_text("BTC", okx_cache_path=str(okx), ws_cache_path=str(ws), now=now_s)
    assert "清算流OKX" in text
    assert "$70K" in text              # 规模 = OKX 的 100 张 × 0.01 × 70,000
    assert "$5.0M" not in text         # 币安那笔不得进规模
    assert "币安快照" in text          # 但存在性可见


def test_multi_source_text_reports_snapshot_when_okx_missing(tmp_path):
    """OKX 无数据时只给币安快照并**显式说明规模口径不可用**，不拿快照冒充规模。"""
    ws = tmp_path / "ws.json"
    now_s = NOW_MS / 1000
    _write_ws_cache(ws, [[NOW_MS - 30_000, "short", 70_000.0, 3.0]], updated_epoch=int(now_s - 5))
    text = lf.multi_source_text("BTC", okx_cache_path=str(tmp_path / "none.json"),
                               ws_cache_path=str(ws), now=now_s)
    assert "规模口径不可用" in text
    assert "币安快照" in text


def test_multi_source_text_unavailable_when_all_sources_missing(tmp_path):
    assert lf.multi_source_text("BTC", okx_cache_path=str(tmp_path / "a.json"),
                               ws_cache_path=str(tmp_path / "b.json")) == "清算流 不可用"


def test_ws_events_are_usd_converted_from_coins(tmp_path):
    """币安 WS 第 4 列是币数：×价格 即 USD；陈旧缓存不得算 live。"""
    ws = tmp_path / "ws.json"
    now_s = NOW_MS / 1000
    _write_ws_cache(ws, [[NOW_MS - 1000, "long", 70_000.0, 2.0]], updated_epoch=int(now_s - 5))
    live = lf.load_ws_usd_events("BTC", cache_path=str(ws), now=now_s)
    assert live["status"] == "live"
    assert live["events"][0][3] == 140_000.0

    _write_ws_cache(ws, [[NOW_MS - 1000, "long", 70_000.0, 2.0]],
                    updated_epoch=int(now_s - lf.WS_MAX_AGE_S - 60))
    stale = lf.load_ws_usd_events("BTC", cache_path=str(ws), now=now_s)
    assert stale["status"] == "stale_cache"
