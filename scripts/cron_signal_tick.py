#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cron 包装：静默 tick（record + eval）。只有真发生事才输出，适配 no_agent cron。
观察窗默认 384 根（15m × 384 = 4 天）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import signal_outcome as so  # noqa: E402

if __name__ == "__main__":
    n_rec = so.record(so.CACHE, quiet=True)
    n_ev = so.evaluate(384, quiet=True)
    if n_rec or n_ev:
        print(f"[信号闭环] 新增信号 {n_rec} 条，结算 {n_ev} 条")
