#!/usr/bin/env python3
"""Wrapper: re-exports from hermes/scripts/coingecko_collector.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))
from coingecko_collector import *
