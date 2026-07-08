from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card


def test_question_mark_grade_does_not_block_mcp_svp_fallback():
    """tv_dmi_cache grade='?' 时，必须回退到 MCP Side/Grade，不能渲染 SVP ? ?."""
    dmi_rows = {
        "等级": "?",
        "处理": "?",
        "结论": "缩量阴跌 · 动能弱,别追空",
        "方向": "观望 · 深折价",
        "进场": "等触发",
        "止损": "—",
        "目标": "↑周二 纽 高 64234.1",
    }
    tv_vals = {
        "MCP Side Code": 9.0,
        "MCP Grade Code": -1.0,
        "MCP Target Price": 64234.1,
        "MCP CVD Value": -542.5,
        "MCP Quality Code": 3.0,
    }
    main = auto_card._build_tv_main_data(dmi_rows, tv_vals, price=63030)
    assert main["grade"] == "X"
    assert main["treatment"] == "缩量阴跌 · 动能弱,别追空"


def test_tv_override_inferrs_grade_from_mcp_when_table_grade_unknown():
    meta = {"status": "B等待", "direction": "wait"}
    engine = {}
    dmi_rows = {"等级": "?", "处理": "?", "结论": "缩量阴跌 · 动能弱,别追空"}
    tv_vals = {"MCP Side Code": 9.0, "MCP Grade Code": -1.0}
    result = auto_card._apply_tv_dmi_override(meta, engine, "BTCUSDT", dmi_rows, tv_vals)
    assert result["tv_grade"] == "X"
    assert meta["status"] == "X禁做"
    assert meta["direction"] == "wait"
