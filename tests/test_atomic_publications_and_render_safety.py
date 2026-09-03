from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import btc_ref_levels_sync as btc_sync
import tv_data_bridge as bridge
from render_v96 import render_v96_card


def test_btc_reference_output_uses_atomic_writer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(btc_sync, "OUT", tmp_path / "btc_ref_levels.json")
    monkeypatch.setattr(btc_sync, "atomic_write_json", lambda path, payload: calls.append((path, payload)))
    # Structural contract: the production publication path must use the shared writer.
    source = (ROOT / "scripts" / "btc_ref_levels_sync.py").read_text(encoding="utf-8")
    assert "atomic_write_json(OUT, payload)" in source


def test_tv_bridge_cache_uses_atomic_writer():
    source = (ROOT / "scripts" / "tv_data_bridge.py").read_text(encoding="utf-8")
    assert "atomic_write_json(CACHE, data)" in source


def test_pending_append_is_valid_jsonl_and_serialized(tmp_path, monkeypatch):
    import telegram_reliable as tr

    pending = tmp_path / "pending_telegram.jsonl"
    monkeypatch.setattr(tr, "PENDING_FILE", pending)
    path = tr.append_pending("telegram:-100:1", "hello", "network")

    assert path == pending
    rows = [json.loads(line) for line in pending.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["target"] == "telegram:-100:1"
    assert rows[0]["text"] == "hello"


def test_pending_flush_rewrites_atomically_without_dropping_rows(tmp_path, monkeypatch):
    import telegram_reliable as tr

    pending = tmp_path / "pending_telegram.jsonl"
    monkeypatch.setattr(tr, "PENDING_FILE", pending)
    tr.append_pending("telegram:-100:1", "send", "network")
    tr.append_pending("telegram:-100:1", "keep", "network")
    monkeypatch.setattr(tr, "send_telegram_reliable", lambda *args, **kwargs: (True, "sent"))

    sent, kept = tr.flush_pending(limit=1)

    assert (sent, kept) == (1, 1)
    rows = [json.loads(line) for line in pending.read_text(encoding="utf-8").splitlines()]
    assert [row["text"] for row in rows] == ["keep"]
    assert not list(tmp_path.glob("*.tmp"))


def test_pending_flush_deadletters_permanent_failures(tmp_path, monkeypatch):
    import telegram_reliable as tr

    pending = tmp_path / "pending_telegram.jsonl"
    dead = tmp_path / "deadletter_telegram.jsonl"
    monkeypatch.setattr(tr, "PENDING_FILE", pending)
    monkeypatch.setattr(tr, "DEADLETTER_FILE", dead)
    tr.append_pending("telegram:-100:1", "bad", "http 400: unsupported parse_mode")
    monkeypatch.setattr(
        tr, "send_telegram_reliable",
        lambda *args, **kwargs: (False, "http 400: unsupported parse_mode"),
    )

    sent, kept = tr.flush_pending()

    assert (sent, kept) == (0, 0)
    assert not pending.exists()
    rows = [json.loads(line) for line in dead.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["dead_letter"] is True
    assert rows[0]["last_reason"].startswith("http 400")


def test_photo_delivery_requires_explicit_automation_gate(tmp_path, monkeypatch):
    import telegram_reliable as tr

    photo = tmp_path / "chart.png"
    photo.write_bytes(b"png")
    monkeypatch.delenv("TANGXI_ENABLE_AUTOMATED_TG", raising=False)

    ok, reason = tr.send_telegram_photo("telegram:-100:1", str(photo))

    assert ok is False
    assert reason == "automated_delivery_disabled"


def test_telegram_reliable_requires_explicit_automation_target(monkeypatch):
    import telegram_reliable as tr

    monkeypatch.delenv("TANGXI_ENABLE_AUTOMATED_TG", raising=False)
    monkeypatch.delenv("TANGXI_AUTOMATED_TG_TARGET", raising=False)
    ok, reason = tr.send_telegram_reliable("telegram:-100:1", "blocked", token="test")
    assert ok is False
    assert reason == "automated_delivery_disabled"

    monkeypatch.setenv("TANGXI_ENABLE_AUTOMATED_TG", "1")
    monkeypatch.setenv("TANGXI_AUTOMATED_TG_TARGET", "telegram:-100:2")
    ok, reason = tr.send_telegram_reliable("telegram:-100:1", "blocked", token="test")
    assert ok is False
    assert reason == "automated_delivery_target_mismatch"


def test_trade_bridge_blocks_legacy_entry_ready_without_final_verdict(monkeypatch, tmp_path):
    import trade_exec_bridge as bridge_module

    data_dir = tmp_path / "hermes-data"
    data_dir.mkdir()
    (data_dir / "btc_signals.json").write_text(
        json.dumps({"stage": "entry_ready", "price": 100, "entry_price": 99, "scoring_total": 12}),
        encoding="utf-8",
    )
    (data_dir / "qlib_factors.json").write_text(json.dumps({"factors": {}}), encoding="utf-8")
    (data_dir / "protections_state.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(bridge_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bridge_module, "TRADE_EVENTS", str(data_dir / "trade_events.jsonl"))
    events = []
    monkeypatch.setattr(bridge_module, "log_event", lambda event_type, symbol, details: events.append((event_type, details)))

    result = bridge_module.bridge_signal_to_execution()

    assert result["final_verdict_authorized"] is False
    assert [event_type for event_type, _details in events] == ["signal_check", "execution_blocked"]
    assert events[-1][1]["reason"] == "legacy_entry_ready_without_authorized_final_verdict"


def test_trade_bridge_blocks_legacy_entry_ready_without_final_verdict_duplicate_removed(monkeypatch, tmp_path):
    import trade_exec_bridge as bridge_module

    data_dir = tmp_path / "hermes-data"
    data_dir.mkdir()
    (data_dir / "btc_signals.json").write_text(
        json.dumps({"stage": "entry_ready", "price": 100, "entry_price": 99, "scoring_total": 12}),
        encoding="utf-8",
    )
    (data_dir / "qlib_factors.json").write_text(json.dumps({"factors": {}}), encoding="utf-8")
    (data_dir / "protections_state.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(bridge_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bridge_module, "TRADE_EVENTS", str(data_dir / "trade_events.jsonl"))
    events = []
    monkeypatch.setattr(bridge_module, "log_event", lambda event_type, symbol, details: events.append((event_type, details)))

    result = bridge_module.bridge_signal_to_execution()

    assert result["final_verdict_authorized"] is False
    assert [event_type for event_type, _details in events] == ["signal_check", "execution_blocked"]
    assert events[-1][1]["reason"] == "legacy_entry_ready_without_authorized_final_verdict"


def test_photo_delivery_requires_explicit_automation_target(tmp_path, monkeypatch):
    import telegram_reliable as tr

    photo = tmp_path / "chart.png"
    photo.write_bytes(b"png")
    monkeypatch.delenv("TANGXI_ENABLE_AUTOMATED_TG", raising=False)
    monkeypatch.delenv("TANGXI_AUTOMATED_TG_TARGET", raising=False)
    ok, reason = tr.send_telegram_photo("telegram:-100:1", str(photo))
    assert ok is False
    assert reason == "automated_delivery_disabled"


def test_trade_bridge_accepts_only_complete_go_a_final_verdict(monkeypatch, tmp_path):
    import trade_exec_bridge as bridge_module

    data_dir = tmp_path / "hermes-data"
    data_dir.mkdir()
    (data_dir / "btc_signals.json").write_text(
        json.dumps({
            "stage": "entry_ready", "price": 100, "scoring_total": 12,
            "_final_verdict": {
                "state": "GO-A", "executable": True,
                "side": "long", "entry": 100, "stop": 98, "target": 104,
                "verdict_id": "v-test",
            },
        }), encoding="utf-8",
    )
    (data_dir / "qlib_factors.json").write_text(json.dumps({"factors": {}}), encoding="utf-8")
    (data_dir / "protections_state.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(bridge_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bridge_module, "TRADE_EVENTS", str(data_dir / "trade_events.jsonl"))
    events = []
    monkeypatch.setattr(bridge_module, "log_event", lambda event_type, symbol, details: events.append((event_type, details)))

    result = bridge_module.bridge_signal_to_execution()

    assert result["final_verdict_authorized"] is True
    rows = [json.loads(line) for line in (data_dir / "trade_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["type"] == "entry_signal"
    assert rows[-1]["entry_price"] == 100
    assert rows[-1]["stop_price"] == 98
    assert rows[-1]["target_price"] == 104
    assert rows[-1]["final_verdict_executable"] is True


def test_trade_bridge_deduplicates_same_final_verdict(monkeypatch, tmp_path):
    import trade_exec_bridge as bridge_module

    data_dir = tmp_path / "hermes-data"
    data_dir.mkdir()
    signal = {
        "stage": "entry_ready", "symbol": "BTCUSDT", "price": 100, "scoring_total": 12,
        "_final_verdict": {
            "state": "GO-A", "executable": True, "side": "long",
            "entry": 100, "stop": 98, "target": 104, "verdict_id": "v-dedupe",
        },
    }
    (data_dir / "btc_signals.json").write_text(json.dumps(signal), encoding="utf-8")
    (data_dir / "qlib_factors.json").write_text(json.dumps({"factors": {}}), encoding="utf-8")
    (data_dir / "protections_state.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(bridge_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bridge_module, "TRADE_EVENTS", str(data_dir / "trade_events.jsonl"))

    first = bridge_module.bridge_signal_to_execution()
    second = bridge_module.bridge_signal_to_execution()

    assert first["final_verdict_authorized"] is True
    assert second["status"] == "already_logged"
    rows = [json.loads(line) for line in (data_dir / "trade_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(row["type"] == "entry_signal" for row in rows) == 1
    assert sum(row["type"] == "signal_check" for row in rows) == 2


def test_hard_stop_rejects_non_go_a_live_entry():
    import hard_stop

    result = hard_stop.execute_stop_loss(
        symbol="BTCUSDT", direction="long", entry=100, stop=98,
        target1=104, dry_run=False,
        final_verdict={"state": "WAIT", "executable": True, "side": "long",
                       "entry": 100, "stop": 98, "target": 104},
    )

    assert result["success"] is False
    assert result["execution_authorized"] is False
    assert "GO-A" in result["error"]


def test_hard_stop_rejects_live_parameter_mismatch():
    import hard_stop

    result = hard_stop.execute_stop_loss(
        symbol="BTCUSDT", direction="long", entry=101, stop=98,
        target1=104, dry_run=False,
        final_verdict={"state": "GO-A", "executable": True, "side": "long",
                       "entry": 100, "stop": 98, "target": 104, "risk_usd": 3.0},
    )

    assert result["success"] is False
    assert result["execution_authorized"] is False
    assert "不一致" in result["error"]


def test_hard_stop_rejects_live_risk_mismatch():
    import hard_stop

    result = hard_stop.execute_stop_loss(
        symbol="BTCUSDT", direction="long", entry=100, stop=98,
        risk_usd=2.0, target1=104, dry_run=False,
        final_verdict={"state": "GO-A", "executable": True, "side": "long",
                       "entry": 100, "stop": 98, "target": 104, "risk_usd": 3.0},
    )

    assert result["success"] is False
    assert result["execution_authorized"] is False
    assert "风险金额" in result["error"]


def test_hard_stop_rejects_live_parameter_mismatch_duplicate_removed():
    import hard_stop

    result = hard_stop.execute_stop_loss(
        symbol="BTCUSDT", direction="long", entry=101, stop=98,
        target1=104, dry_run=False,
        final_verdict={"state": "GO-A", "executable": True, "side": "long",
                       "entry": 100, "stop": 98, "target": 104, "risk_usd": 3.0},
    )

    assert result["success"] is False
    assert result["execution_authorized"] is False
    assert "不一致" in result["error"]

    assert result["success"] is False
    assert result["execution_authorized"] is False
    assert "不一致" in result["error"]


def test_hard_stop_accepts_complete_go_a_only_as_live_boundary():
    import hard_stop

    result = hard_stop.execute_stop_loss(
        symbol="BTCUSDT", direction="long", entry=100, stop=98,
        target1=104, dry_run=False,
        final_verdict={"state": "GO-A", "executable": True, "side": "long",
                       "entry": 100, "stop": 98, "target": 104, "risk_usd": 3.0},
    )

    # Current module intentionally stops before MCP execution; this verifies
    # the authorization boundary without placing any order.
    assert result["success"] is False
    assert "MCP" in result["error"]


def test_no_go_card_does_not_render_backup_prices():
    card = render_v96_card(
        symbol="BTCUSDT", status="X禁做", direction="short", price=100,
        high=105, low=95, chg=0, tf_lines="", cvd_dir="卖", cvd_quality="C",
        taker_dir="", taker_ratio=None, funding_rate=None, kill_zone="",
        vwap_ema={}, fg_v="", levels=[], bearish=True,
        st_a={"entry": 99, "stop": 101, "target": 95},
        st_b={"entry": 101, "stop": 99, "target": 105}, rr_a=0.8,
        rr_b=2.0, rr_a_note="", rr_b_note="", risk_amt=0,
        leverage_text="", inv_line=None, prot_status="通过", data_grade="C",
        sweep_state="", displacement="", one_reason="", model_id="test",
        n5=0, eng_conf=0, final_verdict={"state": "NO-GO", "executable": False, "side": "neutral"},
    )
    assert "99" not in card
    assert "101" not in card
    assert "105" not in card
    assert "不做执行" in card or "不下单" in card
