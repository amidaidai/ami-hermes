#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 多品种关键位实时守卫 — 0.5s REST 轮询，读 keylevels_config.json（多品种多顶点）。

配置(data/keylevels_config.json):
{
  "symbols": {
    "BTCUSDT": {
      "ws_price": "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT",
      "levels": [
        {"name": "磁吸↑·周五伦高", "price": 79864, "note": "反抽短空"},
        {"name": "磁吸↓·周五伦低", "price": 78400, "note": "企稳试多"}
      ]
    }
  }
}

价格自上次巡检以来穿过任一 level → 写 data/trigger_{symbol}.json，并直接发一条“到价请看图”提醒。
防刷屏：每 level 独立 30 分钟冷却。守护挂了由 keylevel_guard_watchdog 自动拉起。
"""
import json
import hashlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import atomic_write_json

_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
CONFIG_FILE = DATA / "keylevels_config.json"
STATE_FILE = DATA / ".keylevel_guard_state.json"
HEARTBEAT_FILE = DATA / ".keylevel_guard_heartbeat.json"
LOCK_FILE = DATA / ".keylevel_guard.lock"
TZ = timezone(timedelta(hours=8))

COOLDOWN_SECONDS = 1800   # 每 level 独立冷却 30 分钟
POLL_SECONDS = 0.5
PRICE_ALERTS_ENABLED = True  # 用户明确授权：只提醒到价，不做方向判断/下单
PRICE_ALERT_TARGET = "telegram:-1003733144325:386"

import urllib.request


def ts():
    return time.time()


def now_bjt_iso():
    from datetime import datetime, timezone, timedelta
    return datetime.now(tz=timezone(timedelta(hours=8))).isoformat()


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {"symbols": {}}


def config_revision() -> str:
    """返回当前批准监测配置的内容版本，随事件写出以阻断旧配置误触发。"""
    try:
        return hashlib.sha256(CONFIG_FILE.read_bytes()).hexdigest()[:16]
    except OSError:
        return "missing"


def level_is_active(level, now_epoch):
    """只允许显式启用且未过期的批准关键位进入监控。"""
    if level.get("enabled", True) is False:
        return False
    expires = level.get("valid_until") or level.get("expires_at")
    if not expires:
        return True
    try:
        from datetime import datetime
        if isinstance(expires, (int, float)):
            return now_epoch <= float(expires)
        return now_epoch <= datetime.fromisoformat(str(expires).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return False


def structure_review_is_current(config, now_epoch=None) -> bool:
    """Reject all approved levels after the policy's maximum structure age."""
    config = config if isinstance(config, dict) else {}
    policy = config.get("auto_approval_policy") or {}
    if not isinstance(policy, dict) or policy.get("max_structure_age_hours") is None:
        return True
    try:
        max_hours = float(policy["max_structure_age_hours"])
        reviewed_raw = policy.get("structure_reviewed_at") or policy.get("authorized_at")
        reviewed = datetime.fromisoformat(str(reviewed_raw).replace("Z", "+00:00"))
        if reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=TZ)
        now_value = time.time() if now_epoch is None else float(now_epoch)
        return max_hours > 0 and now_value <= reviewed.timestamp() + max_hours * 3600.0
    except (TypeError, ValueError, OverflowError):
        return False


def active_approved_level_count(config=None, now_epoch=None) -> int:
    """Count currently valid, explicitly approved levels in the sole source."""
    config = config if isinstance(config, dict) else load_config()
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if not structure_review_is_current(config, now_epoch):
        return 0
    total = 0
    for block in (config.get("symbols", {}) or {}).values():
        if not isinstance(block, dict):
            continue
        for level in block.get("levels", []) or []:
            if isinstance(level, dict) and level_is_active(level, now_epoch):
                total += 1
    return total


def approved_level_inventory(config=None) -> dict:
    """Count configured levels without applying expiry or structure-review gates."""
    config = config if isinstance(config, dict) else load_config()
    enabled = 0
    disabled = 0
    for block in (config.get("symbols", {}) or {}).values():
        if not isinstance(block, dict):
            continue
        for level in block.get("levels", []) or []:
            if not isinstance(level, dict):
                continue
            if level.get("enabled", True) is False:
                disabled += 1
            else:
                enabled += 1
    return {
        "enabled": enabled,
        "disabled": disabled,
        "configured": enabled + disabled,
    }


def config_health(config=None, now_epoch=None) -> dict:
    """Return a machine-readable health result.

    - ok: at least one enabled, unexpired, structure-current level
    - idle: levels exist but the user has silenced every one (enabled=false)
    - degraded: zero active levels for any other reason (expiry / no config)
    """
    config = config if isinstance(config, dict) else load_config()
    count = active_approved_level_count(config, now_epoch)
    inventory = approved_level_inventory(config)
    if count > 0:
        status = "ok"
    elif inventory["configured"] > 0 and inventory["enabled"] == 0:
        status = "idle"
    else:
        status = "degraded"
    return {
        "status": status,
        "active_approved_levels": count,
        "configured_levels": inventory["configured"],
        "enabled_levels": inventory["enabled"],
        "disabled_levels": inventory["disabled"],
        "source": str(CONFIG_FILE),
        "checked_at": now_bjt_iso(),
    }


def get_price(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
            return float(d.get("price") or d.get("lastPrice"))
    except Exception:
        return None


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(s):
    atomic_write_json(STATE_FILE, s, indent=None)


def split_trigger(symbol, level, price, direction, *, revision):
    """写 data/trigger_{symbol}.json 供 agent 读取。"""
    f = DATA / f"trigger_{symbol}.json"
    try:
        with open(f) as _f:
            data = json.load(_f)
    except Exception:
        data = {}
    data["event_id"] = f"{symbol}-{level['name']}-{int(time.time() * 1000)}"
    data["event_type"] = "keylevel_cross"
    data["triggered"] = True
    data["symbol"] = symbol
    data["level"] = level["name"]
    data["level_price"] = level["price"]
    data["price"] = price
    # direction 仅保留兼容字段；最终方向必须由分析层重新裁决。
    data["direction"] = "neutral"
    data["cross_direction"] = direction
    data["tv_symbol"] = level.get("tv_symbol") or (
        f"BINANCE:{symbol}.P" if symbol.upper().endswith("USDT") else symbol
    )
    data["config_revision"] = revision
    data["level_source"] = level.get("source", "keylevels_config")
    data["level_valid_until"] = level.get("valid_until") or level.get("expires_at")
    data["event_class"] = "price_cross_only"
    data["ts"] = now_bjt_iso()
    data["analysis_required"] = True
    data["analysis_status"] = "pending"
    data["source"] = "binance_rest"
    data["cooldown_until"] = ts() + COOLDOWN_SECONDS
    atomic_write_json(f, data)


def send_price_arrival_alert(symbol, level, price, direction):
    """直接通知到价；禁止在守卫层加入多空判断或执行价格。"""
    if not PRICE_ALERTS_ENABLED:
        return False, "disabled"
    text = (
        f"○ {symbol} 到价：{price:,.0f}，触及{level.get('name', '关键位')} "
        f"{float(level['price']):,.0f}\n"
        "请查看 TradingView 15m 图表，自己确认结构。\n"
        "仅提醒，不代表方向，不自动下单。"
    )
    try:
        from telegram_direct import send_telegram_direct
        return send_telegram_direct(PRICE_ALERT_TARGET, text, timeout=10)
    except Exception as exc:
        log(f"ALERT_SEND_FAILED {type(exc).__name__}")
        return False, type(exc).__name__


def acquire_instance_lock():
    """确保 Windows/Linux 上只有一个多品种守护实例。"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            handle.write("0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        handle.close()
        raise SystemExit("keylevel_guard already running")
    return handle


def heartbeat(status):
    hb = {"ts": now_bjt_iso(), "pid": os.getpid(), "status": status}
    atomic_write_json(HEARTBEAT_FILE, hb, indent=None)


def log(m):
    safe = m.encode("ascii", "replace").decode("ascii")
    print(safe, flush=True)


def main_loop():
    last_price_by_sym = {}   # symbol -> last price
    persisted = load_state()
    triggered = persisted.get("triggered", {}) if isinstance(persisted, dict) else {}
    last_price_by_sym = persisted.get("last_price", {}) if isinstance(persisted, dict) else {}
    log(f"multi-symbol keylevel guard started PID={os.getpid()}")
    heartbeat("running")

    while True:
        t0 = time.time()
        cfg = load_config()   # 每次热读配置，加位/删位无需重启
        revision = str(cfg.get("config_revision") or config_revision())
        now = ts()

        if not structure_review_is_current(cfg, now):
            heartbeat("structure_review_required")
            time.sleep(POLL_SECONDS)
            continue

        for sym, c in cfg.get("symbols", {}).items():
            url = c.get("ws_price") or f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}"
            price = get_price(url)
            if price is None:
                continue
            last = last_price_by_sym.get(sym)
            lvls = c.get("levels", [])
            for lv in lvls:
                if not isinstance(lv, dict) or not level_is_active(lv, now):
                    continue
                lvl = float(lv["price"])
                crossed = None
                if last is not None:
                    if last < lvl <= price:
                        crossed = "up"
                    elif last >= lvl > price:
                        crossed = "down"
                if crossed:
                    key = f"{sym}:{lv['name']}"
                    info = triggered.get(key, {})
                    cool_until = info.get("cool_until", 0.0)
                    # 所有结构统一冷却：冷却期内不因反向穿越而再次刷屏。
                    # 只有冷却结束后重新穿越，才允许再次提醒。
                    if now >= cool_until:
                        log(f"TRIGGER {sym} {lv['name']} {crossed} price={price:,.1f}")
                        split_trigger(sym, lv, price, crossed, revision=revision)
                        ok, reason = send_price_arrival_alert(sym, lv, price, crossed)
                        log(f"ALERT {'OK' if ok else 'FAIL'} {sym} {lv['name']} {reason}")
                        triggered[key] = {"dir": crossed, "cool_until": now + COOLDOWN_SECONDS}
                        save_state({"triggered": triggered, "last_price": last_price_by_sym})
            last_price_by_sym[sym] = price

        save_state({"triggered": triggered, "last_price": last_price_by_sym})
        heartbeat("running")

        elapsed = time.time() - t0
        if elapsed < POLL_SECONDS:
            time.sleep(POLL_SECONDS - elapsed)


if __name__ == "__main__":
    _instance_lock = acquire_instance_lock()
    try:
        main_loop()
    except KeyboardInterrupt:
        log("Shutdown")
