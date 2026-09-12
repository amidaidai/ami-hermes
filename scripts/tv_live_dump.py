#!/usr/bin/env python3
"""Compatibility wrapper: refresh live TV cache through tv_data_bridge.

历史版本曾写入硬编码BTC关键位；现在统一调用真实TradingView CDP采集，禁止静态数据落盘。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tv_data_bridge import collect_and_cache  # noqa: E402
from atomic_json import atomic_write_json  # noqa: E402


TV_SYMBOL_ALIASES = {
    "BTCUSDT": "BINANCE:BTCUSDT.P",
    "XAUUSD": "OANDA:XAUUSD",
}


def resolve_tv_symbol(symbol: str) -> str:
    raw = str(symbol or "").upper().strip()
    return TV_SYMBOL_ALIASES.get(raw, raw)


def _symbol_key(symbol: str) -> str:
    raw = str(symbol or "").upper().split(":")[-1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    key = re.sub(r"[^A-Z0-9]", "", raw)
    return key[:-4] if key.endswith("PERP") else key


def cache_paths_for_symbol(symbol: str) -> list[Path]:
    key = _symbol_key(symbol)
    specific = ROOT / "data" / f"tv_live_{key}.json"
    if key in {"BTCUSDT", "BTCUSD"}:
        return [ROOT / "data" / "tv_live.json", specific]
    return [specific]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="刷新指定品种的TradingView实时缓存")
    parser.add_argument("--symbol", default="BINANCE:BTCUSDT.P")
    parser.add_argument("--alert", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeframe", default="", help="主周期代码，例如 5/15/60/240")
    parser.add_argument("--batch-id", default="", help="可选采集批次标识，用于XAU双缓存原子配对")
    args = parser.parse_args()
    expected_symbol = resolve_tv_symbol(args.symbol)
    if args.timeframe:
        cli = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"
        tf_result = subprocess.run(
            ["node", str(cli), "timeframe", str(args.timeframe)],
            cwd=str(cli.parents[2]), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if tf_result.returncode != 0:
            print(f"tv timeframe switch failed: {(tf_result.stderr or tf_result.stdout)[:160]}")
            sys.exit(1)
    result = collect_and_cache(alert_mode=args.alert, expect_symbol=expected_symbol)
    if result is None or result.get("stale") or not result.get("fresh"):
        print(f"tv cache refresh failed or stale for {expected_symbol}")
        sys.exit(1)
    if _symbol_key(str(result.get("symbol") or "")) != _symbol_key(expected_symbol):
        print(f"tv cache symbol mismatch: expected {expected_symbol}, got {result.get('symbol')}")
        sys.exit(1)

    live_payload = dict(result)
    live_payload["source"] = "tv_live_dump"
    if args.batch_id:
        live_payload["batch_id"] = args.batch_id
    live_paths = cache_paths_for_symbol(str(result.get("symbol") or args.symbol))
    for live_path in live_paths:
        atomic_write_json(live_path, live_payload)

    # 默认静默成功，避免 no_agent cron 噪音；--verbose 才输出摘要。
    if args.verbose:
        print(
            f"{live_paths[0].name}+{live_paths[1].name} refreshed:",
            "symbol", result.get("symbol"),
            "POC", result.get("poc"),
            "VAH", result.get("vah"),
            "VAL", result.get("val"),
        )
