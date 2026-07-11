from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import data_freshness_watchdog as dfw


def test_liquidation_file_with_only_api_errors_is_invalid_even_when_fresh(tmp_path):
    path = tmp_path / "liquidation_pressure.json"
    path.write_text(json.dumps({"results": [{"status": "api_error"}, {"status": "api_error"}]}), encoding="utf-8")
    assert "全部失败" in dfw._quality_issue("liquidation_pressure.json", path)


def test_liquidation_file_with_valid_row_has_no_quality_issue(tmp_path):
    path = tmp_path / "liquidation_pressure.json"
    path.write_text(json.dumps({"results": [{"symbol": "BTCUSDT", "oi": 123, "price": 64000}]}), encoding="utf-8")
    assert dfw._quality_issue("liquidation_pressure.json", path) == ""
