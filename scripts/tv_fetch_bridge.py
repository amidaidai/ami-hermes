#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TradingView CDP 数据桥：零 token cron wrapper。
stdout 保持 ASCII；中文/指标数据只写 JSON 缓存。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path("D:/Hermes agent")
SCRIPT = ROOT / "tools" / "tradingview-mcp" / "fetch_tv_data.cjs"
WORKDIR = SCRIPT.parent


def main() -> int:
    if not SCRIPT.exists():
        print("ERROR: fetch script missing")
        return 1
    try:
        cp = subprocess.run(
            ["node", str(SCRIPT)],
            cwd=str(WORKDIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        print("ERROR: tv fetch timeout")
        return 1
    except FileNotFoundError:
        print("ERROR: node not found")
        return 1

    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "unknown error").encode("ascii", "ignore").decode("ascii")
        print("ERROR: tv fetch failed " + err[:300])
        return cp.returncode or 1

    # 成功静默，避免cron回传噪音。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
