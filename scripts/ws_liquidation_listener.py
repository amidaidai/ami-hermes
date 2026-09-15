#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Binance USDT-M 强平流采集器（`!forceOrder@arr`，免 key）—— 清算第三源。

为什么存在
----------
币安 REST 强平接口（`/fapi/v1/allForceOrders`）已下线、Bybit `/v5/market/liquidation`
返 404（2026-09-15 实测），逐笔强平只剩交易所 WS 流可用。OKX 公共接口已覆盖
OKX 本所（`liquidation_flow.py`）；本采集器补上**币安本所**的强平流 —— 用户的
主战场就在币安，单看 OKX 会把「币安这波被扫了多少」漏掉。

订阅与字段（2026-09-15 实测，含两条**路径/口径**教训）
----------------------------------------------------
- **路径已变更**：官方文档现为 `wss://fstream.binance.com/market/ws/!forceOrder@arr`
  （多了 `/market/` 段）。旧路径 `wss://fstream.binance.com/ws/!forceOrder@arr` 仍能
  握手成功但**永不推送** —— 静默空转，就是本脚本此前长期收不到数据的真因。
- **它是「快照采样」不是全量逐笔**：官方变更日志（2021-04-27）写明该流"不再推送实时
  订单数据，改为最多 1 条/秒的快照"。实测 30 秒全市场仅 3 条（MRNAUSDT、龙虾USDT…）。
  因此**不得用于强平规模统计**（会严重低估），只能作「币安侧最近发生过强平」的存在性
  提示；规模口径以 OKX 逐笔（`liquidation_flow.py`）为准。
- 推送体：`{"e":"forceOrder","E":ms,"o":{"s":"BTCUSDT","S":"SELL","p":..,"q":..,"ap":..,"X":"FILLED"}}`
- `S=SELL` = 多单被强平；`S=BUY` = 空单被强平（记的是**被强平方**）
- 名义 = `qty × ap`（币本位合约，币数 × 均成交价，直接是 USD 量级）

输出（供卡面只读，不在渲染路径打网络）
--------------------------------------
- `data/liquidation_ws.json`：滚动 24h 事件窗，含 `updated_epoch`（数据新鲜度看门狗只认
  这个字段名，`fetched_at` 不在 `source_health.TIMESTAMP_KEYS` 里）
- `data/.liquidation_ws_heartbeat.json`：进程活性心跳（看门狗据此判活/重启）

设计约束
--------
- 常驻进程：`python scripts/ws_liquidation_listener.py`；由 cron `清算WS采集保活`
  （`liquidation_ws_watchdog.py`）守护，心跳陈旧即杀旧重启。
- `--duration N`：采 N 秒后正常退出（自检/单测用，不写常驻状态）。
- 断连自动重连；断连期间**不伪造新鲜度** —— `updated_epoch` 停更，看门狗会看到陈旧。
- 仅用于人工分析，不接自动下单。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import websockets

WS_URL = "wss://fstream.binance.com/market/ws/!forceOrder@arr"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "liquidation_ws.json"
HEARTBEAT = DATA / ".liquidation_ws_heartbeat.json"

SYMBOLS = ("BTCUSDT", "ETHUSDT")      # 与 OKX 侧覆盖对齐（BTC/ETH）
WINDOW_S = 24 * 3600                  # 滚动事件窗
CACHE_FLUSH_S = 5                     # 事件触发的落盘节流
STAMP_REFRESH_S = 60                  # 无事件时也刷 updated_epoch（活性≠有新事件）
RECONNECT_DELAY = 5
PING_INTERVAL = 30
TZ = timezone(timedelta(hours=8))


def _coin(symbol: str) -> str:
    """`BTCUSDT` → `BTC`（只留已知品种，其它返回空串）。"""
    su = str(symbol or "").upper()
    for base in ("BTC", "ETH", "SOL", "XRP", "BNB"):
        if su == f"{base}USDT":
            return base
    return ""


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse_message(msg) -> list | None:
    """WS 推送 → `[ts_ms, side, price, qty, coin]`；非目标品种/异常返回 None。

    `side` 是**被强平的方向**：`S=SELL` 说明多头持仓被卖出强平。
    """
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode("utf-8", "replace")
    try:
        data = json.loads(msg)
    except (TypeError, ValueError):
        return None
    if data.get("e") != "forceOrder":
        return None
    o = data.get("o") or {}
    coin = _coin(o.get("s"))
    if not coin:
        return None
    try:
        ts = int(data.get("E") or o.get("T") or 0)
        side = "long" if str(o.get("S")).upper() == "SELL" else "short"
        price = float(o.get("ap") or o.get("p") or 0)
        qty = float(o.get("q") or 0)
    except (TypeError, ValueError):
        return None
    if ts <= 0 or price <= 0 or qty <= 0:
        return None
    return [ts, side, round(price, 6), round(qty, 10), coin]


class LiquidationCollector:
    def __init__(self, duration: int | None = None, jsonl_out: str | None = None):
        self.running = True
        self.duration = duration
        self.jsonl_out = Path(jsonl_out) if jsonl_out else None
        self.events: dict[str, list[list]] = {c: [] for c in (_coin(s) for s in SYMBOLS)}
        self.total = 0
        self.connected = False
        self.ws = None
        self._last_flush = 0.0
        self._last_stamp = 0.0

    # ── 状态落盘 ────────────────────────────────────────────────────────────
    def _prune(self, now_ms: int) -> None:
        floor = now_ms - WINDOW_S * 1000
        for coin, rows in self.events.items():
            self.events[coin] = [r for r in rows if int(r[0]) >= floor]

    def flush(self, *, force: bool = False, status: str | None = None) -> None:
        now_ms = int(time.time() * 1000)
        self._prune(now_ms)
        record = {
            "source": "binance_ws",
            "updated_epoch": int(now_ms / 1000),
            "status": status or ("live" if self.connected else "stale_cache"),
            "error": None if self.connected else "websocket disconnected",
            "coins": {
                coin: {
                    "events": rows,
                    "coverage_from": int(rows[0][0]) if rows else 0,
                    "coverage_to": int(rows[-1][0]) if rows else 0,
                }
                for coin, rows in self.events.items()
            },
        }
        _atomic_write(CACHE, record)
        _atomic_write(HEARTBEAT, {
            "pid": os.getpid(),
            "ts": datetime.now(TZ).isoformat(),
            "connected": self.connected,
            "events_total": self.total,
            "events_window": sum(len(v) for v in self.events.values()),
        })

    # ── 采集主循环 ──────────────────────────────────────────────────────────
    async def _on_message(self, msg: str) -> None:
        ev = parse_message(msg)
        if not ev:
            return
        ts, _side, price, qty, coin = ev
        self.events.setdefault(coin, []).append([ts, _side, price, qty])
        self.total += 1
        if self.jsonl_out:
            try:
                with open(self.jsonl_out, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": ts, "coin": coin, "side": _side,
                                         "price": price, "qty": qty},
                                        ensure_ascii=False) + "\n")
            except OSError:
                pass
        now = time.time()
        if now - self._last_flush >= CACHE_FLUSH_S:
            self._last_flush = now
            self.flush()

    async def _tick(self) -> None:
        """无事件时也周期刷新 updated_epoch —— 让「在跑但没强平」区别于「没在跑」。"""
        while self.running:
            await asyncio.sleep(5)
            now = time.time()
            if now - self._last_stamp >= STAMP_REFRESH_S:
                self._last_stamp = now
                self.flush()

    async def _connect(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.duration if self.duration else None
        while self.running:
            if deadline is not None and loop.time() >= deadline:
                break
            try:
                print(f"[{datetime.now(TZ).isoformat()}] 连接 {WS_URL}", flush=True)
                async with websockets.connect(
                    WS_URL, ping_interval=PING_INTERVAL, ping_timeout=10, close_timeout=5,
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    print(f"[{datetime.now(TZ).isoformat()}] 已连接，监听 "
                          f"{'/'.join(SYMBOLS)} 强平流", flush=True)
                    self.flush(force=True)
                    async for msg in ws:
                        if not self.running:
                            break
                        await self._on_message(msg)
                        if deadline is not None and loop.time() >= deadline:
                            break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                print(f"[{datetime.now(TZ).isoformat()}] 连接异常: "
                      f"{type(exc).__name__}: {exc}", flush=True)
            finally:
                self.connected = False
                self.ws = None
                if self.running and (deadline is None or loop.time() < deadline):
                    self.flush(status="stale_cache")
                    print(f"[{datetime.now(TZ).isoformat()}] {RECONNECT_DELAY}s 后重连", flush=True)
                    await asyncio.sleep(RECONNECT_DELAY)

    def stop(self, *_a) -> None:
        self.running = False

    async def run(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self.stop)
                except (NotImplementedError, ValueError):
                    pass
        except Exception:
            pass
        tick = asyncio.create_task(self._tick())
        try:
            await self._connect()
        finally:
            self.running = False
            tick.cancel()
            self.flush()
            print(f"[{datetime.now(TZ).isoformat()}] 退出；本轮共收 {self.total} 笔强平", flush=True)


def _fmt(ev: list) -> str:
    side = "多单强平" if ev[1] == "long" else "空单强平"
    return f"  {side} @ {ev[2]:,.1f} × {ev[3]:g} ≈ ${ev[2] * ev[3]:,.0f}"


def main() -> int:
    global CACHE
    ap = argparse.ArgumentParser(description="Binance 强平流采集器（!forceOrder@arr）")
    ap.add_argument("--duration", type=int, default=None, help="采集 N 秒后退出（自检用）")
    ap.add_argument("--jsonl-out", default=None, help="额外落 jsonl 原始流水（调试）")
    ap.add_argument("--cache", default=str(CACHE), help="滚动缓存路径（默认 data/liquidation_ws.json）")
    args = ap.parse_args()

    CACHE = Path(args.cache)
    collector = LiquidationCollector(duration=args.duration, jsonl_out=args.jsonl_out)
    asyncio.run(collector.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
