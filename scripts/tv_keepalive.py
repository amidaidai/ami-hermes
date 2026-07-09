#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TV Desktop 保活看门狗 v1.0 — 每10分 cron。

职责：
1) 探测 9222 端口（TV Desktop CDP）。
2) 已开 → 静默退出（不刷屏）。
3) 未开 → 尝试调 launch 脚本拉起 TV（带 --remote-debugging-port=9222）。
4) 拉起失败（环境无 GUI session / 拒绝访问 / 路径缺失）→ 静默退出，
   依赖下游脚本的 REST 降级，绝不报错刷屏。

设计原则：本看门狗只负责"尝试保活"，不负责"判定健康"。
下游管线（BTC关键位/XAU同步/作战室）各有 9222 探测 + REST 降级，
TV 关时优雅降级，因此本看门狗失败也无需告警轰炸。
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
# 直接探测路径（与 launch 脚本一致，优先本机常见安装位）
TV_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\TradingView\TradingView.exe"),
    r"C:\Program Files\TradingView\TradingView.exe",
    r"C:\Program Files (x86)\TradingView\TradingView.exe",
]
STATE_FILE = os.path.join(ROOT, "data", "tv_keepalive_state.json")
# 拉起失败后冷却期：避免每10分无脑重试刷错误日志
COOLDOWN_SEC = 1800  # 30分钟


def log(msg: str) -> None:
    # 仅在真实动作时输出（拉起成功/失败原因），正常静默
    print(msg, flush=True)


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
    # 优先用官方 launch 脚本（自动探测路径 + 等待 CDP）
    if os.path.exists(LAUNCH_BAT):
        try:
            subprocess.Popen(
                ["cmd", "/c", LAUNCH_BAT, str(PORT)],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            # 给 launch 脚本等待时间（它内部会等 CDP 就绪，最多约15s）
            for _ in range(10):
                time.sleep(2)
                if port_open():
                    return True
            return False
        except Exception:
            return False
    # 回退：直接拼路径启动
    tv_exe = next((p for p in TV_CANDIDATES if os.path.exists(p)), None)
    if not tv_exe:
        return False
    # 关键修复：清掉 ELECTRON_RUN_AS_NODE 等 env 污染。
    # Hermes 终端默认带 ELECTRON_RUN_AS_NODE=1，会让 TV Desktop(Electron)
    # 以 node 模式启动并拒绝 Chromium flag ("bad option: --remote-debugging-port")。
    # 必须清掉该 env 才能正常带 CDP 端口启动。
    child_env = os.environ.copy()
    child_env.pop("ELECTRON_RUN_AS_NODE", None)
    child_env.pop("ELECTRON_DISABLE_SANDBOX", None)
    try:
        subprocess.Popen(
            [tv_exe, f"--remote-debugging-port={PORT}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=child_env,
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
        # 已开 → 静默（清掉失败冷却标记）
        st = load_state()
        if st.get("last_fail"):
            save_state({"last_fail": 0, "last_ok": time.time()})
        return 0

    # 未开 → 检查冷却
    st = load_state()
    last_fail = float(st.get("last_fail", 0) or 0)
    if time.time() - last_fail < COOLDOWN_SEC:
        # 冷却期内不重试，避免刷错误（依赖下游 REST 降级）
        return 0

    # 尝试拉起
    ok = try_launch()
    if ok:
        log(f"✅ TV Desktop 已自动拉起 (9222)")
        save_state({"last_fail": 0, "last_ok": time.time()})
        return 0
    else:
        # 拉起失败（环境无 GUI session / 拒绝访问）→ 静默降级，记冷却
        save_state({"last_fail": time.time(), "last_ok": 0})
        return 0


if __name__ == "__main__":
    sys.exit(main())
