#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 BTC 关键位实时守卫 — WebSocket 价格流，穿越即触发分析推送。

真实时：订阅 Binance 合约 aggTrade 流（每笔聚合成交→价格），价格自上次以来
**穿过 79,633 或 78,400** 任一方向 → 立即写触发标志，由 agent 做完整分析并推 386。
比 cron 分钟级轮询快得多（毫秒级），且不受 cron 最小间隔限制。

触发信令：写 data/btc_keylevel_trigger.json（含已触发位/方向/时间/冷却截止）。
防刷屏：每触发位独立 30 分钟冷却。
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import atomic_write_json

try:
    import websockets
except ImportError:
    print("websockets not installed", flush=True)
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
TRIGGER_FILE = DATA_DIR / "btc_keylevel_trigger.json"
STATE_FILE = DATA_DIR / ".btc_keylevel_ws_state.json"
HEARTBEAT_FILE = DATA_DIR / ".btc_keylevel_ws_heartbeat.json"

SYM = "btcusdt"
WS_URL = "wss://fstream.binance.com/ws/btcusdt@aggTrade"

# 关键位：穿越检测
LEVELS = {
    "反抽位79633": 79633.0,
    "买回位78400": 78400.0,
}
COOLDOWN_SECONDS = 1800   # 每触发位独立冷却 30 分钟
POLL_WS = 8               # 间隔秒数（每次重连，且每次读最新价做穿越判断），实际为事件驱动


def ts():
    return time.time()


def now_bjt_iso():
    from datetime import datetime, timezone, timedelta
    return datetime.now(tz=timezone(timedelta(hours=8))).isoformat()


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"last_price": None, "triggered": {}}


def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, ensure_ascii=False)


def split_trigger(name, price, direction):
    """把触发写入 TRIGGER_FILE，供 agent 读取。自动更新冷却。"""
    data = None
    try:
        with open(TRIGGER_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["triggered"] = True
    data["zone"] = name
    data["zone_price"] = LEVELS[name]
    data["price"] = price
    data["direction"] = direction
    data["ts"] = now_bjt_iso()
    data["cooldown_until"] = ts() + COOLDOWN_SECONDS
    TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(TRIGGER_FILE, data)


def heartbeat(status):
    hb = {"ts": now_bjt_iso(), "pid": os.getpid(), "status": status,
          "last_price": _GLOBAL.get("last_price")}
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(HEARTBEAT_FILE, hb, indent=None)


_GLOBAL = {"last_price": None}


async def main_loop():
    state = load_state()
    last_price = state.get("last_price")
    triggered = state.get("triggered", {})   # {name: {"dir":..., "cool_until":...}}

    log(f"BTC keylevel WS guard started PID={os.getpid()}")
    heartbeat("running")

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                log("WS connected")
                heartbeat("connected")
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue
                    price = float(data.get("p"))
                    _GLOBAL["last_price"] = price

                    for name, lvl in LEVELS.items():
                        crossed = None
                        if last_price is not None:
                            if last_price < lvl <= price:
                                crossed = "up"
                            elif last_price >= lvl > price:
                                crossed = "down"
                        if crossed:
                            now = ts()
                            info = triggered.get(name, {})
                            cool_until = info.get("cool_until", 0.0)
                            # 冷却内且方向相同 → 跳过；否则触发
                            if now >= cool_until or info.get("dir") != crossed:
                                log(f"TRIGGER {name} {crossed} price={price:,.0f}")
                                split_trigger(name, price, crossed)
                                triggered[name] = {"dir": crossed, "cool_until": now + COOLDOWN_SECONDS}
                                save_state({"last_price": price, "triggered": triggered, "_ts": ts()})
                    last_price = price
                    save_state({"last_price": price, "triggered": triggered, "_ts": ts()})
                    heartbeat("connected")
        except asyncio.TimeoutError:
            log("WS recv timeout, reconnecting")
        except Exception as e:
            log(f"WS error: {e} — reconnect in {POLL_WS}s")
            heartbeat("reconnecting")
            await asyncio.sleep(POLL_WS)
        await asyncio.sleep(1)


def log(m):
    safe = m.encode("ascii", "replace").decode("ascii")
    print(safe, flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        log("Shutdown")
