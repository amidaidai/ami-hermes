from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shadow_calibration import append_shadow_signal, calibrate_groups, label_outcome


def test_empty_and_short_history_never_mature():
    for bars in ([], [{"open": 100, "high": 105, "low": 99, "close": 104}]):
        out = label_outcome(_signal(), bars)["h16"]
        assert out["mature"] is False
        assert out["gross_r"] is None


def _signal(**overrides):
    data = {
        "signal_id": "BTC-15m-1", "symbol": "BTCUSDT", "timeframe": "15m",
        "ts": 1, "side": "long", "entry": 100.0, "stop": 98.0, "target": 104.0,
        "model_id": "fvg_pullback", "regime": "trend", "grade": "A",
        "fvg_quality": 82.0, "ob_quality": 60.0, "haldro_valid_code": 2,
    }
    data.update(overrides)
    return data


def _bar(open=100.0, high=101.0, low=99.0, close=100.0, **extra):
    return dict(open=open, high=high, low=low, close=close, **extra)


def test_limit_requires_entry_touch_and_missing_model_is_degraded():
    bars = [_bar(open=104, high=105, low=103, close=104)] * 16
    missing = label_outcome(_signal(), bars)["h16"]
    assert missing["status"] == "missing_order_model"
    out = label_outcome(_signal(order_model={"type": "limit"}), bars)["h16"]
    assert out["filled"] is False
    assert out["first_hit"] == "none"
    assert out["gross_r"] is None


def test_limit_dual_touch_is_stop_first_and_gap_stop_uses_open():
    signal = _signal(order_model={"type": "limit"})
    both = label_outcome(signal, [_bar(high=105, low=97)], horizons=(1,))["h1"]
    assert both["filled"] is True
    assert both["first_hit"] == "stop"
    assert both["gross_r"] == -1
    gap = label_outcome(signal, [_bar(), _bar(open=95, high=97, low=94, close=96)], horizons=(2,))["h2"]
    assert gap["exit_price"] == 95
    assert gap["gross_r"] == -2.5


def test_limit_intrabar_target_before_fill_not_assumed():
    out = label_outcome(_signal(order_model={"type": "limit"}),
                        [_bar(open=103, high=105, low=99, close=101)], horizons=(1,))["h1"]
    assert out["filled"] is True
    assert out["first_hit"] == "none"
    assert out["gross_r"] is None


def test_market_next_open_and_costs_are_explicit_and_sensitive():
    bars = [_bar(open=101, high=105, low=100, close=104, funding_rate=0.001)]
    signal = _signal(order_model={"type": "market_next_open"})
    missing = label_outcome(signal, bars, horizons=(1,))["h1"]
    assert missing["fill_price"] == 101
    assert missing["net_r"] is None
    signal["cost_model"] = {"fee_bps": 10, "slippage_bps": 10, "funding": "per_bar"}
    out = label_outcome(signal, bars, horizons=(1,))["h1"]
    assert out["gross_r"] == 1.5
    assert out["net_r"] < out["gross_r"]
    assert out["funding_r"] > 0
    signal["cost_model"]["fee_bps"] = 20
    assert label_outcome(signal, bars, horizons=(1,))["h1"]["net_r"] < out["net_r"]


def test_bad_or_unclosed_ohlc_is_not_mature_or_filled():
    for bar in ({"high": 105, "low": 99}, _bar(closed=False), _bar(high=float("nan"))):
        out = label_outcome(_signal(order_model={"type": "limit"}), [bar], horizons=(1,))["h1"]
        assert out["mature"] is False
        assert out["filled"] is False


def test_label_outcome_records_mfe_mae_and_first_barrier_for_each_horizon():
    bars = [
        {"high": 101.0, "low": 99.0},
        {"high": 103.0, "low": 99.5},
        {"high": 104.5, "low": 100.0},
        {"high": 105.0, "low": 99.0},
    ]
    bars = [{"open": 100, "close": 100, **bar} for bar in bars]
    out = label_outcome(_signal(order_model={"type": "limit"}), bars, horizons=(2, 4))
    assert out["h2"]["mfe_r"] == 1.5
    assert out["h2"]["mae_r"] == 0.5
    assert out["h2"]["first_hit"] == "none"
    assert out["h4"]["first_hit"] == "target"
    assert out["h4"]["bars_to_hit"] == 3


def test_short_outcome_uses_inverse_price_direction():
    bars = [{"high": 100.5, "low": 98.0}, {"high": 101.0, "low": 95.0}]
    bars = [{"open": 100, "close": 100, **bar} for bar in bars]
    signal = _signal(side="short", stop=102.0, target=96.0, order_model={"type": "limit"})
    out = label_outcome(signal, bars, horizons=(2,))
    assert out["h2"]["mfe_r"] == 2.5
    assert out["h2"]["mae_r"] == 0.5
    assert out["h2"]["first_hit"] == "target"


def test_append_shadow_signal_is_idempotent(tmp_path):
    path = tmp_path / "signals.jsonl"
    assert append_shadow_signal(path, _signal()) is True
    assert append_shadow_signal(path, _signal()) is False
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1


def test_append_shadow_signal_upgrades_same_bucket_when_live_authority_improves(tmp_path):
    path = tmp_path / "signals.jsonl"
    stale = _signal(haldro_valid_code=0) | {"dual": {"valid_code": 0}}
    fresh = _signal(haldro_valid_code=2) | {"dual": {"valid_code": 2}, "main": {"model_id": "fvg_pullback"}}
    assert append_shadow_signal(path, stale) is True
    assert append_shadow_signal(path, fresh) is True
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["dual"]["valid_code"] == 2
    assert "main" in rows[0]


def test_calibration_accepts_nested_regime_contract():
    rows = [
        _signal(signal_id=str(i), regime={"code": "trend"})
        | {"outcome": {"h16": {"first_hit": "target", "mature": True, "filled": True}}}
        for i in range(30)
    ]
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    assert stats["trend|fvg_pullback"]["samples"] == 30
    assert stats["trend|fvg_pullback"]["calibrated_win_rate"] == 1.0


def test_calibration_never_emits_probability_below_min_samples():
    rows = []
    for i in range(29):
        rows.append(_signal(signal_id=str(i)) | {"outcome": {"h16": {"first_hit": "target", "mature": True, "filled": True}}})
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    bucket = stats["trend|fvg_pullback"]
    assert bucket["samples"] == 29
    assert bucket["calibrated_win_rate"] is None
    rows.append(_signal(signal_id="29") | {"outcome": {"h16": {"first_hit": "stop", "mature": True, "filled": True}}})
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    assert stats["trend|fvg_pullback"]["calibrated_win_rate"] == 29 / 30


def test_calibration_requires_thirty_mature_filled_decisions_not_thirty_rows():
    rows = [_signal(signal_id=str(i)) | {"outcome": {"h16": {
        "first_hit": "target" if i == 0 else "none", "mature": True, "filled": True}}}
        for i in range(30)]
    bucket = calibrate_groups(rows)["trend|fvg_pullback"]
    assert bucket["reliable"] is False
    assert bucket["calibrated_win_rate"] is None
    assert bucket["min_samples"] == 30
    assert bucket["win_rate_interval"] is None
    for row in rows:
        row["outcome"]["h16"] = {"first_hit": "target", "mature": False, "filled": False}
    assert calibrate_groups(rows)["trend|fvg_pullback"]["decisive_samples"] == 0


def test_calibration_emits_wilson_interval_not_certainty():
    rows = [_signal(signal_id=str(i)) | {"outcome": {"h16": {
        "first_hit": "target", "mature": True, "filled": True}}} for i in range(30)]
    bucket = calibrate_groups(rows)["trend|fvg_pullback"]
    low, high = bucket["win_rate_interval"]
    assert 0 < low < high <= 1
    assert bucket["interval_method"] == "wilson_95"
