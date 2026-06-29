#!/usr/bin/env python3
"""Compatibility wrapper for hermes/scripts/multi_source_collector.py.

Runtime modules sometimes add D:/Hermes agent/scripts before hermes/scripts on
sys.path. A plain ``from multi_source_collector import *`` imports this file
again and hides cmc_quote/cmc_global. Load the canonical implementation by
absolute path under a private module name instead.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parent.parent / "hermes" / "scripts" / "multi_source_collector.py"
_spec = importlib.util.spec_from_file_location("_tangxi_multi_source_collector", _CANONICAL)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load canonical multi_source_collector: {_CANONICAL}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

for _name, _value in vars(_mod).items():
    if not _name.startswith("_"):
        globals()[_name] = _value

__all__ = [k for k in globals() if not k.startswith("_")]
