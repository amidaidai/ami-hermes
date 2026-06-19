#!/usr/bin/env python3
"""兼容入口。真正脚本：行情守望.py"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("行情守望.py")), run_name="__main__")
