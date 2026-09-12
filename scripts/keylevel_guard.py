#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 多品种关键位实时守卫 — 0.5s REST 轮询，读 keylevels_config.json（多品种多顶点）。

配置(data/keylevels_config.json):
{
  "symbols": {
    "BTCUSDT": {
      "ws_price": "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT",
      "levels": [
        {"name": "结构·熊FVG/OB", "price": 76938, "push_tier": "critical"},
        {"name": "价值区·VAH",    "price": 77310, "push_tier": "event"}
      ]
    }
  }
}

## 两个正交的开关（2026-09-12 解耦，勿再混用）

- `enabled`   = 是否**参与监控与结构复核**。false = 彻底不监控。
- `push_tier` = 是否**推送、多久推**。与 enabled 无关。

之所以必须解耦：结构复核（keylevels_structure_review）的盖章条件是
`checked >= MIN_VALID and valid == checked`，而它只统计 `enabled=True` 的位。
若为了"少推"而把位设成 `enabled=false`，会让复核样本不足 → 永不盖章 →
24h 结构闸落下 → 监控全停。正确做法是 **enabled 保持 true、只降 push_tier**。

## 推送分级

| tier | 冷却 | 幅度门 | 行为 |
|---|---|---|---|
| critical | 4h | 0.25% | 结构位(FVG/OB)/HTF 磁吸 → 即时推 |
| event    | 6h | 0.35% | 价值区边界(VAH/VAL) → 即时推 |
| silent   | —  | —     | 只记 digest，不推、不触发分析 |

另有两道全局限流（跨位生效，防"一次行情连穿多个位"连环推）：
- 任意两次推送最小间隔 GLOBAL_MIN_GAP_SECONDS
- 每小时上限 GLOBAL_MAX_PER_HOUR

价格自上次巡检以来穿过任一 level → 写 data/trigger_{symbol}.json（仅 critical/event），
并按分级决定是否直发一条"到价请看图"提醒。
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
DIGEST_FILE = DATA / "keylevel_digest.jsonl"
TZ = timezone(timedelta(hours=8))

POLL_SECONDS = 0.5
PRICE_ALERTS_ENABLED = True  # 用户明确授权：只提醒到价，不做方向判断/下单
PRICE_ALERT_TARGET = "telegram:-1003733144325:386"

# ── 推送分级（2026-09-12）─────────────────────────────────────────────
# cooldown: 同一位两次推送的最小间隔（秒）；min_move_pct: 相对上次推送价的幅度门
TIER_POLICY = {
    "critical": {"cooldown": 4 * 3600, "min_move_pct": 0.25},
    "event": {"cooldown": 6 * 3600, "min_move_pct": 0.35},
}
DEFAULT_PUSH_TIER = "event"      # 未标注 tier 的位按 event 处理
SILENT_TIERS = {"silent", "off", "none", "digest"}
GLOBAL_MIN_GAP_SECONDS = 1800    # 任意两次推送最小间隔 30 分钟
GLOBAL_MAX_PER_HOUR = 3          # 每小时推送硬上限
HYSTERESIS_PCT = 0.15            # 触发后须离开该位 ±0.15% 才重新武装
DIGEST_MIN_INTERVAL = 300        # 同一 key 的 digest 最小间隔（秒）
COOLDOWN_SECONDS = 6 * 3600      # 兼容旧引用：未分级时的默认冷却

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


def level_push_tier(level) -> str | None:
    """返回该位的推送级别；None 表示只记录、不推送。

    这是**唯一**决定推送与否的入口 —— `enabled` 只控制监控参与度，
    不得用它来表达"别推给我"，否则会让结构复核样本不足。
    """
    if not isinstance(level, dict):
        return None
    if level.get("push") is False:
        return None
    raw = str(level.get("push_tier") or DEFAULT_PUSH_TIER).strip().lower()
    if raw in SILENT_TIERS:
        return None
    return raw if raw in TIER_POLICY else DEFAULT_PUSH_TIER


def tier_policy(tier: str | None) -> dict:
    return TIER_POLICY.get(str(tier), TIER_POLICY[DEFAULT_PUSH_TIER])


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
    push_enabled = 0
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
                if level_push_tier(level) is not None:
                    push_enabled += 1
    return {
        "enabled": enabled,
        "disabled": disabled,
        "configured": enabled + disabled,
        "push_enabled": push_enabled,
    }


def monitoring_intent(config=None) -> str:
    """返回配置里显式声明的监控意图，用于区分「用户主动静默」与「失效」。

    - "active"     : 至少一个 enabled 位（正常监控）
    - "user_silenced": 全部 enabled=false，且顶层显式声明是用户要求静默
    - "retired"    : 顶层显式声明已退役
    - "undeclared" : 全部 enabled=false 但没有显式声明 → 视为异常，预检应报错
    """
    config = config if isinstance(config, dict) else load_config()
    declared = str(config.get("monitoring_status") or "").strip().lower()
    if declared in {"retired"}:
        return "retired"
    inventory = approved_level_inventory(config)
    if inventory["enabled"] > 0:
        return "active"
    if declared in {"user_silenced", "silent"}:
        return "user_silenced"
    policy = config.get("auto_approval_policy") or {}
    if isinstance(policy, dict) and policy.get("user_silenced") is True:
        return "user_silenced"
    return "undeclared"


def config_health(config=None, now_epoch=None) -> dict:
    """Return a machine-readable health result.

    - ok: at least one enabled, unexpired, structure-current level
    - idle: levels exist but every one is silenced (enabled=false)
    - degraded: zero active levels for any other reason (expiry / no config)

    `idle` 只描述"有没有在监控"，**不代表健康**；调用方必须结合
    `monitoring_intent` 判断这是用户主动静默还是意外失效。
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
        "push_enabled_levels": inventory["push_enabled"],
        "monitoring_intent": monitoring_intent(config),
        "structure_review_current": structure_review_is_current(config, now_epoch),
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


def append_digest(entries) -> None:
    """把未推送（silent 级）的到价事件记入 digest，不打扰用户但留痕。"""
    if not entries:
        return
    try:
        with open(DIGEST_FILE, "a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except OSError as exc:
        log(f"DIGEST_WRITE_FAILED {type(exc).__name__}")


def _record_digest(triggered, digest_round, key, now, payload) -> None:
    """把"被抑制的到价"记入 digest，但按 key 节流。

    守卫是 0.5s 轮询：若每次轮询都写 digest，一个被幅度门挡住的位会
    每秒写两条，几分钟就把 jsonl 刷到几万行。这里按 DIGEST_MIN_INTERVAL
    对同一 key 节流，既留痕又不淹日志。
    """
    info = triggered.get(key)
    if not isinstance(info, dict):
        info = {}
    last = float(info.get("last_digest", 0.0) or 0.0)
    if now - last < DIGEST_MIN_INTERVAL:
        return
    digest_round.append(payload)
    triggered[key] = {**info, "last_digest": now}


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
    data["push_tier"] = level_push_tier(level) or "silent"
    data["event_class"] = "price_cross_only"
    data["ts"] = now_bjt_iso()
    data["analysis_required"] = True
    data["analysis_status"] = "pending"
    data["source"] = "binance_rest"
    data["cooldown_until"] = ts() + tier_policy(level_push_tier(level))["cooldown"]
    atomic_write_json(f, data)


def _format_alert(symbol, price, hits) -> str:
    """单条到价提醒文本（可含多位聚合）。守卫层禁止方向判断与执行价。"""
    lines = []
    if len(hits) == 1:
        h = hits[0]
        lines.append(
            f"○ {symbol} 到价：{price:,.0f}，触及{h['name']} "
            f"{float(h['price']):,.0f}"
        )
        lines.append(f"级别：{h['tier']} · 冷却 {int(tier_policy(h['tier'])['cooldown'] / 3600)}h")
    else:
        lines.append(f"○ {symbol} 到价：{price:,.0f}，同时触及 {len(hits)} 个位")
        for h in hits:
            lines.append(f"· {h['tier']} {h['name']} {float(h['price']):,.0f}")
    lines.append("请查看 TradingView 15m 图表，自己确认结构。")
    lines.append("仅提醒，不代表方向，不自动下单。")
    return "\n".join(lines)


def send_price_arrival_alert(symbol, price, hits):
    """直接通知到价；禁止在守卫层加入多空判断或执行价格。

    走 telegram_reliable.push_tg_rich 统一入口，复用其夜间静默（23:00–08:00）
    与去重/重试逻辑；失败落 pending 队列，不在这里循环重试。
    """
    if not PRICE_ALERTS_ENABLED or not hits:
        return False, "disabled"
    text = _format_alert(symbol, price, hits)
    try:
        from telegram_reliable import push_tg_rich
        return push_tg_rich(PRICE_ALERT_TARGET, text)
    except Exception as exc:
        log(f"ALERT_SEND_FAILED {type(exc).__name__}")
        return False, type(exc).__name__


def global_rate_limit_ok(recent_pushes, now):
    """跨位全局限流：最小间隔 + 每小时上限。"""
    pushes = [float(t) for t in (recent_pushes or []) if isinstance(t, (int, float))]
    pushes = [t for t in pushes if now - t < 24 * 3600]
    if pushes and now - max(pushes) < GLOBAL_MIN_GAP_SECONDS:
        return False, "global_min_gap", pushes
    if len([t for t in pushes if now - t < 3600]) >= GLOBAL_MAX_PER_HOUR:
        return False, "global_hourly_cap", pushes
    return True, "", pushes


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


def evaluate_symbol(sym, block, last, price, now, triggered):
    """评估一个品种本轮所有位的穿越，返回 (digest_entries, push_candidates)。

    纯函数：不发送、不限流、不落盘 —— 便于对「降噪是否生效」做确定性模拟。
    会就地更新 `triggered`（冷却 / 武装状态 / 幅度锚定价），因为那是守卫的持续状态。

    降噪四件套都在这里叠加：
      1. push_tier 分级 → None 的位根本不进候选
      2. 同 key 冷却 → 冷却期内不重复
      3. 幅度门 → 相对上次推送价没走出 min_move_pct 就不打扰
      4. 迟滞带 → 触发后须离位 ±HYSTERESIS_PCT 才重新武装
    同轮多位命中会在调用方聚合成一条消息（第 5 件套）。
    """
    digest_round = []
    push_candidates = []
    levels = block.get("levels") if isinstance(block, dict) else None
    for lv in (levels or []):
        if not isinstance(lv, dict) or not level_is_active(lv, now):
            continue
        try:
            lvl = float(lv["price"])
        except (KeyError, TypeError, ValueError):
            continue
        key = f"{sym}:{lv['name']}"
        info = triggered.get(key, {})
        if not isinstance(info, dict):
            info = {}
        tier = level_push_tier(lv)
        policy = tier_policy(tier)

        # 【1】迟滞带重新武装：按【当前距离】每轮更新，与是否穿越无关。
        # 原因一：穿越发生时价格必然贴在该位上（距离≈0），若只在穿越分支里判迟滞，
        #   armed 永远翻不回 True → 每个位一生只能推一次（2026-09-12 实测踩到）。
        # 原因二：必须放在冷却判定之前 —— 重新武装是"是否允许再次关注该位"，
        #   冷却才是"关注了也不许推"，两者顺序颠倒会让冷区永远无法解除。
        try:
            dist_pct = abs(price - lvl) / lvl * 100.0
        except ZeroDivisionError:
            dist_pct = float("inf")
        if info.get("armed") is False:
            if dist_pct >= HYSTERESIS_PCT:
                info = {**info, "armed": True}
                triggered[key] = info
            else:
                continue    # 未重新武装：本轮忽略（防贴线抖动连发）

        # 【2】同 key 冷却：冷却期内一律不推（含反向穿越）。
        cool_until = float(info.get("cool_until", 0.0) or 0.0)
        if now < cool_until:
            continue

        # 【3】穿越判定
        crossed = None
        if last is not None:
            if last < lvl <= price:
                crossed = "up"
            elif last >= lvl > price:
                crossed = "down"
        if not crossed:
            continue

        if tier is None:
            # silent：不推送、不触发分析，只留 digest 痕迹（按间隔节流）
            _record_digest(triggered, digest_round, key, now, {
                "ts": now_bjt_iso(), "symbol": sym, "level": lv["name"],
                "level_price": lvl, "price": price, "cross": crossed,
                "tier": "silent", "pushed": False, "reason": "silent_tier",
            })
            triggered[key] = {**triggered.get(key, info), "dir": crossed,
                              "armed": False,
                              "cool_until": now + float(policy["cooldown"])}
            continue

        # 幅度门：相对上次推送价，没走出实质幅度就不重复打扰。
        anchor = info.get("anchor_price")
        if anchor:
            try:
                move = abs(price - float(anchor)) / float(anchor) * 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                move = float("inf")
            if move < float(policy["min_move_pct"]):
                _record_digest(triggered, digest_round, key, now, {
                    "ts": now_bjt_iso(), "symbol": sym, "level": lv["name"],
                    "level_price": lvl, "price": price, "cross": crossed,
                    "tier": tier, "pushed": False, "reason": "amplitude_gate",
                })
                continue

        push_candidates.append({
            "name": lv["name"], "price": lvl, "tier": tier,
            "policy": policy, "key": key, "cross": crossed, "level": lv,
        })
    return digest_round, push_candidates


def main_loop():
    persisted = load_state()
    triggered = persisted.get("triggered", {}) if isinstance(persisted, dict) else {}
    last_price_by_sym = persisted.get("last_price", {}) if isinstance(persisted, dict) else {}
    recent_pushes = persisted.get("recent_pushes", []) if isinstance(persisted, dict) else []
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
            if not isinstance(c, dict):
                continue
            url = c.get("ws_price") or f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}"
            price = get_price(url)
            if price is None:
                continue
            last = last_price_by_sym.get(sym)
            # 穿越判定 + 降噪四件套集中在 evaluate_symbol（纯函数，便于模拟验收）
            digest_round, push_candidates = evaluate_symbol(
                sym, c, last, price, now, triggered
            )

            # 同轮聚合：一次行情连穿多个位 → 合并成一条消息。
            if push_candidates:
                ok, reason, recent_pushes = global_rate_limit_ok(recent_pushes, now)
                if ok:
                    hits = [{"name": p["name"], "price": p["price"], "tier": p["tier"]}
                            for p in push_candidates]
                    log(f"TRIGGER {sym} x{len(hits)} price={price:,.1f} "
                        + ",".join(f"{h['tier']}:{h['name']}" for h in hits))
                    for p in push_candidates:
                        split_trigger(sym, p["level"], price, p["cross"], revision=revision)
                    sent, sreason = send_price_arrival_alert(sym, price, hits)
                    log(f"ALERT {'OK' if sent else 'SKIP'} {sym} {sreason}")
                    # silent_night 也算已处理：避免 08:00 后立刻补一堆积压提醒。
                    recent_pushes.append(now)
                    for p in push_candidates:
                        triggered[p["key"]] = {
                            **triggered.get(p["key"], {}),
                            "dir": p["cross"], "armed": False,
                            "cool_until": now + float(p["policy"]["cooldown"]),
                            "anchor_price": price,
                        }
                else:
                    for p in push_candidates:
                        _record_digest(triggered, digest_round, p["key"], now, {
                            "ts": now_bjt_iso(), "symbol": sym, "level": p["name"],
                            "level_price": p["price"], "price": price,
                            "cross": p["cross"], "tier": p["tier"],
                            "pushed": False, "reason": reason,
                        })
                    log(f"RATE_LIMITED {sym} {reason} x{len(push_candidates)}")

            append_digest(digest_round)
            last_price_by_sym[sym] = price

        # 只保留 24h 内的推送时间戳
        recent_pushes = [t for t in recent_pushes if now - float(t) < 24 * 3600]
        save_state({"triggered": triggered, "last_price": last_price_by_sym,
                    "recent_pushes": recent_pushes})
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
