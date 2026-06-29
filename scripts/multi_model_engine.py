#!/usr/bin/env python3
"""Wrapper: re-exports from hermes/scripts/multi_model_engine.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))
from multi_model_engine import *
