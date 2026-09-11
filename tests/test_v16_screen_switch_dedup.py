# -*- coding: utf-8 -*-
"""20260911：切图去冗余的回归测试。

背景：用户报「TV图表总是自己切品种和周期」。取证发现多个定时任务抢同一张图，
而每次 set_symbol/set_timeframe 都会让 TV 重新拉数据、重绘指标。
修复：已经是目标的品种/周期就跳过下发。

注意：本修复【不减少必需的切换】（实测 XAU 一轮 7 次全是必需的），
它的价值是去掉冗余重绘 + 提供可观测的切换计数。
"""
import asyncio
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _load():
    return importlib.import_module("fetch_tv_mcp")


class _FakeSession:
    """记录所有下发的 MCP 调用。"""

    def __init__(self, state):
        self.state = state
        self.calls = []

    async def call_tool(self, name, args=None):
        self.calls.append((name, args or {}))

        class _R:
            def __init__(self, text):
                self.content = [type("C", (), {"text": text})()]

        if name == "chart_get_state":
            import json
            return _R(json.dumps(self.state))
        return _R('{"success": true}')


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_set_symbol_skips_when_already_current(monkeypatch):
    F = _load()
    F.SWITCH_STATS.update(symbol_set=0, symbol_skipped=0)
    s = _FakeSession({"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"})
    out = _run(F.set_symbol(s, "BINANCE:BTCUSDT.P"))
    assert out.get("skipped") is True
    assert not any(c[0] == "chart_set_symbol" for c in s.calls), "不该重复下发"
    assert F.SWITCH_STATS["symbol_skipped"] == 1


def test_set_symbol_sends_when_different(monkeypatch):
    F = _load()
    F.SWITCH_STATS.update(symbol_set=0, symbol_skipped=0)
    s = _FakeSession({"symbol": "OANDA:XAUUSD", "resolution": "5"})
    _run(F.set_symbol(s, "BINANCE:BTCUSDT.P"))
    assert any(c[0] == "chart_set_symbol" for c in s.calls)
    assert F.SWITCH_STATS["symbol_set"] == 1


def test_set_timeframe_skips_on_equivalent_alias():
    """15m 与 15 是同一个周期，不能因为写法不同就重切。"""
    F = _load()
    F.SWITCH_STATS.update(timeframe_set=0, timeframe_skipped=0)
    for cur, want in (("15", "15m"), ("240", "4h"), ("D", "1D"), ("5", "5m"), ("60", "1h")):
        s = _FakeSession({"symbol": "BINANCE:BTCUSDT.P", "resolution": cur})
        out = _run(F.set_timeframe(s, want))
        assert out.get("skipped") is True, f"{cur} vs {want} 应视为同一周期"
        assert not any(c[0] == "chart_set_timeframe" for c in s.calls)


def test_set_timeframe_sends_when_truly_different():
    F = _load()
    F.SWITCH_STATS.update(timeframe_set=0, timeframe_skipped=0)
    s = _FakeSession({"symbol": "BINANCE:BTCUSDT.P", "resolution": "15"})
    _run(F.set_timeframe(s, "5"))
    assert any(c[0] == "chart_set_timeframe" for c in s.calls)


def test_state_read_failure_does_not_skip():
    """读不到状态时宁可不跳过 —— 绝不因为省一次重绘而漏切。

    真实场景下 chart_get_state 失败通常是返回 success:false 或非 JSON，
    而不是抛异常，所以这里模拟「读不到」。"""
    F = _load()
    F.SWITCH_STATS.update(symbol_set=0, symbol_skipped=0)

    class _Blind:
        """状态读不到，但下发调用要能记录到。"""

        def __init__(self):
            self.calls = []

        async def call_tool(self, name, args=None):
            self.calls.append((name, args or {}))

            class _R:
                def __init__(self, text):
                    self.content = [type("C", (), {"text": text})()]

            if name == "chart_get_state":
                return _R("not-json-at-all")      # 读不到 → {}
            return _R('{"success": true}')

    s = _Blind()
    _run(F.set_symbol(s, "BINANCE:BTCUSDT.P"))
    assert any(c[0] == "chart_set_symbol" for c in s.calls), "读不到状态时必须照常下发"
    assert F.SWITCH_STATS["symbol_set"] == 1


def test_switch_stats_line_reports_both_counts():
    F = _load()
    F.SWITCH_STATS.update(symbol_set=2, symbol_skipped=1, timeframe_set=6, timeframe_skipped=3)
    line = F.switch_stats_line()
    assert "实切2" in line and "跳过1" in line and "实切6" in line and "跳过3" in line
