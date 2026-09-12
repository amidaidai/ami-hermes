from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from render_tv_card import render_tv_card


def test_push_card_renders_price_bar_and_ict_evidence():
    evidence = {
        "status": "partial",
        "identity": {"timeframe": "15"},
        "price_context": {
            "open": 100, "high": 105, "low": 98, "close": 103,
            "last_price": 103, "complete": True,
        },
        "ict": {
            "fvg": [{"label": "FVG"}],
            "ob": [{"label": "OB"}],
            "structure_labels": [{"text": "MSS"}],
            "liquidity": [{"label": "PDH"}],
        },
    }
    main = {
        "grade": "C等待", "direction": "观望", "conclusion": "等待确认",
        "chart_evidence": evidence,
        "_final_verdict": {"state": "WAIT", "executable": False},
        "_klines": {},
    }
    card = render_tv_card(main, {}, "BTCUSDT", 103, mode="push")
    assert "图表证据：partial · 15" in card
    assert "价格栏：O100.00 H105.00 L98.00 C103.00 · 现103.00" in card
    assert "ICT：FVG1 · OB1 · BOS/MSS1 · 流动性1" in card
    assert "不升级GO-A" in card
