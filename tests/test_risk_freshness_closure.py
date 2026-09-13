"""Risk-state consumption contract: stale/unknown must be VISIBLE, never fabricated.

Isolated: no producer, no network, no sends, no file rewriting.
"""
import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ["HANGQING_NO_SEND"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import risk_constitution as rc
import risk_constitution_v2 as v2

TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(TZ).strftime("%Y-%m-%d")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(rc, "_PROTECTIONS_FILE", tmp_path / "protections.json")
    def denied(*args, **kwargs):
        raise AssertionError("network forbidden in isolated risk tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def snapshot(date="2000-01-01"):
    return dict(date=date, daily_realized_pnl=0.0, daily_starting_balance=100.0,
                weekly_realized_pnl=0.0, weekly_starting_balance=100.0,
                trades_count=0, loss_streak=0, max_loss_streak=0,
                unreviewed_trade_count=0, suspended=False, suspend_reason="",
                trades_today=0, last_loss_time=None)


def consume(version, state=None):
    if version == "v1":
        return rc.check_constitution("BTCUSDT", risk_usd=0.5,
                                    account_balance=100.0, state=state)
    inputs = dict(symbol="BTCUSDT", account_balance=100.0, atr=1.0,
                  entry_price=100.0, stop_price=99.0, target_price=103.0,
                  regime_multiplier=1.0, protections=rc.Protections())
    if state is not None:
        inputs["risk_state"] = state
    return v2.evaluate_risk(inputs)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_stale_disk_state_is_reported_without_rewriting(version):
    path = rc.DATA_DIR / "risk_state.json"
    path.write_text(json.dumps(snapshot()), encoding="utf-8")
    before = path.read_bytes()
    out = consume(version)
    status = out["risk_state_status"]
    assert status["status"] == "stale"
    assert status["usable"] is False
    assert status["source_date"] == "2000-01-01"
    assert today_marker() in status["reason"]
    # 读取本身绝不回写/刷新文件，也不把旧快照洗成当天。
    assert path.read_bytes() == before
    assert rc.load_risk_state().date == "2000-01-01"


def today_marker():
    return TODAY


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("payload,expected", [(None, "missing"), ("{", "invalid"),
    ("{}", "missing"), ('{"date":"2099-01-01"}', "invalid")])
def test_unavailable_state_never_invents_freshness_or_balance(version, payload, expected):
    path = rc.DATA_DIR / "risk_state.json"
    if payload is not None:
        path.write_text(payload, encoding="utf-8")
    out = consume(version)
    status = out["risk_state_status"]
    assert status["status"] == expected
    assert status["usable"] is False
    state = rc.load_risk_state()
    assert state.daily_starting_balance == 0.0
    assert state.weekly_starting_balance == 0.0
    assert state.date != TODAY
    assert path.exists() == (payload is not None)
    if payload is not None:
        assert path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_explicit_empty_state_is_not_a_verified_account(version):
    out = consume(version, rc.RiskState())
    assert out["risk_state_status"]["status"] == "missing"
    assert out["risk_state_status"]["usable"] is False


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_fresh_state_is_usable_and_sizing_still_works(version):
    path = rc.DATA_DIR / "risk_state.json"
    path.write_text(json.dumps(snapshot(date=TODAY)), encoding="utf-8")
    out = consume(version)
    assert out["risk_state_status"]["status"] == "fresh"
    assert out["risk_state_status"]["usable"] is True
    # 新鲜状态不改变既有风控语义：正常输入仍能给出可执行仓位。
    assert out["allowed"] is True
