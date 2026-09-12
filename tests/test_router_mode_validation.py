"""Explicit machine modes fail closed; natural-language defaults are separate."""
import ast
import importlib.util
from datetime import datetime, timezone
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("router_mode_validation", ROOT / "scripts/pipeline_router.py")
assert SPEC is not None and SPEC.loader is not None
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


@pytest.mark.parametrize("mode", ["Fuuull", "", "  ", None, 0, False, [], {}, "L3"])
@pytest.mark.parametrize("consumer", ["analysis_mode_spec", "route_pipeline", "pipeline_summary", "tier_for_mode", "tier_label", "tier_scope"])
def test_explicit_invalid_modes_raise_value_error(mode, consumer):
    function = getattr(router, consumer)
    args = ("BTCUSDT", mode) if consumer in {"route_pipeline", "pipeline_summary"} else (mode,)
    with pytest.raises(ValueError, match="Unknown analysis mode"):
        function(*args)


@pytest.mark.parametrize("mode", ["quick", "inherit", "standard", "full", "monitor"])
def test_known_modes_preserve_case_whitespace_and_contract(mode):
    supplied = f" {mode.upper()} "
    assert router.analysis_mode_spec(supplied)["mode"] == mode
    for symbol in ("BTCUSDT", "XAUUSD"):
        assert router.route_pipeline(symbol, supplied) == router.route_pipeline(symbol, mode)


def test_omitted_route_mode_and_natural_language_defaults_remain_distinct():
    assert router.route_pipeline("BTCUSDT") == list(router.CRYPTO_FULL_PIPELINE)
    assert router.resolve_analysis_mode("BTC") == "quick"


def test_inherit_alias_is_displayed_as_standard_not_quick():
    assert router.tier_for_mode(" INHERIT ") == "L2"
    assert router.tier_label("inherit") == router.tier_label("standard")
    assert router.tier_scope("inherit") == router.tier_scope("standard")


def test_auto_card_does_not_swallow_router_validation_error(monkeypatch):
    # Load only the real function AST, not module initialization or credentials.
    path = ROOT / "scripts/auto_card.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "auto_card")
    # Exercise the real entry/preflight/router block only; never collect or send.
    stop = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "completed_steps" for target in node.targets))
    function.body = function.body[:stop]
    namespace = {"datetime": datetime, "TZ": timezone.utc, "_asset_class": lambda symbol: "crypto"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    def reject(*args):
        raise ValueError("Unknown analysis mode: injected invalid contract")
    fake_router = types.ModuleType("pipeline_router")
    setattr(fake_router, "route_pipeline", reject)
    setattr(fake_router, "load_analysis_context", lambda symbol: None)
    monkeypatch.setitem(sys.modules, "pipeline_router", fake_router)
    with pytest.raises(ValueError, match="Unknown analysis mode"):
        namespace["auto_card"]("BTCUSDT", push=False, mode="quick")

