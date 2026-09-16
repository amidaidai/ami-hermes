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
                        lambda *a, **k: {"status": "live", "events": [[int((now - 300) * 1000), "long", 75000, 3]],
                                         "age_s": 1.0, "error": None})
    text = liquidation_flow.multi_source_text("BTC", now=now)
    assert "疑似停更" in text, text
    # 停更期间币安快照只是「存在性」证据，不能被读成规模（首两列才是规模口径）
    assert "仅存在性" in text, text


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


# ── 6. 静默轮次可被判据化识别 ────────────────────────────────────────────────
def _write_marks(tmp_path, records):
    import json

    path = tmp_path / "xau_tv_sync_runs.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                    encoding="utf-8")
    return path


def test_unterminated_round_is_detected(monkeypatch, tmp_path):
    """有 enter、无终态 = 异常终止（实测 13:15:50 轮即此形态）。"""
    import xau_tv_sync

    monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE",
                        _write_marks(tmp_path, [
                            {"ts": "t1", "pid": 1, "reason": "enter"},
                            {"ts": "t2", "pid": 1, "reason": "published"},
                            {"ts": "t3", "pid": 21864, "reason": "enter"},
                        ]))
    orphan = xau_tv_sync.last_round_unterminated()
    assert orphan and orphan["pid"] == 21864


def test_terminated_rounds_are_clean(monkeypatch, tmp_path):
    import xau_tv_sync

    for terminal in ({"reason": "exit", "rc": 0}, {"reason": "defer:cache_usable"},
                     {"reason": "error"}, {"reason": "published"}):
        marks = [{"ts": "t1", "pid": 1, "reason": "enter"}, dict({"ts": "t2", "pid": 1}, **terminal)]
        monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE", _write_marks(tmp_path, marks))
        assert xau_tv_sync.last_round_unterminated() is None, terminal


def test_analysis_owner_proceed_is_not_a_terminal_marker(monkeypatch, tmp_path):
    """`proceed:analysis_owner` 只是「放行」不是终态 —— 该轮仍需 exit 才算终结。"""
    import xau_tv_sync

    monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE",
                        _write_marks(tmp_path, [
                            {"ts": "t1", "pid": 7, "reason": "enter"},
                            {"ts": "t2", "pid": 7, "reason": "proceed:analysis_owner"},
                        ]))
    assert xau_tv_sync.last_round_unterminated() is not None


# ── 7. XAU ① 体温条不再印前缀样板字 ──────────────────────────────────────────
def test_position_label_is_objective():
    from tv_five_tf_contract import position_label

    assert position_label(100, 0, 95, -0.10) == "高位95%·跌0.10%"
    assert position_label(100, 0, 5, 0.5) == "低位5%·涨0.50%"
    assert position_label(100, 0, 50, 0) == "中位50%·平0.00%"
    assert position_label(100, 0, 50) == "中位50%"          # 无涨跌幅时只给位置
    # 坏数据不编数字 → 空串（调用方各自兜底）
    assert position_label(None, 0, 50) == ""
    assert position_label(0, 0, 0) == ""


def test_gold_five_tf_view_uses_position_label_not_boilerplate():
    """无 SVP 逐层结构的品种：五周期视图必须给位置+涨跌，不许只印「TV现场·D」。"""
    import tv_five_tf_contract as c

    view = c._normalise_record("5m", {"high": 4330.0, "low": 4320.0, "close": 4321.0,
                                      "change_pct": -0.10}, "api:twelvedata", None)
    assert view["description"] == "低位10%·跌0.10%", view["description"]
    # 有结构读数的品种照旧用结构文案（不得被位置标签顶掉）
    view2 = c._normalise_record("15m", {"high": 4330.0, "low": 4320.0, "close": 4325.0,
                                        "grid": {"结构": "多趋势·BOS↑"}}, "tv", None)
    assert view2["description"] == "多趋势·BOS↑", view2["description"]


def test_auto_card_delegates_position_label_to_contract():
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert "from tv_five_tf_contract import position_label" in src
    assert "def _gold_tf_position_label" not in src
    # 旧样板文案（① 印出「🔵TV现场·D」的元凶）不得复活
    assert 'f"TV现场·XAU {tf} {_dir}·{_cp:+.1f}%"' not in src
