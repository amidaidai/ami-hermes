#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Binance USDT-M Futures 强平单 WebSocket 监听
- 订阅: wss://fstream.binance.com/ws/!forceOrder@arr
- 输出: /data/liq_btcusdt_YYYYMMDD.jsonl (每行一条 JSON)
- 字段: ts(ms), side, price, qty, symbol, o_type(可选)
- 仅保留 BTCUSDT，其他品种丢弃
- 自动断线重连、按日轮转文件
"""
import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import websockets

# ============== 配置 ==============
WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"
DATA_DIR = Path(r"D:/Hermes agent/data/liquidations")
DATA_DIR.mkdir(parents=True, exist_ok=True)
TARGET_SYMBOL = "BTCUSDT"
RECONNECT_DELAY = 5  # 秒
HEARTBEAT_INTERVAL = 30  # 秒
# ==================================


class LiquidationListener:
    def __init__(self):
        self.running = True
        self.current_file = None
        self.current_date = None
        self.ws = None

    def _get_filepath(self, dt: datetime) -> Path:
        return DATA_DIR / f"liq_{TARGET_SYMBOL.lower()}_{dt.strftime('%Y%m%d')}.jsonl"

    def _rotate_file(self, dt: datetime):
        date_str = dt.strftime('%Y%m%d')
        if date_str != self.current_date:
            if self.current_file:
                self.current_file.close()
            self.current_file = open(self._get_filepath(dt), "a", encoding="utf-8", buffering=1)
            self.current_date = date_str
            print(f"[{dt.isoformat()}] 📄 轮转文件: {self.current_file.name}")

    async def _write_record(self, record: dict):
        now = datetime.now(timezone(timedelta(hours=8)))  # 北京时间
        self._rotate_file(now)
        self.current_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _parse_message(self, msg: str):
        try:
            data = json.loads(msg)
            # Binance 推送格式: {"e":"forceOrder","E":123456789,"o":{"s":"BTCUSDT","S":"SELL","p":"77650.1","q":"12.3","ap":"77649.8","X":"FILLED","l":"12.3","z":"12.3","T":123456789}}
            if data.get("e") != "forceOrder":
                return None
            o = data.get("o", {})
            if o.get("s") != TARGET_SYMBOL:
                return None
            return {
                "ts": data.get("E"),           # 事件时间 ms
                "side": o.get("S"),            # BUY/SELL (被强平方向)
                "price": float(o.get("p")),    # 强平价格
                "qty": float(o.get("q")),      # 强平数量
                "symbol": o.get("s"),
                "avg_price": float(o.get("ap", o.get("p"))),  # 平均成交价
                "status": o.get("X"),          # FILLED 等
                "last_qty": float(o.get("l", 0)),
                "cum_qty": float(o.get("z", 0)),
                "trade_time": o.get("T"),      # 成交时间 ms
            }
        except Exception as e:
            print(f"[解析错误] {e} | raw: {msg[:200]}")
            return None

    async def _connect(self):
        while self.running:
            try:
                print(f"[{datetime.now().isoformat()}] 🔌 连接 {WS_URL}")
                async with websockets.connect(
                    WS_URL,
                    ping_interval=HEARTBEAT_INTERVAL,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self.ws = ws
                    print(f"[{datetime.now().isoformat()}] ✅ 已连接，开始监听 {TARGET_SYMBOL} 强平流")
                    async for msg in ws:
                        if not self.running:
                            break
                        record = self._parse_message(msg)
                        if record:
                            await self._write_record(record)
                            # 实时打印关键信息
                            side_emoji = "🔴" if record["side"] == "SELL" else "🟢"
                            print(f"  {side_emoji} {record['ts']} | {record['side']} @ {record['price']:,.1f} | qty={record['qty']:.3f} | {record['symbol']}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] ⚠️ 连接异常: {e}")
            finally:
                self.ws = None
                if self.running:
                    print(f"[{datetime.now().isoformat()}] ♻️ {RECONNECT_DELAY}s 后重连...")
                    await asyncio.sleep(RECONNECT_DELAY)

    async def run(self):
        # 优雅关闭
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._shutdown)
            except NotImplementedError:
                pass  # Windows 不支持 add_signal_handler
        await self._connect()

    def _shutdown(self):
        print(f"\n[{datetime.now().isoformat()}] 🛑 收到停止信号，正在关闭...")
        self.running = False
        if self.ws:
            asyncio.create_task(self.ws.close())
        if self.current_file:
            self.current_file.close()


def main():
    listener = LiquidationListener()
    try:
        asyncio.run(listener.run())
    except KeyboardInterrupt:
        listener._shutdown()


if __name__ == "__main__":
    main()