"""Manual risk reconciliation: explicit inputs only, never invents an account."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("risk_state_reconcile", ROOT / "scripts/risk_state_reconcile.py")
assert spec is not None and spec.loader is not None
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "STATE_PATH", tmp_path / "risk_state.json")


def test_requires_explicit_balance_and_writes_nothing():
    with pytest.raises(SystemExit):
        R.main(["--write"])          # argparse 直接拒绝：没有余额就不进入流程
    assert not R.STATE_PATH.exists()


@pytest.mark.parametrize("bad", ["0", "-5"])
def test_non_positive_balance_is_refused(bad, capsys):
    assert R.main(["--balance", bad, "--write"]) == 2
    assert not R.STATE_PATH.exists()
    assert "禁止编造" in capsys.readouterr().err


def test_dry_run_previews_without_writing(capsys):
    assert R.main(["--balance", "500", "--daily-pnl", "-3.5"]) == 0
    assert not R.STATE_PATH.exists()
    assert "dry-run" in capsys.readouterr().out


def test_write_stamps_today_and_reports_fresh_status():
    assert R.main(["--balance", "500", "--daily-pnl", "-3.5", "--write"]) == 0
    payload = json.loads(R.STATE_PATH.read_text(encoding="utf-8"))
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    assert payload["date"] == today
    assert payload["daily_starting_balance"] == 500
    assert payload["daily_realized_pnl"] == -3.5
    assert payload["reconciled_by"] == "manual_cli"

    from risk_constitution import RiskState, risk_state_status
    state = RiskState(**{k: v for k, v in payload.items() if k in RiskState.__dataclass_fields__})
    assert risk_state_status(state)["status"] == "fresh"


def test_unrelated_keys_are_preserved():
    R.STATE_PATH.write_text(json.dumps({
        "date": "2026-07-15", "daily_starting_balance": 67.52,
        "last_unreviewed_trade": {"symbol": "BTCUSDT", "note": "keep me"},
        "max_daily_loss": 30.0,
    }), encoding="utf-8")
    assert R.main(["--balance", "800", "--write"]) == 0
    payload = json.loads(R.STATE_PATH.read_text(encoding="utf-8"))
    assert payload["last_unreviewed_trade"]["note"] == "keep me"
    assert payload["max_daily_loss"] == 30.0
    assert payload["daily_starting_balance"] == 800


def test_unreviewed_count_survives_when_not_given():
    R.STATE_PATH.write_text(json.dumps({"unreviewed_trade_count": 2}), encoding="utf-8")
    assert R.main(["--balance", "100", "--write"]) == 0
    assert json.loads(R.STATE_PATH.read_text(encoding="utf-8"))["unreviewed_trade_count"] == 2


def test_corrupt_existing_file_is_refused_not_overwritten():
    R.STATE_PATH.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        R.main(["--balance", "100", "--write"])
    assert R.STATE_PATH.read_text(encoding="utf-8") == "{not json"
