"""2026-09-16 审计批次二的回归测试（四项卡面/审计一致性修复）。

1. 孤儿集成「来源?」占位符 —— 生产者写 `_meta["source"]`，消费端读 `_meta["_source"]`。
2. 清算流静默零值 —— OKX 腿停更高 1 小时时，近 1h 仍照印 $0/$0，读成「市场无强平」。
3. cron_read 审计只看仓库 data/ —— coinlobster 工件在 Hermes 运行态 data/，
   于是「③ 表有数、完成度表说 not_run」同一张卡自相矛盾。
4. 外部验证层没进新鲜度看门狗 —— 采集器死了没人报。
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import data_freshness_watchdog as wd
import liquidation_flow


# ── 1. 来源标签 ──────────────────────────────────────────────────────────────
def test_orphan_source_label_reads_producer_key():
    assert auto_card._orphan_source_label(
        {"_meta": {"source": "棠溪·孤儿脚本集成适配层"}}) == "棠溪·孤儿脚本集成适配层"
    # 兼容已经写成 _source 的旧结构
    assert auto_card._orphan_source_label({"_meta": {"_source": "x"}}) == "x"
    # 兜底标签不得是 "?" 占位符
    for bad in ({}, {"_meta": None}, {"_meta": "oops"}, None):
        label = auto_card._orphan_source_label(bad)
        assert label and "?" not in label


# ── 2. 清算流停更可见 ────────────────────────────────────────────────────────
def _okx_cache(events, fetched_at):
    return {"source": "okx_public", "fetched_at": fetched_at, "status": "live",
            "coins": {"BTC": {"ct_val": 0.01, "stale": False, "events": events}}}


def test_liquidation_flow_marks_stalled_feed(monkeypatch):
    import time
    now = time.time()
    stale_events = [[int((now - 3 * 3600) * 1000), "long", 75000, 100]]
    monkeypatch.setattr(liquidation_flow, "load_cache", lambda *a, **k: _okx_cache(stale_events, now))
    monkeypatch.setattr(liquidation_flow, "load_ws_usd_events",
                        lambda *a, **k: {"status": "live", "events": [], "age_s": 1.0, "error": None})
    text = liquidation_flow.multi_source_text("BTC", now=now)
    assert "疑似停更" in text, text


def test_liquidation_flow_keeps_quiet_market_clean(monkeypatch):
    import time
    now = time.time()
    fresh_events = [[int((now - 60) * 1000), "long", 75000, 10],
                    [int((now - 600) * 1000), "short", 75100, 5]]
    monkeypatch.setattr(liquidation_flow, "load_cache", lambda *a, **k: _okx_cache(fresh_events, now))
    monkeypatch.setattr(liquidation_flow, "load_ws_usd_events",
                        lambda *a, **k: {"status": "live", "events": [], "age_s": 1.0, "error": None})
    text = liquidation_flow.multi_source_text("BTC", now=now)
    assert "疑似停更" not in text, text


# ── 3. cron_read 双数据根 ────────────────────────────────────────────────────
def test_cron_read_audit_probes_both_data_roots():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'ROOT / "data" / source_file' in source
    assert 'AppData/Local/hermes" / "data" / source_file' in source
    assert "next((p for p in _candidates if p.exists()), _candidates[0])" in source


def test_coinlobster_artifact_is_registered_in_freshness_watchdog():
    entry = wd.WATCH_FILES.get("coinlobster_snapshot.json")
    assert entry, "外部验证层工件必须进新鲜度看门狗"
    assert 0 < entry["threshold"] <= 0.7
    paths = [str(p) for p in entry["paths"]]
    assert any(p.endswith("hermes\\data\\coinlobster_snapshot.json")
               or p.endswith("hermes/data/coinlobster_snapshot.json") for p in paths)


# ── 5. 静默轮次可诊断 ────────────────────────────────────────────────────────
def test_sync_entrypoint_leaves_exit_marker(monkeypatch):
    """正常退出必留 exit 行；只有异常终止才会「有 enter、无 exit」。"""
    import xau_tv_sync

    marks: list = []
    monkeypatch.setattr(xau_tv_sync, "_audit_marker",
                        lambda reason, **kw: marks.append((reason, kw)))
    monkeypatch.setattr(xau_tv_sync, "_sync_main", lambda: 0)
    assert xau_tv_sync.main() == 0
    assert marks[-1][0] == "exit" and marks[-1][1].get("rc") == 0

    marks.clear()
    monkeypatch.setattr(xau_tv_sync, "_sync_main", lambda: 1)
    assert xau_tv_sync.main() == 1
    assert marks[-1][0] == "exit" and marks[-1][1].get("rc") == 1


def test_sync_entrypoint_marks_unexpected_termination(monkeypatch):
    """BaseException（asyncio 取消 / SystemExit）也必须留痕后再抛。"""
    import pytest
    import xau_tv_sync

    marks: list = []
    monkeypatch.setattr(xau_tv_sync, "_audit_marker",
                        lambda reason, **kw: marks.append((reason, kw)))

    def _boom():
        raise KeyboardInterrupt("stub")

    monkeypatch.setattr(xau_tv_sync, "_sync_main", _boom)
    with pytest.raises(KeyboardInterrupt):
        xau_tv_sync.main()
    assert marks[-1][0] == "exit:exception"
