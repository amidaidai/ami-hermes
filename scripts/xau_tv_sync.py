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
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
OUT = ROOT / "data" / "xau_tv_state.json"
SYMBOL = "OANDA:XAUUSD"
# v9.7: 补 D 层日线，使"自上而下确认"有大背景（原只同步 5m/15m/1h/4h）
TIMEFRAMES = [("1D", "D"), ("5m", "5"), ("15m", "15"), ("1h", "60"), ("4h", "240")]
SOURCE_SNAPSHOT = ROOT / "data" / "source_snapshot_XAUUSD.json"


def _refresh_source_snapshot_if_stale(max_age_seconds: int = 1800) -> None:
    """Keep XAU's multi-source quality snapshot inside the 30-minute freshness gate."""
    try:
        if SOURCE_SNAPSHOT.exists() and time.time() - SOURCE_SNAPSHOT.stat().st_mtime <= max_age_seconds:
            return
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from trading_system import source_snapshot
        source_snapshot("XAUUSD")
    except Exception as exc:
        print(f"⚠ XAU多源快照刷新失败: {exc}", file=sys.stderr)


async def _run_with_retry(max_attempts: int = 3) -> int:
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            rc = await _run()
            if rc == 0:
                return 0
        except Exception as exc:
            last_exc = exc
            print(f"⚠ XAU TV同步尝试 {attempt}/{max_attempts} 失败: {exc}", file=sys.stderr)
        if attempt < max_attempts:
            time.sleep(5)
    if last_exc:
        raise last_exc
    return 1


def _refresh_tv_live_cache() -> None:
    """同步XAU OHLCV后刷新同品种Data Window缓存，避免两条TV权威链分裂。"""
    cmd = [sys.executable, str(ROOT / "scripts" / "tv_live_dump.py"),
           "--symbol", SYMBOL, "--verbose"]
    result = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "tv_live_dump failed")[:200])
    if result.stdout.strip():
        print(result.stdout.strip())

# TV MCP 连接依赖
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
            for tf, resolution in TIMEFRAMES:
                await set_timeframe(session, resolution)
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
            # 缓存权威读取固定在XAU主执行周期5m。
            await set_timeframe(session, "5")
            await asyncio.sleep(3)
            _refresh_source_snapshot_if_stale()
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
                    for tf in ["1D", "4h", "1h", "15m", "5m"]:
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
                    if os.environ.get("XAU_TV_NO_PUSH") != "1":
                        sys.path.insert(0, str(Path(__file__).resolve().parent))
                        from telegram_reliable import push_tg_rich
                        push_tg_rich("telegram:-1003733144325:846", output)
            except Exception as _te:
                print(f"⚠ XAU TV RichMarkdown推送失败: {_te}", file=sys.stderr)
            return 0


def _parse_ohlcv(ohlcv_text: str, state_text: str) -> dict | None:
    """优先解析TV MCP结构化OHLCV，并只消费倒数第二根已闭合K线。"""
    try:
        payload = json.loads(ohlcv_text)
        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            payload = json.loads(payload["result"])
        bars = payload.get("last_5_bars") if isinstance(payload, dict) else None
        if isinstance(bars, list) and bars:
            bar = bars[-2] if len(bars) >= 2 else bars[-1]
            o = float(bar["open"])
            h = float(bar["high"])
            l = float(bar["low"])
            c = float(bar["close"])
            if 1000 < l <= h < 10000 and l <= min(o, c) <= max(o, c) <= h:
                return {
                    "open": o, "high": h, "low": l, "close": c,
                    "change_pct": (c - o) / o * 100 if o else 0.0,
                }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return None


def main() -> int:
    """Run the TV sync with a cron-safe three-level degradation path."""
    try:
        rc = asyncio.run(_run_with_retry())
        if isinstance(rc, int) and rc != 0:
            raise RuntimeError(f"同步返回非零状态 {rc}")
        _refresh_tv_live_cache()
        return 0
    except Exception as e:
        # 若旧文件30分钟内，保留旧数据，不让单次CDP抖动破坏有效缓存。
        if OUT.exists():
            try:
                age = time.time() - OUT.stat().st_mtime
                if age < 1800:
                    print(f"⚠ XAU TV同步失败({e})，保留 {age:.0f}s 前旧数据")
                    return 0
            except OSError:
                pass
        # 无可用旧数据时落盘明确stale，严禁伪装成现场数据。
        try:
            payload = {
                "symbol": SYMBOL,
                "stale": True,
                "error": str(e)[:200],
                "updated_at": datetime.now(TZ).isoformat(),
            }
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"⚠ XAU TV同步失败({e})，写降级占位")
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
