#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XAU TV MCP 现场同步 v1.0 — 读 OANDA:XAUUSD 五层真实结构写 data/xau_tv_state.json

解决 v9.6 地图 P0：XAU 占位推算虚挂。本脚本通过 TradingView MCP 现场切
5/15/1h/4h 读真实 high/low/close/OHLCV，auto_card.py 优先用此真实数据覆盖占位。

用法: python scripts/xau_tv_sync.py
依赖: tools/tradingview-mcp (TV MCP CDP 已启动)
降级: TV MCP 不可用则静默退出(不写文件，auto_card 走占位并标注⚠️)
"""
import sys
import json
import asyncio
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
OUT = ROOT / "data" / "xau_tv_state.json"
SYMBOL = "OANDA:XAUUSD"
TIMEFRAMES = ["5m", "15m", "1h", "4h"]

# TV MCP 连接依赖（与 fetch_tv_mcp.py 一致）
hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
if hermes_venv.exists():
    sys.path.insert(0, str(hermes_venv))


async def _run():
    # 端口探测前置：TV Desktop CDP(9222)未开则静默退出，避免启动 node 超时/异常
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", 9222)) != 0:
                print("⚠ TV Desktop(9222)未运行，XAU同步跳过")
                return 0
    except Exception:
        return 0
    try:
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from fetch_tv_mcp import (
            call_tool, set_symbol, set_timeframe,
            get_chart_state, get_ohlcv, parse_result,
        )
    except Exception as e:
        print(f"⚠ TV MCP 模块不可用: {e}", file=sys.stderr)
        return 1

    server_script = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    if not server_script.exists():
        print(f"⚠ TV MCP server 未找到: {server_script}", file=sys.stderr)
        return 1

    server_params = StdioServerParameters(command="node", args=[str(server_script)])
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            # 切到 XAU
            await set_symbol(session, SYMBOL)
            await asyncio.sleep(2)

            result = {"symbol": SYMBOL, "updated_at": datetime.now(TZ).isoformat(), "timeframes": {}}
            for tf in TIMEFRAMES:
                await set_timeframe(session, tf)
                await asyncio.sleep(3)
                state = await get_chart_state(session)
                ohlcv = await get_ohlcv(session)
                st = parse_result(state)
                ov = parse_result(ohlcv)
                tf_data = _parse_ohlcv(ov, st)
                if tf_data:
                    result["timeframes"][tf] = tf_data
                    print(f"  ✅ {tf}: H{tf_data['high']:.1f} L{tf_data['low']:.1f} C{tf_data['close']:.1f}")
                else:
                    print(f"  ⚠ {tf}: 解析失败", file=sys.stderr)

            OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✅ XAU TV状态已写 {OUT}")
            # v9.8: 推 TG 五层关键位表
            try:
                now = datetime.now(TZ)
                ts = now.strftime("%Y年%m月%d日%H：%M")
                tfs = result.get("timeframes", {})
                if tfs:
                    lines = [f"🥇 XAU TV五层现场 · {ts}"]
                    lines.append("")
                    lines.append("| 周期 | 高 | 低 | 收 | 振幅 |")
                    lines.append("|:----|:----:|:----:|:----:|:----:|")
                    for tf in ["5m", "15m", "1h", "4h"]:
                        d = tfs.get(tf)
                        if d:
                            rng = (d["high"] - d["low"]) / d["low"] * 100 if d.get("low") else 0
                            lines.append(f"| {tf} | `{d['high']:.1f}` | `{d['low']:.1f}` | `{d['close']:.1f}` | {rng:.2f}% |")
                    # 决策：4h收盘相对区间位置
                    h4 = tfs.get("4h")
                    if h4:
                        pos = (h4["close"] - h4["low"]) / (h4["high"] - h4["low"]) * 100 if h4["high"] != h4["low"] else 50
                        zone = "高位" if pos > 66 else "低位" if pos < 33 else "中位"
                        lines.append("")
                        lines.append(f"4h位置: 区间{zone}({pos:.0f}%) → {'🟢偏多但防回落' if pos>66 else '🔴偏空但防反弹' if pos<33 else '⚪方向待选'}")
                        lines.append("")
                        lines.append(f"**总体结论**: XAU五层区间**{zone}**，**{'🟢偏多但防回落' if pos>66 else '🔴偏空但防反弹' if pos<33 else '⚪方向待选'}**。")
                    else:
                        lines.append("")
                        lines.append("**总体结论**: XAU五层数据不足，方向待选。")
                    output = "\n".join(lines)
                    print(output)
                    sys.path.insert(0, str(Path(__file__).resolve().parent))
                    from telegram_reliable import push_tg_rich
                    push_tg_rich("telegram:-1003733144325:846", output)
            except Exception as _te:
                print(f"⚠ XAU TV RichMarkdown推送失败: {_te}", file=sys.stderr)
            return 0


def _parse_ohlcv(ohlcv_text: str, state_text: str) -> dict | None:
    """从 TV MCP OHLCV/state 文本提取最新K线 high/low/close/open。"""
    import re
    # 尝试 OHLCV 文本中的数字行: [time, open, high, low, close, volume]
    nums = re.findall(r"-?\d+\.?\d*", ohlcv_text)
    # 取末尾一组 4-6 个数字 (high/low/close/open 附近)
    if len(nums) >= 4:
        try:
            floats = [float(x) for x in nums[-6:]]
            # 假设顺序 open high low close ... 取合理区间
            candidates = [f for f in floats if 1000 < f < 5000]  # XAU 价格区间
            if len(candidates) >= 3:
                return {
                    "open": candidates[0],
                    "high": max(candidates),
                    "low": min(candidates),
                    "close": candidates[-1],
                    "change_pct": 0,
                }
        except Exception:
            pass
    return None


if __name__ == "__main__":
    # v9.6 三级降级：TV CDP 偶断不得直接 exit 1 让 cron 报错。
    # 失败则保留旧 xau_tv_state.json（若 15min 内）或写降级标记，cron 仍 ok。
    try:
        rc = asyncio.run(_run())
        raise SystemExit(rc if isinstance(rc, int) else 0)
    except Exception as e:
        import json as _json
        import time as _t
        # 若旧文件 15min 内，保留旧数据不覆盖
        if OUT.exists():
            try:
                age = (time.time() - OUT.stat().st_mtime)
                if age < 900:
                    print(f"⚠ XAU TV同步失败({e})，保留 {age:.0f}s 前旧数据")
                    raise SystemExit(0)
            except Exception:
                pass
        # 无可用旧数据 → 写降级占位，标 stale
        try:
            _json.dump({"symbol": "OANDA:XAUUSD", "stale": True,
                        "error": str(e)[:200],
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                       OUT.open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"⚠ XAU TV同步失败({e})，写降级占位")
        except Exception:
            pass
        raise SystemExit(0)
