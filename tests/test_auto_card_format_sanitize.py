from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

import auto_card


def test_sanitize_card_format_removes_decorative_emoji_and_square_brackets():
    raw = "- 总分：**7.7/14** · 🥈 A\n- 市场：🔴 LOW_VOL_BEAR\n- 搜索：热词[Sentiment·Greed]"
    clean = auto_card.sanitize_card_format(raw)
    assert "🥈" not in clean
    assert "🔴" not in clean
    assert "[" not in clean and "]" not in clean
    assert "热词：Sentiment·Greed" in clean
