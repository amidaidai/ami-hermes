from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from go_nogo_gate import gate_report_card


def test_gate_report_uses_plain_language_header_and_unordered_gate_rows():
    result = {
        "go": False,
        "final_state": "NO-GO",
        "green_count": 2,
        "red_gates": ["tv_live"],
        "yellow_gates": [],
        "verdict": "✗ NO-GO · TV不可用",
        "gates": {
            "data_freshness": {"status": "green", "reason": "数据新鲜"},
            "tv_live": {"status": "red", "reason": "TV缓存过期"},
        },
    }
    report = gate_report_card(result, "XAUUSD")
    nonempty = [line for line in report.splitlines() if line.strip()]

    assert nonempty[1].startswith("✗ XAUUSD：")
    assert "| # |" not in report
    assert "| 1 |" not in report
    assert "| 闸门 | 状态 | 原因 |" in report
