"""Pure diagnostic-gate regressions; no live I/O or push calls."""
import os
import sys
from pathlib import Path

import pytest

os.environ["HANGQING_NO_SEND"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from go_nogo_gate import check_gate


def rr_gate(meta, final=None):
    engine = {"_final_verdict": final} if final is not None else {}
    return check_gate("BTCUSDT", engine, meta)["gates"]["rr_ratio"]


@pytest.mark.parametrize("value", [float("inf"), float("nan"), float("-inf"), "inf", "nan", "bad", {}, [], None, "", 0, False])
def test_invalid_explicit_primary_never_borrows_alias(value):
    gate = rr_gate({"rr_a": value, "rr1": 3.4, "rr_b": 3.4})
    assert gate["status"] == "red"
    assert "1:inf" not in gate["reason"]
    assert "1:nan" not in gate["reason"]


@pytest.mark.parametrize("value", [float("inf"), "bad", {}, None])
def test_invalid_opposite_never_crashes_primary(value):
    assert rr_gate({"rr_a": 2.5, "rr_b": value})["status"] == "green"


@pytest.mark.parametrize("state", ["GO-A", "WAIT", "NO-GO"])
@pytest.mark.parametrize("value,expected", [(0.566, "red"), (3.4, "green"), (0, "red"), (None, "red"), (float("inf"), "red"), ("bad", "red")])
def test_canonical_rr_overrides_legacy_in_every_state(state, value, expected):
    final = {"state": state, "executable": state == "GO-A", "rr": value}
    legacy = 0.566 if expected == "green" else 3.4
    gate = rr_gate({"rr_a": legacy, "rr_b": 3.4}, final)
    assert gate["status"] == expected
    assert gate["source"] == "final_verdict.rr"


def test_absent_primary_accepts_legacy_same_side_alias():
    assert rr_gate({"rr1": 2.5, "rr_b": 3.4})["status"] == "green"


@pytest.mark.parametrize("value", [0.547, 0.566])
def test_nonzero_small_primary_cannot_be_opposite(value):
    assert rr_gate({"rr_a": value, "rr_b": 3.404})["status"] == "red"
