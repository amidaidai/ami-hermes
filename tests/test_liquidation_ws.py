"""Binance 强平流采集器回归（scripts/ws_liquidation_listener.py）。

只锁离线可复现的部分：推送解析、方向语义、滚动窗口、缓存/心跳契约。
真 WS 连接不进单测（依赖交易所网络）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ws_liquidation_listener as ws  # noqa: E402

TS = 1_789_478_089_000


def _push(symbol="BTCUSDT", side="SELL", px="77650.1", qty="12.3", ap=None, ts=TS):
    return json.dumps({
        "e": "forceOrder", "E": ts,
        "o": {"s": symbol, "S": side, "p": px, "q": qty,
              "ap": ap if ap is not None else px, "X": "FILLED", "T": ts},
    })


def test_sell_side_means_long_position_liquidated():
    """`S=SELL` = 多头被强平 —— 记的是被强平方，不是订单方向。"""
    ev = ws.parse_message(_push(side="SELL"))
    assert ev == [TS, "long", 77650.1, 12.3, "BTC"]


def test_buy_side_means_short_position_liquidated():
    assert ws.parse_message(_push(side="BUY"))[1] == "short"


def test_average_price_preferred_over_trigger_price():
    ev = ws.parse_message(_push(px="77500", ap="77649.8"))
    assert ev[2] == 77649.8


def test_unknown_symbol_and_malformed_payloads_are_dropped():
    assert ws.parse_message(_push(symbol="DOGEUSDT")) is None
    assert ws.parse_message(_push(symbol="BTCUSDT", side="SELL", qty="0")) is None
    assert ws.parse_message("not-json") is None
    assert ws.parse_message(json.dumps({"e": "aggTrade"})) is None


def test_bytes_payload_is_accepted():
    assert ws.parse_message(_push().encode())[1] == "long"


def test_coin_mapping_covers_configured_symbols():
    assert ws._coin("ethusdt") == "ETH"
    assert ws._coin("SOLUSDT") == "SOL"
    assert ws._coin("XAUUSD") == ""


def test_flush_writes_cache_and_heartbeat_contract(tmp_path, monkeypatch):
    """缓存必须带 `updated_epoch`：数据新鲜度看门狗只认 TIMESTAMP_KEYS，不认 fetched_at。"""
    cache = tmp_path / "liquidation_ws.json"
    beat = tmp_path / ".liquidation_ws_heartbeat.json"
    monkeypatch.setattr(ws, "CACHE", cache)
    monkeypatch.setattr(ws, "HEARTBEAT", beat)

    col = ws.LiquidationCollector()
    col.connected = True
    col.events["BTC"].append([int(__import__("time").time() * 1000) - 1000, "long", 70_000.0, 1.0])
    col.total = 1
    col.flush()

    rec = json.loads(cache.read_text(encoding="utf-8"))
    assert rec["status"] == "live"
    assert isinstance(rec["updated_epoch"], int) and rec["updated_epoch"] > 0
    assert rec["coins"]["BTC"]["events"][0][1] == "long"
    assert rec["coins"]["BTC"]["coverage_to"] > 0
    assert json.loads(beat.read_text(encoding="utf-8"))["events_total"] == 1


def test_prune_drops_events_outside_window(tmp_path, monkeypatch):
    import time

    monkeypatch.setattr(ws, "CACHE", tmp_path / "c.json")
    monkeypatch.setattr(ws, "HEARTBEAT", tmp_path / "h.json")
    now_ms = int(time.time() * 1000)
    col = ws.LiquidationCollector()
    col.events["BTC"] = [
        [now_ms - 60_000, "long", 70_000.0, 1.0],                       # 窗内
        [now_ms - (ws.WINDOW_S + 120) * 1000, "short", 70_000.0, 2.0],  # 窗外
    ]
    col.flush()
    rec = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert len(rec["coins"]["BTC"]["events"]) == 1


def test_disconnected_flush_is_labelled_stale_not_live(tmp_path, monkeypatch):
    """断线时不得把状态写成 live —— 卡面要靠它显示降级。"""
    monkeypatch.setattr(ws, "CACHE", tmp_path / "c.json")
    monkeypatch.setattr(ws, "HEARTBEAT", tmp_path / "h.json")
    col = ws.LiquidationCollector()
    col.connected = False
    col.flush()
    assert json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))["status"] == "stale_cache"


def test_watchdog_and_collector_agree_on_paths_and_threshold():
    """保活看门狗盯的就是采集器的落盘位置，路径不一致会让守护永远重启。"""
    src = (ROOT / "scripts" / "liquidation_ws_watchdog.py").read_text(encoding="utf-8")
    assert "data/.liquidation_ws_heartbeat.json" in src
    assert "ws_liquidation_listener.py" in src
    assert ws.STAMP_REFRESH_S < 180, "心跳刷新间隔必须小于看门狗超时阈值"