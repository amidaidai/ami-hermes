#!/usr/bin/env python3
"""Compatibility wrapper for hermes/scripts/auto_card.py."""
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "hermes" / "scripts" / "auto_card.py"
if not TARGET.exists():
    raise FileNotFoundError(f"auto_card target missing: {TARGET}")
runpy.run_path(str(TARGET), run_name="__main__")
