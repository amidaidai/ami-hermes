#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · TradingView 主周期图表截图 v2.0

提供 capture_analysis_setup(symbol, direction) —— 连接 TV MCP，切到
「主周期」图表（加密 15m / 贵金属 5m），抓一张图返回本地路径。
失败返回 None（调用方降级为纯文字卡片，不阻塞推送）。

符号映射：
  BTCUSDT -> BINANCE:BTCUSDT.P   (主周期 15m)
  XAUUSD  -> OANDA:XAUUSD        (主周期 5m)
周期代码走 TV MCP：chart_set_timeframe 接受 "5"/"15"/"D" 等。
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
HERMES_VENV = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
SCREENSHOT_DIR = Path("D:/Hermes agent/tools/tradingview-mcp/screenshots")
SERVER_SCRIPT = Path("D:/Hermes agent/tools/tradingview-mcp/src/server.js")

SYMBOL_MAP = {
    "BTCUSDT": ("BINANCE:BTCUSDT.P", "15", "15m"),
    "XAUUSD": ("OANDA:XAUUSD", "5", "5m"),
    "AAPL": ("NASDAQ:AAPL", "60", "1h"),
    "TSLA": ("NASDAQ:TSLA", "60", "1h"),
    "NVDA": ("NASDAQ:NVDA", "60", "1h"),
    "MSFT": ("NASDAQ:MSFT", "60", "1h"),
    "EURUSD": ("OANDA:EURUSD", "15", "15m"),
    "GBPUSD": ("OANDA:GBPUSD", "15", "15m"),
    "USDJPY": ("OANDA:USDJPY", "15", "15m"),
    "ES": ("CME_MINI:ES1!", "15", "15m"),
    "NQ": ("CME_MINI:NQ1!", "15", "15m"),
    "CL": ("NYMEX:CL1!", "15", "15m"),
}
DEFAULT_TF = ("15", "15m")
INDICATOR_RECALC_SECONDS = 20


def _tool_json(result) -> dict:
    texts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if text:
            texts.append(str(text))
    raw = "\n".join(texts)
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            payload = json.loads(payload["result"])
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def chart_state_is_ready(state: dict, symbol: str, timeframe: str) -> bool:
    actual_symbol = str(state.get("symbol") or state.get("ticker") or "").upper()
    actual_tf = str(state.get("resolution") or state.get("timeframe") or "").upper()
    expected_tf = {"5": "5M", "15": "15M", "60": "1H", "240": "4H", "D": "1D"}.get(timeframe, timeframe).upper()
    studies = state.get("studies") or []
    names = [str(row.get("name") if isinstance(row, dict) else row) for row in studies]
    return (
        actual_symbol == symbol.upper()
        and actual_tf in {timeframe.upper(), expected_tf}
        and any("SVP" in name for name in names)
        and any("Volume Aggregated" in name for name in names)
    )


def _sym_tf(symbol: str):
    s = (symbol or "BTCUSDT").upper().replace(".P", "")
    if s in SYMBOL_MAP:
        return SYMBOL_MAP[s]
    if s.endswith("USDT"):
        return ("BINANCE:" + s + ".P", "15", "15m")
    if len(s) == 6 and s.endswith("USD"):
        return ("OANDA:" + s, "15", "15m")
    return (s, "15", "15m")


async def _capture(symbol: str, *, reuse_verified: bool = False) -> str | None:
    if not SERVER_SCRIPT.exists():
        print(f"[tv_screenshot] TV MCP server 未找到: {SERVER_SCRIPT}", file=sys.stderr)
        return None
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for p in (str(HERMES_VENV),):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession

    tv_sym, tf_code, tf_label = _sym_tf(symbol)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    out_path = SCREENSHOT_DIR / f"{symbol.replace('/', '_')}_{tf_label}_{stamp}.png"

    server_params = StdioServerParameters(command="node", args=[str(SERVER_SCRIPT)])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tv_data_bridge import tv_collection_lock
    with tv_collection_lock(timeout=60):
      async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            try:
                state = _tool_json(await session.call_tool("chart_get_state", {}))
                ready = reuse_verified and chart_state_is_ready(state, tv_sym, tf_code)
                if not ready:
                    await session.call_tool("chart_set_symbol", {"symbol": tv_sym})
                    await session.call_tool("chart_set_timeframe", {"timeframe": tf_code})
                    await asyncio.sleep(INDICATOR_RECALC_SECONDS)
                    state = _tool_json(await session.call_tool("chart_get_state", {}))
                    if not chart_state_is_ready(state, tv_sym, tf_code):
                        print("[tv_screenshot] 图表身份/周期/studies重算校验失败", file=sys.stderr)
                        return None
            except Exception as e:
                print(f"[tv_screenshot] 图表准备失败: {e}", file=sys.stderr)
                return None
            # 截图（chart 区域）
            try:
                res = await session.call_tool("capture_screenshot", {"region": "full"})
            except Exception as e:
                print(f"[tv_screenshot] capture 失败: {e}", file=sys.stderr)
                return None
            # 解析返回路径
            raw = ""
            try:
                texts = []
                if hasattr(res, "content"):
                    for item in res.content:
                        if hasattr(item, "text"):
                            texts.append(item.text)
                        elif isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                raw = "\n".join(texts)
                sd = json.loads(raw)
                src = sd.get("file_path") or sd.get("path") or sd.get("filepath") or sd.get("screenshot")
                if not src or not Path(src).exists():
                    print(f"[tv_screenshot] 截图路径无效: {src}", file=sys.stderr)
                    return None
                # 复制到带品种+周期标记的确定路径（避免覆盖/重名问题）
                Path(src).replace(out_path)
                print(f"[tv_screenshot] 截图完成: {out_path}", file=sys.stderr)
                return str(out_path)
            except Exception as e:
                print(f"[tv_screenshot] 解析截图返回失败: {e} | raw={raw[:200]}", file=sys.stderr)
                return None


def capture_analysis_setup(
    symbol: str,
    direction: str | None = None,
    *,
    reuse_verified: bool = True,
) -> str | None:
    """同步入口：用 hermes venv 的 python 3.11 子进程抓主周期图表。

    hermes venv 内的 mcp / pydantic_core 是 cp311 编译，必须用 venv 自带的
    python 运行，否则在 3.12 主进程里 import 会因 ABI 不匹配报错
    （No module named 'pydantic_core._pydantic_core'）。走子进程隔离最稳。
    """
    venv_py = HERMES_VENV.parent.parent / "Scripts" / "python.exe"
    if not venv_py.exists():
        # 回退：尝试当前解释器直接跑（同 ABI 时可用）
        try:
            return asyncio.run(_capture(symbol, reuse_verified=reuse_verified))
        except Exception as e:
            print(f"[tv_screenshot] 子进程 python 缺失且直跑失败: {e}", file=sys.stderr)
            return None
    try:
        # 清理可能继承自父进程的 PYTHONPATH/PYTHONHOME，避免把 3.12 的
        # 路径塞进 venv 的 3.11 解释器，导致 pydantic_core ABI 不匹配。
        clean_env = {k: v for k, v in os.environ.items()
                     if k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
        r = subprocess.run(
            [str(venv_py), __file__, symbol, *( ["--reuse-verified"] if reuse_verified else [] )],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
            env=clean_env,
        )
        if r.returncode != 0:
            print(f"[tv_screenshot] 子进程失败({r.returncode}): {r.stderr[-500:]}", file=sys.stderr)
            return None
        out = r.stdout.strip().splitlines()
        path = out[-1].strip() if out else ""
        if path and Path(path).exists():
            return path
        print(f"[tv_screenshot] 子进程无有效路径 rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr[:500]!r}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[tv_screenshot] 子进程异常: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    # 注意：直接运行时走 async worker，不要调 capture_analysis_setup
    # （那是给外部主进程用的子进程封装，会再 spawn 自身造成递归）。
    try:
        print(asyncio.run(_capture(sym, reuse_verified="--reuse-verified" in sys.argv)) or "")
    except Exception as e:
        print(f"[tv_screenshot] 异常: {e}", file=sys.stderr)
