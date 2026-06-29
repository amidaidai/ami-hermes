#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TradingView CDP 数据桥：零 token cron wrapper。
支持多品种：BTCUSDT (默认), XAUUSD 等。
stdout 保持 ASCII；中文/指标数据只写 JSON 缓存。
"""
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path("D:/Hermes agent")
SCRIPT = ROOT / "tools" / "tradingview-mcp" / "fetch_tv_data.cjs"
WORKDIR = SCRIPT.parent

SYMBOLS = ["BINANCE:BTCUSDT.P", "OANDA:XAUUSD"]


def fetch_one(symbol: str) -> int:
    if not SCRIPT.exists():
        print(f"ERROR: fetch script missing for {symbol}")
        return 1
    try:
        cp = subprocess.run(
            ["node", str(SCRIPT), symbol],
            cwd=str(WORKDIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: tv fetch timeout for {symbol}")
        return 1
    except FileNotFoundError:
        print("ERROR: node not found")
        return 1

    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "unknown error").encode("ascii", "ignore").decode("ascii")
        print(f"ERROR: tv fetch failed for {symbol}: {err[:300]}")
        return cp.returncode or 1

    return 0


def main() -> int:
    errors = 0
    for sym in SYMBOLS:
        result = fetch_one(sym)
        if result != 0:
            errors += 1
    return 1 if errors == len(SYMBOLS) else 0


if __name__ == "__main__":
    raise SystemExit(main())
