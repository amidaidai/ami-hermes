#!/usr/bin/env python3
"""兼容入口。真正脚本：信号巡检.py"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("信号巡检.py")), run_name="__main__")
