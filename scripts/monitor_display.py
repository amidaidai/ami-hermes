#!/usr/bin/env python3
"""Shared Chinese display helpers for monitor cards."""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


import re

SEQ_NUMS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

LEVEL_NAME_MAP = {
    "R1_retest": "阻1·反抽位",
    "R2_reclaim_filter": "阻2·收复过滤位",
    "R3_old_support": "阻3·旧支撑转压力",
    "R4_intraday_vwap": "阻4·日内VWAP",
    "R5_breakdown_origin": "阻5·破位源头",
    "S1_sweep_low": "支1·扫低观察位",
    "S2_day_low": "支2·日内低点",
    "S3_swing_vwap": "支3·波段VWAP",
}

TYPE_MAP = {
    "reclaim_filter": "收复过滤",
    "breakout_accept": "突破接受",
    "supply_reject": "供给拒绝",
    "sweep_reclaim": "扫流动性回收",
    "major_low": "关键低点",
    "deep_support": "深回撤支撑",
    "vwap_reclaim_filter": "VWAP收复过滤",
    "retest_short": "反抽做空观察",
    "break_low": "破低延续",
    "liquidity_sweep_low": "扫低回收",
    "legacy_level": "旧版关键位",
    "level": "关键位",
}

SIDE_MAP = {
    "resistance": "阻力",
    "support": "支撑",
    "unknown": "关键",
}

PRIORITY_MAP = {"high": "高", "medium": "中", "low": "低"}
CONDITION_MAP = {
    "near_or_breach": "接近或触发",
    "near": "接近计划位",
    "breach": "触发关键位",
    "close_confirm": "等待收盘确认",
    "retest": "回踩确认",
    "sweep_reclaim": "扫流动性后收回",
    "combo": "组合条件触发",
    "combined": "组合条件触发",
}

RULE_REPLACEMENTS = [
    ("close above", "收盘上破"),
    ("close below", "收盘下破"),
    ("price reclaims", "价格收复"),
    ("and retest holds", "且回踩守住"),
    ("reclaim above", "收复上方"),
    ("below", "下方"),
    ("above", "上方"),
]


def seq(index: int) -> str:
    return SEQ_NUMS[index - 1] if 1 <= index <= len(SEQ_NUMS) else f"{index}."


def lab(name: str, width: int = 4) -> str:
    return f"{name:<{width}}："


def zh_priority(value) -> str:
    return PRIORITY_MAP.get(str(value), str(value))


def zh_condition(value) -> str:
    return CONDITION_MAP.get(str(value), str(value or "接近计划位"))


def zh_duration(value) -> str:
    text = str(value or "")
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([mhd])\s*", text, re.I)
    if not m:
        return text or "未设置"
    num, unit = m.groups()
    if num.endswith(".0"):
        num = num[:-2]
    return f"{num}{ {'m': '分钟', 'h': '小时', 'd': '天'}[unit.lower()] }"


def zh_rule(rule) -> str:
    text = str(rule or "见最新分析")
    for old, new in RULE_REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r"\b(\d+)m\b", r"\1分钟", text)
    text = re.sub(r"\b(\d+)h\b", r"\1小时", text)
    text = re.sub(r"\b(\d+)d\b", r"\1天", text)
    return text


def display_name(item: dict) -> str:
    if item.get("display_name"):
        return str(item["display_name"])
    raw = str(item.get("name") or "关键位")
    if raw in LEVEL_NAME_MAP:
        return LEVEL_NAME_MAP[raw]

    m = re.match(r"^([RS])(\d+)_([A-Za-z]+)_?(.*)$", raw)
    if not m:
        return raw
    prefix, number, word, rest = m.groups()
    head = "阻" if prefix == "R" else "支"
    word_zh = {
        "reclaim": "收复",
        "breakout": "突破接受位",
        "supply": "供给",
        "sweep": "扫低",
        "low": "低点",
        "value": "价值区",
        "retest": "反抽",
    }.get(word.lower(), word)
    tail = ""
    if rest:
        tail = re.sub(r"_?\d+(?:\.\d+)?", "", rest).strip("_")
        tail = tail.replace("filter", "过滤").replace("origin", "源头")
        tail = f"·{tail}" if tail else ""
    return f"{head}{number}·{word_zh}{tail}"


def zh_side(value) -> str:
    return SIDE_MAP.get(str(value), str(value or "关键"))


def zh_type(value) -> str:
    return TYPE_MAP.get(str(value), str(value or "关键位"))


def distance_text(price: float, level: float) -> str:
    if not level:
        return "距离未知"
    diff = price - level
    pct = abs(diff) / level * 100
    if abs(diff) < 1e-9:
        return "价格正贴关键位"
    side = "高于" if diff > 0 else "低于"
    return f"现价{side}关键位 {pct:.1f}%"


def display_plan(plan_id, symbol: str) -> str:
    text = str(plan_id or "手动计划")
    coin = symbol.replace("USDT", "")
    coin_zh = {"BTC": "比特币", "ETH": "以太坊", "XAU": "黄金"}.get(coin, coin)
    m = re.search(r"(\d{4})(\d{2})(\d{2})-(\d{4})", text)
    if m:
        _, month, day, clock = m.groups()
        return f"{coin_zh}日内计划·{int(month)}月{int(day)}日{clock[:2]}:{clock[2:]}"
    return text.replace("USDT", "")


def situation_text(tier: str) -> str:
    return {
        "critical": "关键位已触发，且动能有配合",
        "warning": "价格已贴近或触发关键位",
        "info": "价格接近计划位，先观察确认",
        "invalidated": "旧计划失效，不按原方向执行",
        "expired": "监控位过期，旧计划降权",
    }.get(tier, "等待计划条件触发")


def level_confidence_text(item: dict) -> str:
    conf = item.get("live_level_confidence") or item.get("level_confidence") or item.get("confidence")
    if not isinstance(conf, dict):
        return "未评分"
    grade = conf.get("grade") or conf.get("quality") or "C"
    score = conf.get("score") or conf.get("confidence") or 0
    label = conf.get("label") or "未验证"
    basis = conf.get("basis") or []
    if isinstance(basis, list) and basis:
        basis_text = "；".join(str(x) for x in basis[:3])
        return f"{grade}级 · {score}% · {label} · {basis_text}"
    return f"{grade}级 · {score}% · {label}"


def format_level_block(price: float, item: dict, index: int) -> str:
    level = float(item.get("level", 0) or 0)
    lines = [f"{seq(index)} {lab('价位')}{display_name(item)} · `{level:.0f}`"]
    lines.append(f"   {lab('位信')}{level_confidence_text(item)}")
    lines.append(f"   {lab('距离')}{distance_text(price, level)}")
    lines.append(f"   {lab('属性')}{zh_side(item.get('side'))} · {zh_type(item.get('type'))}")
    lines.append(f"   {lab('现状')}{item.get('condition_reason') or zh_condition(item.get('condition'))}")
    lines.append(f"   {lab('动作')}{item.get('action', '关键位提醒')}")
    lines.append(f"   {lab('失效')}{zh_rule(item.get('invalid_if', '见最新分析'))}")
    lines.append(f"   {lab('优先')}{zh_priority(item.get('priority', 'medium'))}")
    if item.get("expires"):
        lines.append(f"   {lab('有效')}{zh_duration(item.get('expires'))}")
    return "\n".join(lines)
