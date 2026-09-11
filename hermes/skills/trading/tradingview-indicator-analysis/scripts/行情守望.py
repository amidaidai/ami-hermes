#!/usr/bin/env python3
"""实时推送监控 v6.3 — 风控闸门、衍生品摘要、计划闭环。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    import trading_system as ts
except Exception:
    ts = None

try:
    from monitor_display import (
        display_name,
        display_plan,
        format_level_block,
        lab,
        seq,
        situation_text,
    )
except Exception:
    display_name = display_plan = format_level_block = lab = seq = situation_text = None

DEFAULT_SYMBOL = "BTCUSDT"
ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
LEVELS_FILE = DATA_DIR / "monitor_levels.json"
EVENT_FILE = DATA_DIR / "monitor_events.json"
STATE_FILE = DATA_DIR / "monitor_state.json"
LOG_FILE = DATA_DIR / "monitor.log"
LOCK_FILE = DATA_DIR / "monitor.lock"
HEARTBEAT_FILE = DATA_DIR / "monitor_heartbeat.json"
REFRESH_FILE = DATA_DIR / "structure_refresh_requests.jsonl"
SYSTEM_EVENT_FILE = DATA_DIR / "system_events.jsonl"

NEAR_PCT = 0.003
BREACH_PCT = 0.001
POLL = 10
COOLDOWN = {"critical": 120, "warning": 300, "info": 900, "invalidated": 900, "expired": 1800}
SAME_LV_CD = 1800
ALERT_BUDGET_WINDOW = 3600
ALERT_BUDGET_BY_TIER = {"critical": 8, "warning": 4, "info": 2, "invalidated": 2, "expired": 1}
ALERT_BUDGET_GLOBAL = 12
STRICT_PUSH_MODE = True
# 棠溪需要确认监控在工作；warning 维持强确认，但不再把 75-77 的高优先级位信全部静默。
MIN_WARNING_LEVEL_SCORE = 75
MIN_CRITICAL_LEVEL_SCORE = 75
NOISE_SUMMARY_WINDOW = 3 * 3600
MAX_STALE_SECONDS = 90
MAX_PRICE_JUMP_PCT = {"BTCUSDT": 1.2, "XAUUSD": 0.6}
DATA_FAILURE_LIMIT = 3
META_KEYS = {"updated", "analysis_cycle", "price_at_analysis", "symbol", "symbols", "levels", "plan_id"}


def now_local():
    return datetime.now().astimezone()


def old_lab(name, width=4):
    return f"{name:<{width}}："


def old_seq(index):
    nums = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
    return nums[index - 1] if 1 <= index <= len(nums) else f"{index}."


def zh_priority(value):
    return {"high": "高", "medium": "中", "low": "低"}.get(str(value), str(value))


def zh_rule(rule):
    text = str(rule or "见最新分析")
    replacements = [
        ("close above", "收盘上破"),
        ("close below", "收盘下破"),
        ("price reclaims", "价格收复"),
        ("and retest holds", "且回踩守住"),
        ("reclaim above", "收复上方"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def old_display_name(item):
    if item.get("display_name"):
        return item["display_name"]
    mapping = {
        "R1_retest": "阻1_反抽",
        "R2_reclaim_filter": "阻2_收复过滤",
        "R3_old_support": "阻3_旧支撑",
        "R4_intraday_vwap": "阻4_日内VWAP",
        "R5_breakdown_origin": "阻5_破位源",
        "S1_sweep_low": "支1_扫低",
        "S2_day_low": "支2_日低",
        "S3_swing_vwap": "支3_波段VWAP",
    }
    return mapping.get(str(item.get("name", "关键位")), str(item.get("name", "关键位")))


def old_display_plan(plan_id, symbol):
    text = str(plan_id or "手动计划")
    coin = symbol.replace("USDT", "")
    coin_zh = {"BTC": "比特币", "ETH": "以太坊", "XAU": "黄金"}.get(coin, coin)
    m = re.search(r"(\d{4})(\d{2})(\d{2})-(\d{4})", text)
    if m:
        _, month, day, clock = m.groups()
        return f"{coin_zh}日内计划·{int(month)}月{int(day)}日{clock[:2]}:{clock[2:]}"
    return text.replace("USDT", "")


def old_situation_text(tier):
    return {
        "critical": "关键位已触发，且动能有配合",
        "warning": "价格已贴近或触发关键位",
        "info": "价格接近计划位，先观察确认",
        "invalidated": "旧计划失效，不按原方向执行",
        "expired": "监控位过期，旧计划降权",
    }.get(tier, "等待计划条件触发")


def log(msg):
    ts_ = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts_}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_json(path, default):
    try:
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def parse_duration(text):
    if not text:
        return None
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([mhd])\s*", str(text), re.I)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=value)


def get_price(symbol, block=None):
    if ts:
        try:
            probe = ts.template_price(symbol)
            price = probe.get("price")
            if isinstance(price, (int, float)) and price > 0:
                return float(price)
        except Exception as e:
            log(f"模板价格错误 {symbol}: {e}")
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:
        log(f"价格错误 {symbol}: {e}")
        if isinstance(block, dict) and isinstance(block.get("price_at_analysis"), (int, float)):
            log(f"价格源不可用 {symbol}: 使用分析价临时兜底")
            return float(block["price_at_analysis"])
        return None


def get_close(symbol, interval):
    if not str(symbol).upper().endswith("USDT"):
        return get_price(symbol)
    try:
        r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": 2}, timeout=10)
        r.raise_for_status()
        k = r.json()
        return float(k[-2][4] if len(k) > 1 else k[-1][4])
    except Exception as e:
        log(f"收盘价错误 {symbol} {interval}: {e}")
        return None


def get_cvd(symbol):
    if not str(symbol).upper().endswith("USDT"):
        return "不适用", "非加密"
    try:
        r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": "1m", "limit": 5}, timeout=10)
        r.raise_for_status()
        k = r.json()
        buy = sum(float(x[9]) for x in k)
        total = sum(float(x[7]) for x in k)
        sell = total - buy
        d = buy - sell
        direction = "买" if d > total * 0.1 else ("卖" if d < -total * 0.1 else "中性")
        return direction, "C级"
    except Exception:
        return "?", "C级"


def push(msg):
    try:
        subprocess.run([sys.executable, "-m", "hermes_cli.main", "send", "-t", "telegram:阿弥黛黛", "-q", msg], timeout=15, capture_output=True)
        return True
    except Exception as e:
        log(f"推送失败: {e}")
        return False


def pid_alive(pid):
    if not pid:
        return False
    try:
        if os.name == "nt":
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue) {{ '1' }}"], capture_output=True, text=True, timeout=5).stdout
            return "1" in out
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def acquire_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            old_pid = int(lock.get("pid") or 0)
            old_started = lock.get("started")
        except Exception:
            try:
                old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip() or "0")
                old_started = None
            except Exception:
                old_pid = 0
                old_started = None
        if pid_alive(old_pid):
            log(f"已有监控运行: PID {old_pid}")
            return False
        try:
            LOCK_FILE.unlink()
        except FileNotFoundError:
            pass
    payload = {"pid": os.getpid(), "started": now_local().isoformat(), "script": str(Path(__file__).resolve())}
    LOCK_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_heartbeat("start")
    return True


def write_heartbeat(status="running", symbol=None):
    payload = {"time": now_local().isoformat(), "pid": os.getpid(), "status": status}
    if symbol:
        payload["symbol"] = symbol
    save_json(HEARTBEAT_FILE, payload)


def release_lock():
    try:
        current = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        if str(current.get("pid")) == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        try:
            if LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK_FILE.unlink()
        except Exception:
            pass
    write_heartbeat("stopped")


def iter_symbol_blocks(raw):
    if isinstance(raw.get("symbols"), dict):
        for symbol, block in raw["symbols"].items():
            if isinstance(block, dict):
                merged = dict(block)
                merged.setdefault("symbol", symbol)
                yield symbol, merged
        return
    yield raw.get("symbol") or DEFAULT_SYMBOL, raw


def normalize_levels(block):
    if isinstance(block.get("levels"), list):
        items = []
        for idx, item in enumerate(block["levels"]):
            if not isinstance(item, dict) or not isinstance(item.get("level"), (int, float)):
                continue
            normalized = dict(item)
            normalized["name"] = str(normalized.get("name") or f"L{idx + 1}")
            normalized["level"] = float(normalized["level"])
            normalized.setdefault("side", "unknown")
            normalized.setdefault("type", "level")
            normalized.setdefault("action", "关键位提醒")
            normalized.setdefault("priority", "medium")
            normalized.setdefault("condition", "near_or_breach")
            normalized.setdefault("status", "active")
            normalized.setdefault("invalid_if", "见最新分析")
            items.append(normalized)
        return items
    items = []
    for name, value in block.items():
        if name in META_KEYS or not isinstance(value, (int, float)):
            continue
        items.append({"name": name, "level": float(value), "side": "unknown", "type": "legacy_level", "action": "关键位提醒", "priority": "medium", "condition": "near_or_breach", "expires": "legacy", "invalid_if": "见最新分析", "status": "active"})
    return items


def level_deadline(block, item):
    direct = parse_dt(item.get("valid_until"))
    if direct:
        return direct
    duration = parse_duration(item.get("expires"))
    updated = parse_dt(item.get("updated")) or parse_dt(block.get("updated"))
    if duration and updated:
        return updated + duration
    return None


def is_expired(block, item):
    deadline = level_deadline(block, item)
    return bool(deadline and now_local() > deadline)


def eval_invalid(symbol, rule):
    text = str(rule or "").strip().lower()
    if not text or text in {"见最新分析", "legacy"}:
        return False, ""
    m = re.search(r"(1m|3m|5m|15m|30m|1h|4h|1d)\s+(?:close|收盘)\s+(above|below|上破|下破)\s+([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        interval, op, raw_level = m.groups()
        close = get_close(symbol, interval)
        if close is None:
            return False, ""
        level = float(raw_level)
        above = op in {"above", "上破"}
        hit = close > level if above else close < level
        direction = "上破" if above else "下破"
        return hit, f"{interval}收盘 `{close:.0f}` {direction} `{level:.0f}`"
    m = re.search(r"(?:price\s+reclaims|reclaim\s+above|价格收复|收复上方)\s+([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        price = get_price(symbol)
        if price is None:
            return False, ""
        level = float(m.group(1))
        return price > level, f"价格收复 `{level:.0f}`"
    return False, ""


def condition_ready(condition, price, level, item, symbol):
    text = str(condition or "near_or_breach")
    dist = abs(price - level) / level
    if text in {"near_or_breach", "near"}:
        return dist < NEAR_PCT, "接近计划位"
    if text == "breach":
        return dist < BREACH_PCT, "触发关键位"
    if text == "close_confirm":
        hit, reason = eval_invalid(symbol, item.get("confirm_if") or item.get("invalid_if"))
        return hit, reason or "等待收盘确认"
    if text in {"combo", "combined"}:
        near_ok = dist < NEAR_PCT
        close_rule = item.get("confirm_if")
        if close_rule:
            close_ok, close_reason = eval_invalid(symbol, close_rule)
            if not close_ok:
                return False, close_reason or "等待收盘确认"
        if not near_ok:
            return False, "未接近组合触发区"
        return True, "价格接近且组合条件初步满足"
    if text == "retest":
        return dist < NEAR_PCT, "回踩区等待确认"
    if text == "sweep_reclaim":
        return dist < NEAR_PCT, "扫流动性后等待收回"
    return dist < NEAR_PCT, "接近计划位"


def format_hit(price, item, index):
    if format_level_block:
        return format_level_block(price, item, index) + "\n"
    level = item["level"]
    lines = [f"{index}. 价位：{item.get('name', '关键位')} `{level:.0f}`"]
    lines.append(f"   动作：{item.get('action', '关键位提醒')}")
    return "\n".join(lines) + "\n"


def event_level_rows(items):
    keys = ("name", "level", "side", "type", "action", "priority", "level_confidence", "live_level_confidence", "invalid_if", "expires", "condition", "condition_reason")
    return [{k: x.get(k) for k in keys if k in x} for x in items]


def derivatives_line(snapshot):
    if not snapshot:
        return "未刷新"
    d = snapshot.get("derivatives", {})
    if not d.get("ok"):
        return "不可用"
    return d.get("interpretation", "已刷新")


def confidence_line(snapshot):
    if not snapshot:
        return "C级 · 0% · 无快照"
    q = snapshot.get("quality", "C")
    score = snapshot.get("confidence", 0)
    label = snapshot.get("confidence_label") or "未验证"
    spread = snapshot.get("price_spread_pct")
    spread_txt = f" · 价差{spread:.3f}%" if isinstance(spread, (int, float)) else ""
    return f"{q}级 · {score}% · {label}{spread_txt}"


def grade_from_score(score):
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    return "C"


def live_level_confidence(item, tier, cvd=None, cvd_quality=None, condition_reason=None, snapshot=None):
    base = item.get("level_confidence") if isinstance(item.get("level_confidence"), dict) else {}
    score = int(base.get("score") or 55)
    basis = list(base.get("basis") or [])[:3]
    missing = list(base.get("missing") or [])
    label = base.get("label") or "实时初评"
    if tier == "critical":
        score += 8
        basis.append("触发等级紧急")
    elif tier == "warning":
        score += 3
        basis.append("价格触发关键位")
    if condition_reason:
        basis.append(str(condition_reason))
    if cvd == "买" and item.get("side") == "support":
        score += 4
        basis.append("CVD买盘配合支撑")
    elif cvd == "卖" and item.get("side") == "resistance":
        score += 4
        basis.append("CVD卖盘配合阻力")
    elif cvd in {"买", "卖"}:
        score -= 3
        missing.append("CVD方向未配合关键位")
    if cvd_quality == "C级":
        score -= 3
        missing.append("CVD仅C级")
    if snapshot and snapshot.get("quality") == "C":
        score -= 6
        missing.append("价格数据C级")
    score = max(35, min(95, score))
    return {"grade": grade_from_score(score), "score": score, "label": f"实时{label}", "basis": basis[:4], "missing": missing[:4], "method": "结构位置信度v2-live"}


def confidence_payload(snapshot):
    return {"quality": (snapshot or {}).get("quality"), "score": (snapshot or {}).get("confidence"), "label": (snapshot or {}).get("confidence_label"), "spread_pct": (snapshot or {}).get("price_spread_pct"), "sources": (snapshot or {}).get("prices", {}).get("sources", [])}




def record_noise(state, symbol, tier, reason):
    now_ts = time.time()
    history = [x for x in state.get("noise_history", []) if now_ts - x.get("time", 0) < NOISE_SUMMARY_WINDOW]
    history.append({"time": now_ts, "symbol": symbol, "tier": tier, "reason": reason})
    state["noise_history"] = history[-200:]

def max_level_score(items):
    scores = []
    for item in items or []:
        live = item.get("live_level_confidence") if isinstance(item.get("live_level_confidence"), dict) else {}
        static = item.get("level_confidence") if isinstance(item.get("level_confidence"), dict) else {}
        for src in (live, static):
            try:
                scores.append(int(src.get("score")))
                break
            except Exception:
                continue
    return max(scores) if scores else 0


def xau_single_quote_ok(snapshot):
    snap = snapshot or {}
    if str(snap.get("symbol") or "").upper() != "XAUUSD":
        return False
    prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
    sources = prices.get("sources") if isinstance(prices.get("sources"), list) else []
    source_names = {str(x.get("source") or "") for x in sources if isinstance(x, dict)}
    return "金十Quote" in source_names


def push_allowed(tier, hits, snapshot=None):
    if not STRICT_PUSH_MODE:
        return True, "常规推送模式"
    score = max_level_score(hits)
    data_q = str((snapshot or {}).get("quality") or "C").upper()[:1]
    xau_single_ok = xau_single_quote_ok(snapshot)
    high_priority = any(x.get("priority") == "high" for x in hits or [])
    breached_like = any((x.get("condition") in {"breach", "close_confirm", "combo", "combined"}) or "触发" in str(x.get("condition_reason", "")) for x in hits or [])
    if tier == "critical":
        if score >= MIN_CRITICAL_LEVEL_SCORE and (data_q != "C" or xau_single_ok or score >= 82):
            suffix = " · 单源金十降级" if data_q == "C" and xau_single_ok else ""
            return True, f"紧急且位信{score}%{suffix}"
        return False, f"紧急但确认不足：位信{score}% · 数据{data_q}级"
    if tier == "warning":
        if high_priority and breached_like and score >= MIN_WARNING_LEVEL_SCORE and (data_q != "C" or xau_single_ok):
            suffix = " · 单源金十降级" if data_q == "C" and xau_single_ok else ""
            return True, f"高优先级触发且位信{score}%{suffix}"
        return False, f"未达到强确认：位信{score}% · 数据{data_q}级"
    if tier == "invalidated":
        if high_priority and score >= MIN_WARNING_LEVEL_SCORE:
            return True, f"高优先级计划失效且位信{score}%"
        return False, f"失效提醒降噪：位信{score}%"
    return False, "严格模式不推送接近/过期提醒"

def mark_levels(raw, symbol, names, status):
    levels = raw.get("symbols", {}).get(symbol, {}).get("levels", []) if isinstance(raw.get("symbols"), dict) else raw.get("levels", [])
    if not isinstance(levels, list):
        for name in names:
            raw.pop(name, None)
        raw["updated"] = now_local().isoformat()
        return raw
    for item in levels:
        if item.get("name") in names:
            item["status"] = status
            item["status_time"] = now_local().isoformat()
    if isinstance(raw.get("symbols"), dict):
        raw["symbols"][symbol]["updated"] = now_local().isoformat()
    else:
        raw["updated"] = now_local().isoformat()
    return raw


def append_event(event):
    ev = read_json(EVENT_FILE, [])
    ev.append(event)
    save_json(EVENT_FILE, ev[-300:])


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def maybe_request_refresh(raw, symbol, block, tier, hits):
    levels = [x for x in raw.get("symbols", {}).get(symbol, {}).get("levels", [])] if isinstance(raw.get("symbols"), dict) else raw.get("levels", [])
    active_count = sum(1 for x in levels if x.get("status", "active") == "active")
    reasons = []
    if active_count < 2:
        reasons.append("活跃关键位少于2个")
    if tier == "critical":
        reasons.append("紧急触发后需要重算结构")
    if len(hits) >= 2:
        reasons.append("同轮多关键位触发")
    if not reasons:
        return None
    req = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": block.get("plan_id"), "reasons": reasons, "active_levels": active_count, "hit_levels": [x.get("name") for x in hits], "status": "pending"}
    append_jsonl(REFRESH_FILE, req)
    if isinstance(raw.get("symbols"), dict):
        raw["symbols"][symbol]["needs_structure_refresh"] = True
        raw["symbols"][symbol]["refresh_reason"] = "；".join(reasons)
    else:
        raw["needs_structure_refresh"] = True
        raw["refresh_reason"] = "；".join(reasons)
    return req


def should_skip(last, tier, keys):
    now_ts = time.time()
    if now_ts - last.get("any", 0) < COOLDOWN.get(tier, 300):
        return True
    if any(now_ts - last.get(key, 0) < SAME_LV_CD for key in keys):
        return True
    return alert_budget_exhausted(last, tier, now_ts)


def alert_budget_exhausted(last, tier, now_ts=None):
    now_ts = now_ts or time.time()
    history = [x for x in last.get("history", []) if now_ts - x.get("time", 0) < ALERT_BUDGET_WINDOW]
    last["history"] = history
    tier_count = sum(1 for x in history if x.get("tier") == tier)
    if tier_count >= ALERT_BUDGET_BY_TIER.get(tier, 3):
        return True
    return len(history) >= ALERT_BUDGET_GLOBAL and tier != "critical"


def touch_last(last, keys, tier=None):
    now_ts = time.time()
    last["any"] = now_ts
    for key in keys:
        last[key] = now_ts
    if tier:
        history = [x for x in last.get("history", []) if now_ts - x.get("time", 0) < ALERT_BUDGET_WINDOW]
        history.append({"time": now_ts, "tier": tier, "keys": keys[:3]})
        last["history"] = history[-ALERT_BUDGET_GLOBAL:]


def append_system_event(row):
    row = dict(row)
    row.setdefault("time", now_local().isoformat())
    row.setdefault("schema", "system_event_v1")
    SYSTEM_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SYSTEM_EVENT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def source_stale(snapshot):
    try:
        ts_raw = (snapshot or {}).get("time")
        if not ts_raw:
            return True, "快照时间缺失"
        age = (now_local() - datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).astimezone()).total_seconds()
        if age > MAX_STALE_SECONDS:
            return True, f"快照过旧：{age:.0f}s"
    except Exception:
        return True, "快照时间无法解析"
    return False, ""


def anomaly_check(symbol, price, snapshot, state):
    issues = []
    stale, stale_reason = source_stale(snapshot)
    if stale:
        issues.append(stale_reason)
    quality = str((snapshot or {}).get("quality") or "C").upper()[:1]
    price_sources = ((snapshot or {}).get("prices") or {}).get("sources") or []
    source_names = "+".join(str(x.get("source", "")) for x in price_sources if isinstance(x, dict))
    single_quote_ok = symbol == "XAUUSD" and isinstance(price, (int, float)) and "金十Quote" in source_names
    fail_key = f"{symbol}:data_fail_count"
    # XAU 单源金十报价是当前允许的正常降级状态；不能把它当作行情失效反复熔断。
    if (quality == "C" and not single_quote_ok) or not isinstance(price, (int, float)):
        state[fail_key] = int(state.get(fail_key, 0) or 0) + 1
    else:
        state[fail_key] = 0
    if int(state.get(fail_key, 0) or 0) >= DATA_FAILURE_LIMIT:
        issues.append(f"连续{state[fail_key]}次数据C级/不可用")
    last_prices = state.setdefault("last_prices", {})
    prev = last_prices.get(symbol)
    if isinstance(prev, (int, float)) and isinstance(price, (int, float)) and prev > 0:
        jump = abs(price - prev) / prev * 100
        limit = MAX_PRICE_JUMP_PCT.get(symbol, 1.0)
        if jump > limit:
            issues.append(f"10s价格跳变{jump:.2f}%超过{limit:.2f}%")
    if isinstance(price, (int, float)):
        last_prices[symbol] = float(price)
    if issues:
        append_system_event({"type": "market_data_anomaly", "symbol": symbol, "price": price, "quality": quality, "issues": issues})
        return False, "；".join(issues)
    return True, ""


def render_message(head, symbol, price, plan_id, cycle, hits, urgency, cvd=None, cvd_quality=None, reason=None, tier="info", risk_text=None, derivatives_text=None, confidence_text=None):
    lines = [head]
    lines.append(f"① {lab('品种')}{symbol}")
    lines.append(f"② {lab('价格')}`{price:.0f}`")
    lines.append(f"③ {lab('置信')}{confidence_text or 'C级 · 0% · 未验证'}")
    lines.append(f"④ {lab('计划')}{display_plan(plan_id, symbol)}")
    lines.append(f"⑤ {lab('现状')}{situation_text(tier)}")
    start = 6
    if cvd is not None:
        lines.append(f"⑥ {lab('CVD')}{cvd} · {cvd_quality}")
        start = 7
    if derivatives_text:
        lines.append(f"{seq(start)} {lab('衍生')}{derivatives_text}")
        start += 1
    if risk_text:
        lines.append(f"{seq(start)} {lab('风控')}{risk_text}")
        start += 1
    if hits:

        lines.append("—— 触发细节 ——")
    for i, item in enumerate(hits, start=start):
        lines.append(format_hit(price, item, i).rstrip())
    tail_idx = start + len(hits)
    if reason:
        lines.append(f"{seq(tail_idx)} {lab('原因')}{reason}")
        tail_idx += 1
    lines.append("")
    lines.append("—— 执行结论 ——")
    lines.append(f"{seq(tail_idx)} {lab('周期')}{cycle}")
    lines.append(f"{lab('动作')}{urgency}")
    lines.append(f"{lab('提示')}说「分析 {symbol.replace('USDT', '')}」刷新完整卡")
    return "\n".join(lines)


def process_block(raw, symbol, block, state):
    if block.get("monitor_enabled") is False:
        return raw, False
    price = get_price(symbol, block)
    if price is None:
        return raw, False
    items = [x for x in normalize_levels(block) if x.get("status", "active") == "active"]
    if not items:
        return raw, False

    plan_id = block.get("plan_id") or raw.get("plan_id") or f"{symbol}-manual"
    cycle = block.get("analysis_cycle") or raw.get("analysis_cycle") or "—"
    last = state.setdefault("last_alerts", {})
    snapshot = ts.source_snapshot(symbol, {"plan_id": plan_id, "cycle": cycle, "price_at_analysis": block.get("price_at_analysis")}) if ts else None
    data_ok, data_reason = anomaly_check(symbol, price, snapshot, state)
    if not data_ok:
        log(f"数据异常熔断 {symbol}: {data_reason}")
        record_noise(state, symbol, "system", "数据异常熔断：" + data_reason)
        return raw, False
    data_quality = (snapshot or {}).get("quality", "C")
    requested_risk = None
    if ts:
        try:
            requested_risk = ts.template_risk_limit(symbol)
        except Exception:
            requested_risk = None
    gate = ts.risk_gate(data_quality=data_quality, requested_risk=requested_risk) if ts else {"allowed": True, "tier": "未知", "max_risk_usd": 0, "reasons": ["风控模块未加载"]}
    risk_text = ts.format_risk_gate(gate) if ts else "风控模块未加载"
    derivatives_text = derivatives_line(snapshot)
    confidence_text = confidence_line(snapshot)

    expired = [x for x in items if is_expired(block, x)]
    invalidated = []
    for item in items:
        hit, reason = eval_invalid(symbol, item.get("invalid_if"))
        if hit:
            copied = dict(item)
            copied["invalid_reason"] = reason
            invalidated.append(copied)

    if expired:
        keys = [f"{symbol}:{plan_id}:{x['name']}:expired" for x in expired]
        if not should_skip(last, "expired", keys):
            raw = mark_levels(raw, symbol, {x["name"] for x in expired}, "expired")
            for hit in expired:
                hit["live_level_confidence"] = live_level_confidence(hit, "expired", snapshot=snapshot)
            allow_push, push_reason = push_allowed("expired", expired, snapshot)
            pushed = False
            if allow_push:
                msg = render_message(f"🔵 {symbol} 监控位过期", symbol, price, plan_id, cycle, expired, "旧位已过期，不再按旧计划触发", tier="expired", risk_text=risk_text, derivatives_text=derivatives_text, confidence_text=confidence_text)
                pushed = push(msg)
            else:
                log(f"降噪不推送 {symbol} expired: {push_reason}")
                record_noise(state, symbol, "expired", push_reason)
            event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": "expired", "tier": "expired", "price": price, "levels": event_level_rows(expired), "risk_gate": gate, "confidence": confidence_payload(snapshot), "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": True, "schema": "v2.3"}
            append_event(event)
            if ts:
                ts.log_event(event)
            touch_last(last, keys, "expired")
            return raw, True

    if invalidated:
        keys = [f"{symbol}:{plan_id}:{x['name']}:invalidated" for x in invalidated]
        if not should_skip(last, "invalidated", keys):
            raw = mark_levels(raw, symbol, {x["name"] for x in invalidated}, "invalidated")
            reason = "；".join(x.get("invalid_reason", "") for x in invalidated if x.get("invalid_reason"))
            for hit in invalidated:
                hit["live_level_confidence"] = live_level_confidence(hit, "invalidated", snapshot=snapshot, condition_reason=hit.get("invalid_reason"))
            allow_push, push_reason = push_allowed("invalidated", invalidated, snapshot)
            pushed = False
            if allow_push:
                msg = render_message(f"🔵 {symbol} 计划失效", symbol, price, plan_id, cycle, invalidated, "旧计划已失效，等新分析刷新", reason=reason, tier="invalidated", risk_text=risk_text, derivatives_text=derivatives_text, confidence_text=confidence_text)
                pushed = push(msg)
            else:
                log(f"降噪不推送 {symbol} invalidated: {push_reason}")
                record_noise(state, symbol, "invalidated", push_reason)
            event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": "invalidated", "tier": "invalidated", "price": price, "levels": event_level_rows(invalidated), "risk_gate": gate, "confidence": confidence_payload(snapshot), "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": True, "schema": "v2.3"}
            append_event(event)
            if ts:
                ts.log_event(event)
            touch_last(last, keys, "invalidated")
            return raw, True

    breached, near = [], []
    for item in items:
        level = item["level"]
        d = abs(price - level) / level
        ready, reason_text = condition_ready(item.get("condition", "near_or_breach"), price, level, item, symbol)
        if not ready:
            continue
        copied = dict(item)
        copied["condition_reason"] = reason_text
        if d < BREACH_PCT or item.get("condition") in {"breach", "close_confirm"}:
            breached.append(copied)
        elif d < NEAR_PCT:
            near.append(copied)

    if not breached and not near:
        return raw, False

    cvd, cvd_quality = get_cvd(symbol)
    high_priority_breach = any(x.get("priority") == "high" for x in breached)
    cvd_break = any(x.get("type") in ("vwap_reclaim_filter", "retest_short", "break_low", "liquidity_sweep_low") for x in breached) and cvd == "卖"
    if len(breached) >= 2 or (high_priority_breach and cvd_break):
        tier, head = "critical", f"🔴🔴 {symbol} 紧急关键位"
    elif breached:
        tier, head = "warning", f"🔴 {symbol} 关键位触发"
    else:
        tier, head = "info", f"🟡 {symbol} 接近计划位"
    urgency = "立即按计划确认" if tier == "critical" else ("尽快看5m确认" if tier == "warning" else "可等待触发")
    if not gate.get("allowed", True):
        urgency = "风控禁止开新仓，只允许观察或管理已有仓位"

    hits = breached + near
    for hit in hits:
        hit["live_level_confidence"] = live_level_confidence(hit, tier, cvd=cvd, cvd_quality=cvd_quality, condition_reason=hit.get("condition_reason"), snapshot=snapshot)
    keys = [f"{symbol}:{plan_id}:{x['name']}:{tier}" for x in hits]
    if should_skip(last, tier, keys):
        return raw, False

    allow_push, push_reason = push_allowed(tier, hits, snapshot)
    pushed = False
    if allow_push:
        msg = render_message(head, symbol, price, plan_id, cycle, hits, urgency, cvd=cvd, cvd_quality=cvd_quality, tier=tier, risk_text=risk_text, derivatives_text=derivatives_text, confidence_text=confidence_text)
        pushed = push(msg)
    else:
        log(f"降噪不推送 {symbol} {tier}: {push_reason}")
        record_noise(state, symbol, tier, push_reason)

    if breached:
        raw = mark_levels(raw, symbol, {x["name"] for x in breached}, "triggered")
    refresh_req = maybe_request_refresh(raw, symbol, block, tier, hits)
    if refresh_req:
        log(f"结构刷新请求: {symbol} {refresh_req['reasons']}")
    event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": f"{tier}_{'breach' if breached else 'near'}", "tier": tier, "price": price, "levels": event_level_rows(hits), "cvd": cvd, "cvd_quality": cvd_quality, "risk_gate": gate, "confidence": confidence_payload(snapshot), "refresh_request": refresh_req, "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": True, "schema": "v2.3"}
    append_event(event)
    if ts:
        ts.log_event(event)
    touch_last(last, keys, tier)
    return raw, True


def main():
    if ts:
        ts.ensure_files()
    if not acquire_lock():
        return
    try:
        log(f"实时监控 v6.3 | {POLL}s | 接近{NEAR_PCT*100:.1f}% | 突破{BREACH_PCT*100:.1f}%")
        state = read_json(STATE_FILE, {"last_alerts": {}})
        while True:
            try:
                raw = read_json(LEVELS_FILE, {})
                changed = False
                for symbol, block in list(iter_symbol_blocks(raw)):
                    write_heartbeat("running", symbol)
                    raw, block_changed = process_block(raw, symbol, block, state)
                    changed = changed or block_changed

                if changed:
                    save_json(LEVELS_FILE, raw)
                    save_json(STATE_FILE, state)
                time.sleep(POLL)
            except KeyboardInterrupt:
                log("停止")
                break
            except Exception as e:
                log(f"错误: {e}")
                time.sleep(POLL)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
