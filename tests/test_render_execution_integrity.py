"""Execution cards reject malformed canonical tuples at both render boundaries."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_tv_card import _final_is_executable
from render_v96 import render_v96_card


def render(final, rr_a: object = 3.0, rr_b: object = 2.0, status="GO-A", direction="long"):
    return render_v96_card(
        "BTCUSDT", status, direction, 100, 110, 90, 0, "", "买", "A", "买", 1.1,
        "0.01%", "", {}, "25", [], False,
        {"entry": 100, "stop": 98, "target": 106}, {}, rr_a, rr_b, "", "",
        risk_amt=1, leverage_text="", inv_line=98, prot_status="通过", data_grade="A",
        sweep_state="", displacement="", one_reason="", model_id="test", n5=0,
        eng_conf=0, final_verdict=final,
    )


def valid():
    return dict(state="GO-A", executable=True, grade="A多", side="long",
                entry=100, stop=98, target=106, rr=3.0)


@pytest.mark.parametrize("patch", [
    {"target": float("inf")}, {"stop": -1}, {"rr": float("inf")},
    {"rr": float("nan")}, {"rr": "bad"}, {"rr": 0},
    {"rr": 1.5}, {"target": 101, "rr": 3}, {"stop": 102}, {"grade": "X禁做"},
])
def test_both_renderers_fail_closed(patch):
    final = {**valid(), **patch}
    assert not _final_is_executable(final)
    card = render(final)
    assert "可执行" not in card
    assert "⭐主推 多" not in card
    assert "损98" not in card
    assert "失效 `98`" not in card


def test_valid_canonical_tuple_remains_executable():
    assert _final_is_executable(valid())
    assert "可执行" in render(valid())


def test_invalidation_uses_canonical_stop_not_legacy_argument():
    card = render({**valid(), "stop": 99, "rr": 6})
    assert "失效 `99.00`" in card
    assert "失效 `98.00`" not in card


# ── 旧计划参数（rr_a / rr_b）非法时不得崩溃，也不得冒充 R:R 事实 ──────────────

@pytest.mark.parametrize("bad", [None, "bad", float("nan"), float("inf"), "", {}, []])
def test_wait_state_survives_malformed_legacy_rr(bad):
    card = render({"state": "WAIT", "executable": False, "grade": "C等待"},
                  rr_a=bad, rr_b=bad)
    assert "等确认" in card
    assert "R:R不足" not in card
    assert "损98" not in card


@pytest.mark.parametrize("bad", [None, "bad", float("inf"), float("nan")])
def test_executable_card_survives_malformed_backup_rr(bad):
    card = render(valid(), rr_b=bad)
    assert "可执行" in card
    assert "备选" in card
    assert "1:nan" not in card and "1:inf" not in card


def test_missing_rr_is_not_reported_as_insufficient_rr():
    card = render({"state": "WAIT", "executable": False, "grade": "C等待"},
                  rr_a=None)
    assert "R:R不足" not in card
    assert "缺失或非法" in card or "等确认" in card


def test_price_grade_does_not_claim_source_health():
    assert "价格共识A" in render(valid())
    assert "数据A" not in render(valid())


def test_wait_canonical_rr_is_not_hidden_by_legacy_plan():
    card = render({"state": "WAIT", "executable": False, "rr": 0.5}, rr_a=3)
    assert "主线R:R不足" in card


def test_missing_canonical_rr_does_not_borrow_legacy():
    card = render({"state": "WAIT", "executable": False, "rr": None}, rr_a=0.5)
    verdict = next(line for line in card.splitlines() if line.startswith("【裁决】"))
    assert "R:R不足" not in verdict
