#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TV 图表符号单点映射 —— 改口径只动这一个文件。

黄金口径（2026-09-16 用户批准，替换原 OANDA:XAUUSD）:
    GOLD_TV_SYMBOL = "TVC:GOLD"   TradingView Continuous 现货黄金连续合约
    · 同刻四源偏差 ≤0.05%（TVC:GOLD / OANDA:XAUUSD / FOREXCOM:XAUUSD / FX_IDC:XAUUSD）
    · TV 原生符号，无第三方授权依赖；免费账号实测可切图 + 载入 SVP 主指标 + 全屏截图
    · 硬伤：TVC:GOLD 成交量恒为 0（合成连续合约）→ AggVol 副指标失效。
      黄金量价只走 Binance XAUUSDT 合约 CVD 辅助源（独立键 + 明标 + 仅展示）。

缓存键稳定契约:
    换图表口径不换缓存文件名 —— 黄金永远归一到 XAUUSD，缓存仍为 tv_live_XAUUSD.json。
    否则写入侧会落 tv_live_GOLD.json 而读取侧仍找 tv_live_XAUUSD.json，形成读写错位。
"""
from __future__ import annotations

GOLD_TV_SYMBOL = "TVC:GOLD"
GOLD_CACHE_KEY = "XAUUSD"
BTC_TV_SYMBOL = "BINANCE:BTCUSDT.P"

# 品种名 → TV 图表符号。未知品种原样返回（调用方可能已传带交易所前缀的完整符号）。
TV_SYMBOL_MAP: dict[str, str] = {
    "BTCUSDT": BTC_TV_SYMBOL,
    "XAUUSD": GOLD_TV_SYMBOL,
}

# 黄金的等价写法。含历史口径 OANDA:XAUUSD —— 只做识别，不再作为输出口径。
GOLD_ALIASES: frozenset = frozenset({
    "XAUUSD", "XAU/USD", "XAU_USD", "GOLD",
    "TVC:GOLD", "OANDA:XAUUSD", "FOREXCOM:XAUUSD", "FX_IDC:XAUUSD",
    "BINANCE:XAUUSDT",
})


def is_gold(symbol) -> bool:
    """任意黄金写法（含历史 OANDA:XAUUSD 缓存）都认。"""
    return str(symbol or "").upper().strip() in GOLD_ALIASES


def tv_symbol(symbol) -> str:
    """品种名 → TV 图表符号。切图 / 截图 / 采集的统一入口。"""
    raw = str(symbol or "").upper().strip()
    if raw in GOLD_ALIASES:
        return GOLD_TV_SYMBOL
    return TV_SYMBOL_MAP.get(raw, raw)


def cache_key_of(symbol) -> str:
    """品种 → 缓存文件名后缀。复刻 _tv_symbol_cache_path 规则，只对黄金加一道归一。"""
    raw = str(symbol or "").upper().strip()
    if raw in GOLD_ALIASES:
        return GOLD_CACHE_KEY
    s = raw.split(":")[-1]
    if s.endswith(".P"):
        s = s[:-2]
    key = "".join(ch for ch in s if ch.isalnum())
    if key.endswith("PERP"):
        key = key[:-4]
    return key


def norm_identity(symbol) -> str:
    """身份归一，供跨缓存品种门禁比对。黄金全写法 → XAUUSD（兼容旧缓存）。"""
    raw = str(symbol or "").upper().strip()
    if raw in GOLD_ALIASES:
        return GOLD_CACHE_KEY
    return raw.split(":")[-1].replace(".P", "")
