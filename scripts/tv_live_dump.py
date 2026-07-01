#!/usr/bin/env python3
"""Compatibility wrapper: refresh live TV cache through tv_data_bridge.

历史版本曾写入硬编码BTC关键位；现在统一调用真实TradingView CDP采集，禁止静态数据落盘。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tv_data_bridge import collect_and_cache  # noqa: E402


if __name__ == "__main__":
    result = collect_and_cache(alert_mode="--alert" in sys.argv)
    if result is None:
        print("tv_dmi_cache.json refresh failed: TradingView CDP unavailable")
        sys.exit(1)
    print(
        "tv_dmi_cache.json refreshed:",
        "symbol", result.get("symbol"),
        "POC", result.get("poc"),
        "VAH", result.get("vah"),
        "VAL", result.get("val"),
    )
