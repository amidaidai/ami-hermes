from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_outcome_labeler as sol


def _record(signal_id="BTC-1", ts=1_000_000):
    return {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "ts": ts,
        "side": "long",
        "entry": 100.0,
        "stop": 98.0,
        "target": 104.0,
        "model_id": "fvg_pullback",
        "regime": {"code": "trend"},
    }


def _bars(count=16):
    return [
        [i, "100", "101", "99", "100", "10", i + 899_999]
        for i in range(count)
    ]


def test_label_ready_records_waits_for_full_longest_horizon():
    rows, stats = sol.label_ready_records([_record()], lambda *_: _bars(15), now_ms=99_000_000)
    assert rows == []
    assert stats["waiting"] == 1


def test_label_ready_records_projects_nested_main_and_is_idempotent():
    record = _record() | {
        "main": {"direction": "short", "entry": 100.0, "stop": 102.0, "target": 96.0, "model_id": "ob_pullback"}
    }
    rows, stats = sol.label_ready_records([record], lambda *_: _bars(16), now_ms=99_000_000, existing_ids={"other"})
    assert stats["labeled"] == 1
    assert rows[0]["side"] == "short"
    assert rows[0]["model_id"] == "ob_pullback"
    assert set(rows[0]["outcome"]) == {"h4", "h8", "h16"}

    rows2, stats2 = sol.label_ready_records([record], lambda *_: _bars(16), now_ms=99_000_000, existing_ids={str(record["signal_id"])})
    assert rows2 == []
    assert stats2["existing"] == 1


def test_label_ready_records_skips_non_crypto_without_false_failure():
    record = _record() | {"symbol": "XAUUSD"}
    rows, stats = sol.label_ready_records([record], lambda *_: (_ for _ in ()).throw(AssertionError()), now_ms=99_000_000)
    assert rows == []
    assert stats["unsupported"] == 1
