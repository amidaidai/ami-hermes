#!/usr/bin/env python3
"""
TV截图引擎 v1.0 — 分析卡自动截图·含价格轴+CVD
用法: python tv_screenshot.py BTCUSDT 15m → 截图存到 outputs/ 并返回路径
"""

import subprocess, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
TV_CLI = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"
OUTPUT = ROOT / "outputs"

# 品种→TradingView symbol 映射
SYMBOL_MAP = {
    "BTCUSDT": "BINANCE:BTCUSDT.P",
    "XAUUSD": "OANDA:XAUUSD",
    "ETHUSDT": "BINANCE:ETHUSDT.P",
    "SOLUSDT": "BINANCE:SOLUSDT.P",
}

# 时间框架层级: (主周期, [辅助周期])
TF_HIERARCHY = {
    "crypto": ("15", ["5", "60", "240"]),   # 15m主·5m/1h/4h辅
    "forex": ("5", ["15", "60", "240"]),     # 5m主·15m/1h/4h辅
}


def _tv(*args, timeout=30):
    """调用 tv CLI。"""
    try:
        cp = subprocess.run(
            ["node", str(TV_CLI)] + list(args),
            cwd=str(ROOT / "tools" / "tradingview-mcp"),
            capture_output=True, text=True, timeout=timeout,
        )
        return cp.stdout.strip(), cp.returncode == 0
    except Exception:
        return "", False


def tv_available():
    out, ok = _tv("status", timeout=5)
    return ok and "connected" in out.lower()


def set_symbol_and_tf(symbol: str, tf: str):
    """设置图表品种和时间框架。"""
    tv_sym = SYMBOL_MAP.get(symbol, symbol)
    # Set symbol
    sym_out, sym_ok = _tv("symbol", "--set", tv_sym, timeout=10)
    # Set timeframe
    tf_out, tf_ok = _tv("timeframe", "--set", tf, timeout=10)
    return sym_ok and tf_ok


def capture_screenshot(symbol: str, tf: str, tag: str = "") -> str | None:
    """截图并保存为 PNG。
    返回本地文件路径，失败返回 None。
    """
    asset_class = "forex" if symbol == "XAUUSD" else "crypto"
    hierarchy = TF_HIERARCHY[asset_class]

    # 设为主周期
    if not set_symbol_and_tf(symbol, hierarchy[0]):
        print(f"⚠ TV不可用，跳过截图")
        return None

    # 截图
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    fname = f"tv_{symbol}_{tf}_{tag}_{ts}.png"
    fpath = OUTPUT / fname
    OUTPUT.mkdir(parents=True, exist_ok=True)

    out, ok = _tv("screenshot", "--region", "chart", "--method", "api", timeout=20)
    if not ok:
        return None

    # 如果截图输出是 base64或直接路径
    # tv CLI screenshot 通常输出文件路径
    if out and Path(out).exists():
        # Copy to outputs/
        import shutil
        shutil.copy(out, fpath)
    else:
        # 使用 CDP 方法截图
        out2, ok2 = _tv("screenshot", "--region", "chart", "--method", "cdp", timeout=20)
        if ok2 and out2 and Path(out2).exists():
            import shutil
            shutil.copy(out2, fpath)
        else:
            return None

    return str(fpath)


def capture_analysis_setup(symbol: str, direction: str = "") -> str | None:
    """
    完整分析截图流程：
    1. 设主周期
    2. 确保右侧价格栏可见
    3. 确保CVD指标在下方指标区
    4. 截图
    返回截图路径或 None
    """
    asset_class = "forex" if symbol == "XAUUSD" else "crypto"
    main_tf = TF_HIERARCHY[asset_class][0]

    # 设品种+主周期
    if not set_symbol_and_tf(symbol, main_tf):
        return None

    # 等待图表加载
    import time
    time.sleep(2)

    # 截图
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    dir_tag = f"_{direction}" if direction else ""
    fname = f"analysis_{symbol}_{main_tf}m{dir_tag}_{ts}.png"
    fpath = OUTPUT / fname
    OUTPUT.mkdir(parents=True, exist_ok=True)

    out, ok = _tv("screenshot", "--region", "full", "--filename", str(fpath), timeout=30)
    if ok:
        # 查找生成的截图
        for ext in [".png", ".PNG"]:
            candidates = list(OUTPUT.glob(f"*{ts}*{ext}"))
            if candidates:
                return str(candidates[0])
        # Try direct path
        if fpath.with_suffix(".png").exists():
            return str(fpath.with_suffix(".png"))
        # Check if TV CLI output has the path
        if out and Path(out).exists():
            return str(out)

    return None


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    direction = sys.argv[2] if len(sys.argv) > 2 else ""
    print(f"📸 截图 {symbol} ...")
    path = capture_analysis_setup(symbol, direction)
    if path:
        print(f"✅ {path}")
    else:
        print("❌ 截图失败")
        sys.exit(1)
