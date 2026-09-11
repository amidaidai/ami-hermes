#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cron 包装：每日分组报告（副确认 / 副未确认 / 副缺数据 / 副不参与 的胜率与期望R）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import signal_outcome as so  # noqa: E402

if __name__ == "__main__":
    so.report()
