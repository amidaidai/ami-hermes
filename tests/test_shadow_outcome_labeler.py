from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_outcome_labeler as sol


def test_production_adapter_preserves_ohlc_and_only_mature_closes():
    record = _record() | {"order_model": {"type": "market_next_open"}}
    bars = _bars()
    rows, stats = sol.label_ready_records([record], lambda *_: bars, now_ms=bars[-1][6])
    assert not rows and stats["waiting"] == 1
    rows, stats = sol.label_ready_records([record], lambda *_: bars, now_ms=bars[-1][6] + 1)
    assert rows[0]["outcome"]["h16"]["mature"] is True
    assert rows[0]["outcome"]["h16"]["filled"] is True
    assert rows[0]["labeled_at"] == bars[-1][6] + 1
    bar = sol._bar_dict(bars[0])
    assert bar["open"] == 100 and bar["close"] == 100
    assert bar["open_time"] == bars[0][0] and bar["close_time"] == bars[0][6]


def test_futures_failure_never_downgrades_to_spot(monkeypatch):
    urls = []
    def fail(url, direct):
        urls.append(url)
        raise OSError("offline")
    monkeypatch.setattr(sol, "_fetch_json", fail)
    assert sol.fetch_binance_closed_bars("BTCUSDT", "15m", 1, 16) == []
    assert urls and all("fapi.binance.com/fapi/" in url for url in urls)


def test_missing_first_bar_or_gap_cannot_shift_next_open_fill():
    for bars in (_bars(17)[1:], _bars(17)[:3] + _bars(17)[4:]):
        rows, stats = sol.label_ready_records([_record()], lambda *_: bars, now_ms=99_000_000)
        assert rows == []
        assert stats["waiting"] == 1


@pytest.mark.parametrize("timeframe,step", [("5m", 300_000), ("1h", 3_600_000), ("4h", 14_400_000), ("1d", 86_400_000)])
@pytest.mark.parametrize("missing", [0, 3])
def test_continuity_uses_record_timeframe(timeframe, step, missing):
    record = _record(ts=step + 1) | {"timeframe": timeframe, "order_model": {"type": "market_next_open"}}
    bars = [[i, "100", "101", "99", "100", "10", i + step - 1]
            for i in range(2 * step, 19 * step, step)]
    good, stats = sol.label_ready_records([record], lambda *_: bars, now_ms=20 * step)
    assert stats["labeled"] == 1
    assert good[0]["outcome"]["h16"]["filled"] is True
    del bars[missing]
    rows, stats = sol.label_ready_records([record], lambda *_: bars, now_ms=20 * step)
    assert rows == []
    assert stats["waiting"] == 1


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
        for i in range(1_800_000, 1_800_000 + count * 900_000, 900_000)
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
