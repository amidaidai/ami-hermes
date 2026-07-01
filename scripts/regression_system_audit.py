#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪系统审计回归检查：TV品种门禁 + Protections结构化落盘 + 驾驶舱表格。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"✅ {message}")


def test_tv_cache_gate() -> None:
    from auto_card import _tv_cache_status

    btc_cache = {"symbol": "BINANCE:BTCUSDT.P", "timestamp": "2999-01-01T00:00:00+08:00", "fresh": True, "poc": 59657}
    xau_status = _tv_cache_status(btc_cache, "XAUUSD", max_age_minutes=10**9)
    btc_status = _tv_cache_status(btc_cache, "BTCUSDT", max_age_minutes=10**9)
    check(not xau_status["usable"] and "品种不匹配" in xau_status["reason"], "XAU拒绝BTC TV缓存")
    check(btc_status["usable"], "BTC接受BTC TV缓存")


def test_protections_json_shape() -> None:
    from risk_constitution import Protections, load_protections, save_protections

    bad_file = DATA / "protections_state.json"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    original = bad_file.read_text(encoding="utf-8") if bad_file.exists() else None
    try:
        bad_file.write_text(json.dumps("Protections(stoploss_guard={}, cooldown_active=False)", ensure_ascii=False), encoding="utf-8")
        loaded = load_protections()
        check(isinstance(loaded, Protections), "旧字符串Protections可兼容读取")
        save_protections(loaded)
        data = json.loads(bad_file.read_text(encoding="utf-8"))
        check(isinstance(data, dict), "Protections落盘为dict")
        required = {"stoploss_guard", "cooldown_active", "daily_drawdown_pct", "suspended"}
        check(required.issubset(data.keys()), "Protections关键字段完整")
    finally:
        if original is not None:
            bad_file.write_text(original, encoding="utf-8")
        elif bad_file.exists():
            bad_file.unlink()


def test_render_contains_conflict_table() -> None:
    from render_v8 import render_v8_card

    card = render_v8_card(
        "BTCUSDT", "B等待", "long", 60000, None, None, None, "", "买", "A", "buy", "1.2", "0.01%",
        "亚洲", {"available": True, "vwap": {"vwap": 60010, "price_vs_vwap": "下方"}}, "50", [], False,
        {"stop": 59000, "target": 62000}, {"stop": 61000, "target": 58000}, 2.0, 2.0, "", "", 1.0,
        "Binance 10x", 59000, "通过", "A", "待扫", "待判", "测试", "VWAP反抽", 3, 0.5,
        klines={}, tv_dmi={"grade": "B", "action": "观察", "position": "VWAP下方", "bias_4h": "偏空"},
    )
    check("### 矛盾点" in card, "驾驶舱包含矛盾点表")
    check("| 多头证据 |" in card and "| 空头证据 |" in card and "| 裁决 |" in card, "矛盾点表字段完整")


def test_markdown_tables_are_rectangular() -> None:
    from render_v8 import render_v8_card

    card = render_v8_card(
        "XAUUSD", "B等待", "long", 3978, None, None, None, "", "N/A", "C", "N/A", "N/A", "N/A",
        "亚洲", {}, "?", [], False,
        {"stop": 3962, "target": 3993}, {"stop": 3997, "target": 3947}, 0.9, 1.7, "", "", 1.0,
        "OANDA 1000x", None, "通过", "A", "待扫", "待判", "测试", "gold-api·金十 现货3978 | 24h高4018 低3970", 0, 0.0,
        klines={"5m": {"description": "gold-api·金十 现货3978 | 24h高4018 低3970", "poc": 3978, "vah": 3995, "val": 3970}},
        tv_dmi={"grade": "B", "action": "观察", "position": "VWAP下方", "bias_4h": "偏空"},
    )
    blocks = []
    current = []
    for line in card.splitlines():
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append(current); current = []
    if current:
        blocks.append(current)
    for block in blocks:
        widths = [len(row.split("|")) for row in block]
        check(len(set(widths)) == 1, f"Markdown表格列数一致: {block[0][:20]}")


def main() -> None:
    test_tv_cache_gate()
    test_protections_json_shape()
    test_render_contains_conflict_table()
    test_markdown_tables_are_rectangular()
    print("✅ regression_system_audit 全部通过")


if __name__ == "__main__":
    main()
