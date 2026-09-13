# -*- coding: utf-8 -*-
"""XAU 具名粒度修复回归（2026-09-13）

背景：XAU 无 keylevels 配置、走 klines 回退路径生成名字（旧式 f"{tf}高" 无空格）。
`_LEVEL_TF_RE` 的 \b 对「5m高」（中文紧邻）不匹配 → 卡面只显示无周期的「阻/支」，
等待条件具名化退化为「等 阻 / 支 方向确认」。
修复：回退名字改带空格前缀（"5m 高"），与既有「15m VAL」格式统一。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import _level_kind


def test_fallback_level_names_use_spaced_tf_prefix():
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'f"{tf} VAH"' in src
    assert 'f"{tf} 高"' in src
    assert 'f"{tf}VAH"' not in src  # 旧式无空格已清零
    assert 'f"{tf}高"' not in src


def test_level_kind_extracts_tf_from_spaced_names():
    label, _icon, use = _level_kind("5m 高", "resistance", 4346.0, 4348.0)
    assert label == "5m·阻"
    label2, _icon2, use2 = _level_kind("4h VAH", "resistance", 4352.0, 4348.0)
    assert label2 == "4h·VAH"
    label3, _icon3, use3 = _level_kind("15m 低", "support", 4343.0, 4348.0)
    assert label3 == "15m·支"


def test_level_kind_without_space_stays_unprefixed():
    # 无空格中文紧邻形式不识别周期（防回退到旧格式时的行为基线）
    label, _icon, _use = _level_kind("5m高", "resistance", 4346.0, 4348.0)
    assert label == "阻"
