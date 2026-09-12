"""Mode contracts must remain immutable across analysis requests."""
import copy
import importlib.util
from pathlib import Path


def test_mode_spec_results_cannot_mutate_shared_contract():
    path = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_router.py"
    spec = importlib.util.spec_from_file_location("isolated_pipeline_router", path)
    assert spec is not None and spec.loader is not None
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)
    baseline = copy.deepcopy(router.MODE_SPECS)
    for mode in baseline:
        result = router.analysis_mode_spec(mode)
        assert router.MODE_SPECS == baseline
        result["required_output"].append("caller_private_field")
        assert router.MODE_SPECS == baseline
    with __import__("pytest").raises(ValueError, match="Unknown analysis mode"):
        router.analysis_mode_spec("invalid-mode")
    assert router.MODE_SPECS == baseline
