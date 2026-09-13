#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TV Desktop 保活看门狗 v1.0 — 可复用支持脚本（棠溪审计 skill 附带）。

职责：
1) 探测 9222 端口（TV Desktop CDP）。
2) 已开 → 静默退出（不刷屏）。
3) 未开 → 尝试调 launch 脚本拉起 TV（带 --remote-debugging-port=9222）。
4) 拉起失败（环境无 GUI session / 拒绝访问 / 路径缺失）→ 静默退出，
   依赖下游脚本的 REST 降级，绝不报错刷屏。

设计原则：本看门狗只负责"尝试保活"，不负责"判定健康"。
下游管线（BTC关键位/XAU同步/作战室）各有 9222 探测 + REST 降级，
TV 关时优雅降级，因此本看门狗失败也无需告警轰炸。

挂载方式（hermes cron）：
  hermes cron create "*/10 * * * *" --name "TV Desktop保活" \
    --script scripts/tv_keepalive.py --no-agent --deliver local \
    --workdir "D:/Hermes agent"

审计铁律：TV 关着时作战室融合报告的周期一致性会显示 [REST] 而非 [TV]，
属正常降级，不要误判为 bug。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = "D:/Hermes agent"
PORT = 9222
LAUNCH_BAT = os.path.join(ROOT, "tools", "tradingview-mcp", "scripts", "launch_tv_debug.bat")
# 双路径闭环：%LOCALAPPDATA%\TradingView 是 MCP/launch 的实际启动位，
# 需与 Store(WindowsApps) 版本保持同步（见 tv_sync_appdir.py）。
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TV_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\TradingView\TradingView.exe"),
    r"C:\Program Files\TradingView\TradingView.exe",
    r"C:\Program Files (x86)\TradingView\TradingView.exe",
]
STATE_FILE = os.path.join(ROOT, "data", "tv_keepalive_state.json")
COOLDOWN_SEC = 1800  # 30分钟：拉起失败后冷却期，避免每10分无脑重试刷错误


def port_open(host: str = "127.0.0.1", port: int = PORT) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def load_state() -> dict:
    try:
        import json
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        import json
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def try_launch() -> bool:
    """尝试拉起 TV Desktop。成功返回 True，失败返回 False（静默）。"""
    # 0) 双路径闭环：Store 自动更新只动 WindowsApps，本地启动目录会落后。
    #    仅在版本确实落后（或无本地副本）时才清场并同步；已一致时零副作用。
    try:
        from tv_sync_appdir import sync_if_needed
        res = sync_if_needed(kill=True)
        if res.get("status") == "synced":
            print(f"⬆ TV 启动目录已同步到 Store 版 {res.get('store_version')}", flush=True)
    except Exception:
        pass  # 同步模块不可用不阻塞启动，按原流程继续

    if os.path.exists(LAUNCH_BAT):
        try:
            subprocess.Popen(
                ["cmd", "/c", LAUNCH_BAT, str(PORT)],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            # 给 launch 脚本等待时间：它内部可能还要跑 Store 版本同步（数百 MB，
            # 首次同步可达 1 分钟）+ TV 冷启动，故给足 90 秒上限。
            for _ in range(45):
                time.sleep(2)
                if port_open():
                    return True
            return False
        except Exception:
            return False
    tv_exe = next((p for p in TV_CANDIDATES if os.path.exists(p)), None)
    if not tv_exe:
        return False
    try:
        subprocess.Popen(
            [tv_exe, f"--remote-debugging-port={PORT}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(8):
            time.sleep(2)
            if port_open():
                return True
        return False
    except Exception:
        return False


def main() -> int:
    if port_open():
        st = load_state()
        if st.get("last_fail"):
            save_state({"last_fail": 0, "last_ok": time.time()})
        return 0

    st = load_state()
    last_fail = float(st.get("last_fail", 0) or 0)
    if time.time() - last_fail < COOLDOWN_SEC:
        return 0

    ok = try_launch()
    if ok:
        save_state({"last_fail": 0, "last_ok": time.time()})
        return 0
    else:
        save_state({"last_fail": time.time(), "last_ok": 0})
        return 0


if __name__ == "__main__":
    sys.exit(main())
