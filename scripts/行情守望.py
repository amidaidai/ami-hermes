#!/usr/bin/env python3
"""实时推送监控 v7.1 — 风控闸门、衍生品摘要、计划闭环、XAU时段过滤。"""

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

# v7.6: Binance 偶发 SSL UNEXPECTED_EOF / 瞬断 → 裸 requests.get 单次失败即返回 None，
# 累积可拖垮主循环判读。共享 Session + 退避重试（社区共识：urllib3 Retry + backoff）。
_HTTP = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _retry = Retry(total=2, backoff_factor=0.5,
                   status_forcelist=(429, 500, 502, 503, 504),
                   allowed_methods=frozenset(["GET"]))
    _HTTP.mount("https://", HTTPAdapter(max_retries=_retry))
except Exception:
    pass


def _http_get(url, params=None, timeout=5, retries=2):
    """带 SSL EOF 兜底的 GET：SSLError/ConnectionError 时短暂退避重试。"""
    last = None
    for attempt in range(retries + 1):
        try:
            return _HTTP.get(url, params=params, timeout=timeout)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            last = e
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise last


try:
    import trading_system as ts
except (ImportError, ModuleNotFoundError, AttributeError):
    ts = None

# v6.4: 接入系统数据桥（Taker B级/多空比 A级）
# v7.1: 接入 session_filter（XAU London/NY时段过滤）
try:
    from system_data_bridge import cvd_dir as bridge_cvd, deriv_text as bridge_deriv, snapshot as bridge_snap, event_ban as bridge_event_ban, dir_flip as bridge_dir_flip
    _HAS_BRIDGE = True
except (ImportError, ModuleNotFoundError, AttributeError):
    _HAS_BRIDGE = False

try:
    from monitor_display import (
            display_name,
            display_plan,
            format_level_block,
            lab,
            seq,
            situation_text,
            SEQ_NUMS,
        )
except (ImportError, ModuleNotFoundError, AttributeError):
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
# 棠溪确认监控运行中；warning/位信门槛降至65，避免智能更新位被永久静默。
# 位信初始分66-74（缺少TradingView+CVD复核）在实时场景+CVD配合上浮后可推到>=65。
MIN_WARNING_LEVEL_SCORE = 65
MIN_CRITICAL_LEVEL_SCORE = 70
NOISE_SUMMARY_WINDOW = 3 * 3600
MAX_STALE_SECONDS = 90
MAX_PRICE_JUMP_PCT = {"BTCUSDT": 1.2, "XAUUSD": 0.6}
DATA_FAILURE_LIMIT = 3
META_KEYS = {"updated", "analysis_cycle", "price_at_analysis", "symbol", "symbols", "levels", "plan_id"}


def now_local():
    return datetime.now().astimezone()

def log(msg):
    ts_ = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts_}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        pass


def read_json(path, default):
    try:
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
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
    except (ValueError, TypeError, OverflowError):
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
    # 非 USDT 对（XAUUSD/GC=F 等）不回退 Binance，直接走兜底
    is_usdt_pair = str(symbol).upper().endswith("USDT")
    if is_usdt_pair:
        try:
            r = _http_get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol}, timeout=5)
            r.raise_for_status()
            return float(r.json()["price"])
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError, KeyError, TypeError) as e:
            log(f"价格错误 {symbol}: {e}")
    if isinstance(block, dict) and isinstance(block.get("price_at_analysis"), (int, float)):
        log(f"价格源不可用 {symbol}: 使用分析价临时兜底")
        return float(block["price_at_analysis"])
    return None


def get_close(symbol, interval):
    if not str(symbol).upper().endswith("USDT"):
        return get_price(symbol)
    try:
        r = _http_get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": 2}, timeout=5)
        r.raise_for_status()
        k = r.json()
        return float(k[-2][4] if len(k) > 1 else k[-1][4])
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError, KeyError, TypeError) as e:
        log(f"收盘价错误 {symbol} {interval}: {e}")
        return None


def get_cvd(symbol):
    if not str(symbol).upper().endswith("USDT"):
        return "不适用", "非加密"
    # v7.3: 优先用真实逐笔 aggTrades（A级），失败回退 1m K线估算（C级）。
    try:
        from cvd_aggtrades import get_cvd_aggtrades
        r = get_cvd_aggtrades(symbol, limit=1000)
        if r.get("quality") == "A级" and r.get("direction") in ("买", "卖", "中性"):
            return r["direction"], "A级"
    except Exception:
        pass
    # 回退：1m K线 taker_buy_volume 估算
    try:
        r = _http_get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": "1m", "limit": 5}, timeout=5)
        r.raise_for_status()
        k = r.json()
        buy = sum(float(x[9]) for x in k)
        total = sum(float(x[7]) for x in k)
        sell = total - buy
        d = buy - sell
        direction = "买" if d > total * 0.1 else ("卖" if d < -total * 0.1 else "中性")
        return direction, "C级"
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError, KeyError, TypeError):
        return "?", "C级"


import queue as _queue
import threading as _threading

# v7.2: 推送异步化 — 主循环绝不被 Telegram 发送阻塞。
# 旧实现用 subprocess.run(timeout=10) 同步发送，且 except 只捕获
# requests.Timeout（subprocess 超时抛 subprocess.TimeoutExpired，根本没被捕获），
# 一次卡死可拖垮 10s 主循环 → 心跳停滞 → 看门狗误判卡死。
# 新实现：push() 只把消息塞进队列立即返回；后台单线程 worker 串行发送，
# 任何超时/异常都在 worker 内吞掉，永不冒泡到主循环。
_PUSH_QUEUE: "_queue.Queue" = _queue.Queue(maxsize=200)
_PUSH_WORKER = None
_PUSH_WORKER_LOCK = _threading.Lock()

# v7.5: 警报推送按品种路由到不同 Telegram 话题（chat -1003733144325）。
#   BTC 警报 → 386 · XAU 警报 → 385 · 其他警报 → 416 · 任务报告 → 846
TG_CHAT = "-1003733144325"
ALERT_TOPIC_DEFAULT = "416"
ALERT_TOPIC_BY_SYMBOL = {
    "BTCUSDT": "386",
    "XAUUSD": "385",
}
REPORT_TOPIC = "846"  # 非警报的任务报告/心跳卡


def alert_target_for(symbol):
    """按品种返回警报话题目标。未知品种回落到 416。"""
    topic = ALERT_TOPIC_BY_SYMBOL.get((symbol or "").upper(), ALERT_TOPIC_DEFAULT)
    return f"telegram:{TG_CHAT}:{topic}"


def report_target():
    return f"telegram:{TG_CHAT}:{REPORT_TOPIC}"


def _send_one(target, msg):
    """单通道发送。仅 Telegram。优先走 Bot API 直连（省子进程开销，超时自包含），
    直连失败（如缺 token）才落到 subprocess → hermes_cli 兜底，同样发 Telegram。
    返回 True 只代表真实发送成功；失败会写日志，不能再假装 push_sent=True。

    安全开关：环境变量 HANGQING_NO_SEND=1 时一律不外发（测试/CI 用），
    避免单元测试或回放把真实消息漏发到 Telegram。"""
    if os.environ.get("HANGQING_NO_SEND") == "1":
        log(f"NO_SEND 拦截 {target}: {str(msg)[:60]}")
        return True
    # Telegram：优先直连 Bot API
    if str(target).startswith("telegram:") or str(target).lstrip("-").split(":")[0].isdigit():
        try:
            from telegram_direct import send_telegram_direct
            ok, reason = send_telegram_direct(target, msg, timeout=10)
            if ok:
                log(f"推送成功 {target}: telegram_direct")
                return True
            log(f"推送失败 {target}: telegram_direct {reason}")
            # 直连失败（如缺 token）→ 落到 subprocess 兜底
        except Exception as e:
            log(f"推送异常 {target}: telegram_direct {type(e).__name__}: {str(e)[:120]}")
    # 兜底：subprocess → hermes_cli（telegram_direct 缺 token 时仍发 Telegram）
    # 6秒×2 = worst-case 阻塞 12s，低于看门狗心跳容忍阈值，避免拖垮主循环
    last_reason = ""
    for attempt in range(2):
        try:
            cp = subprocess.run(
                [sys.executable, "-m", "hermes_cli.main", "send", "-t", target, "-q", msg],
                timeout=6, capture_output=True, text=True
            )
            if cp.returncode == 0:
                log(f"推送成功 {target}: hermes_cli")
                return True
            last_reason = (cp.stderr or cp.stdout or f"returncode={cp.returncode}").strip()[:200]
            log(f"推送失败 {target}: hermes_cli {last_reason}")
        except subprocess.TimeoutExpired:
            last_reason = "hermes_cli timeout"
            log(f"推送超时 {target}: {last_reason}")
        except (OSError, ValueError, requests.Timeout, requests.ConnectionError,
                requests.HTTPError, KeyError, TypeError) as e:
            last_reason = f"{type(e).__name__}: {str(e)[:160]}"
            log(f"推送异常 {target}: {last_reason}")
        if attempt < 1:
            time.sleep(1)
    return False


def _push_worker_loop():
    """后台 worker：串行消费推送队列。永不退出，异常全吞。
    队列元素为 (target, msg)；target 为 None 时回落到默认警报话题 416。"""
    while True:
        try:
            item = _PUSH_QUEUE.get()
        except Exception:
            continue
        if item is None:  # 关停哨兵
            _PUSH_QUEUE.task_done()
            break
        try:
            if isinstance(item, tuple):
                target, msg = item
            else:  # 向后兼容：纯字符串
                target, msg = None, item
            tg_target = target or f"telegram:{TG_CHAT}:{ALERT_TOPIC_DEFAULT}"
            _send_one(tg_target, msg)
        except Exception:
            pass
        finally:
            _PUSH_QUEUE.task_done()


def _ensure_push_worker():
    global _PUSH_WORKER
    with _PUSH_WORKER_LOCK:
        if _PUSH_WORKER is None or not _PUSH_WORKER.is_alive():
            _PUSH_WORKER = _threading.Thread(
                target=_push_worker_loop, name="push-worker", daemon=True
            )
            _PUSH_WORKER.start()


def push(msg, target=None):
    """推送（v7.5 非阻塞 + 按目标路由）：消息入队后立即返回，后台 worker 串行发送。
    target 省略时回落到默认警报话题 416；警报应传 alert_target_for(symbol)，
    任务报告传 report_target()。返回 True 表示已接受/入队，绝不阻塞主循环。"""
    _ensure_push_worker()
    payload = (target, msg)
    try:
        _PUSH_QUEUE.put_nowait(payload)
    except _queue.Full:
        # 队列满（极端情况）：丢弃最旧一条再塞，保证不阻塞
        try:
            _PUSH_QUEUE.get_nowait()
            _PUSH_QUEUE.task_done()
        except _queue.Empty:
            pass
        try:
            _PUSH_QUEUE.put_nowait(payload)
        except _queue.Full:
            return False
    return True


def drain_push_queue(timeout: float = 12.0):
    """阻塞等待队列清空（关停或测试用）。"""
    _ensure_push_worker()
    deadline = time.time() + timeout
    while not _PUSH_QUEUE.empty() and time.time() < deadline:
        time.sleep(0.1)
    return _PUSH_QUEUE.empty()


def pid_alive(pid):
    if not pid:
        return False
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True, timeout=5).stdout
            return str(int(pid)) in out and "No tasks" not in out
        os.kill(int(pid), 0)
        return True
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError, KeyError, TypeError):
        return False


def acquire_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            old_pid = int(lock.get("pid") or 0)
            old_started = lock.get("started")
        except (json.JSONDecodeError, OSError, ValueError, KeyError):
            try:
                old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip() or "0")
                old_started = None
            except (json.JSONDecodeError, OSError, ValueError, KeyError):
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
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        try:
            if LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK_FILE.unlink()
        except (json.JSONDecodeError, OSError, ValueError, KeyError):
            pass
    write_heartbeat("stopped")


# ═══════════════════════════════════════
# v6.7: 模型预测回验（胜率追踪）
# ═══════════════════════════════════════

_PREDICT_VERIFY_COOLDOWN = 30 * 60  # 30分钟
_last_predict_verify = 0

def _verify_predictions_if_needed(state: dict):
    """每30分钟回验一次所有未验证预测"""
    global _last_predict_verify
    now = time.time()
    if now - _last_predict_verify < _PREDICT_VERIFY_COOLDOWN:
        return
    
    _last_predict_verify = now
    
    try:
        sys.path.insert(0, str(ROOT / "hermes" / "scripts"))
        from prediction_tracker import verify_predictions, aggregate_stats
        from system_data_bridge import snapshot as bridge_snap
        
        # 获取各品种当前价格
        prices = {}
        for sym in ["BTCUSDT", "XAUUSD"]:
            try:
                snap = bridge_snap(sym) if _HAS_BRIDGE else None
                if snap and snap.get("price"):
                    prices[sym] = snap["price"]
                else:
                    # Fallback: read from source_snapshot
                    snap_file = DATA_DIR / "source_snapshot.json"
                    if snap_file.exists():
                        d = json.loads(snap_file.read_text(encoding="utf-8"))
                        if d.get("symbol") == sym or d.get("prices", {}).get("primary"):
                            prices[sym] = d.get("prices", {}).get("primary", 0)
            except (ImportError, ModuleNotFoundError, AttributeError):
                pass
        
        # 回验每个品种
        total_verified = 0
        for sym, price in prices.items():
            if price > 0:
                verified = verify_predictions(sym, price, lookback_hours=4.0)
                total_verified += len(verified)
        
        if total_verified > 0:
            log(f"预测回验完成：{total_verified}条")
            stats = aggregate_stats()
            if stats.get("total_predictions"):
                acc = stats.get("overall_accuracy", 0)
                log(f"模型胜率：{acc:.1%} ({stats['total_predictions']}条已验证)")
    except Exception as e:
        log(f"预测回验错误: {str(e)[:80]}")


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


def _normalize_fraction(value):
    try:
        v = abs(float(value))
    except (TypeError, ValueError):
        return 0.0
    return v / 100.0 if v > 1 else v


def snapshot_volatility_24h_fraction(snapshot, symbol=None):
    snap = snapshot or {}
    extra = snap.get("extra") if isinstance(snap.get("extra"), dict) else {}
    market = snap.get("market") if isinstance(snap.get("market"), dict) else {}
    prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
    for box in (extra, market, prices, snap):
        for key in ("volatility_24h", "volatility_24h_pct", "realized_volatility_24h", "price_change_24h_pct"):
            if isinstance(box, dict) and box.get(key) is not None:
                frac = _normalize_fraction(box.get(key))
                if frac > 0:
                    return frac
    return 0.0


def check_risk_constitution(**kwargs):
    from risk_constitution import check_constitution
    return check_constitution(**kwargs)


def load_constitution_state():
    from risk_constitution import load_risk_state
    return load_risk_state()


def apply_risk_constitution(symbol, gate, snapshot, state=None, account_balance=67.52):
    result_gate = dict(gate)
    result_gate["reasons"] = list(gate.get("reasons", []))
    constitution_result = check_risk_constitution(
        symbol=symbol,
        risk_usd=result_gate.get("max_risk_usd", 3.0),
        account_balance=account_balance,
        state=state if state is not None else load_constitution_state(),
        volatility_24h_pct=snapshot_volatility_24h_fraction(snapshot, symbol),
    )
    if not constitution_result["allowed"]:
        result_gate["allowed"] = False
        result_gate["tier"] = "禁止"
        result_gate["max_risk_usd"] = 0
        result_gate["reasons"] = constitution_result["violations"]
    elif constitution_result["risk_tier"] != "常规":
        result_gate["tier"] = constitution_result["risk_tier"]
        result_gate["max_risk_usd"] = constitution_result["max_risk_usd"]
        result_gate["reasons"].append(f"宪法降级: {constitution_result['risk_tier']}")
    return result_gate


def expire_stale_levels(raw):
    changed = False
    if not isinstance(raw, dict):
        return False
    blocks = list(raw["symbols"].items()) if isinstance(raw.get("symbols"), dict) else [(raw.get("symbol") or DEFAULT_SYMBOL, raw)]
    for symbol, block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("levels"), list):
            continue
        block_changed = False
        for item in block["levels"]:
            if isinstance(item, dict) and item.get("status", "active") in {"active", "triggered"} and is_expired(block, item):
                item["status"] = "expired"
                item["status_time"] = now_local().isoformat()
                item.setdefault("expire_reason", "valid_until过期自动清理")
                changed = block_changed = True
        if block_changed:
            block["updated"] = now_local().isoformat()
    return changed


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
        if dist < BREACH_PCT:
            return True, "价格触发关键位"
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
    if text == "order_block":
        return dist < NEAR_PCT, "抵达订单块供需区"
    if text == "breaker_block":
        return dist < NEAR_PCT, "抵达破坏块反转区"
    if text == "fair_value_gap":
        return dist < NEAR_PCT, "抵达FVG缺口区"
    if text == "bos":
        return dist < NEAR_PCT, "接近结构突破关键位"
    if text == "choch":
        return dist < BREACH_PCT, "性质转变确认触发"
    if text == "cvd_divergence":
        return dist < NEAR_PCT, "CVD背离位附近"
    return dist < NEAR_PCT, "接近计划位"


def _fmt_price(symbol, level):
    """XAU 保留 1 位小数，加密取整。"""
    try:
        lv = float(level)
    except (TypeError, ValueError):
        return str(level)
    if "XAU" in str(symbol).upper():
        return f"{lv:.1f}"
    return f"{lv:.0f}"


def format_hit(price, item, index, symbol="BTCUSDT"):
    """v7.4: 触发位子项 — 对齐分析卡结构段，含位信/距离/属性/动作/失效。"""
    display = item.get("display_name") or item.get("name", "关键位")
    level = item.get("level", 0)
    action = item.get("action", "关键位提醒")
    lines = [f"▸ {display} · `{_fmt_price(symbol, level)}`"]
    # 距离
    try:
        lv = float(level)
        if lv:
            diff = float(price) - lv
            pct = abs(diff) / lv * 100
            side = "高于" if diff > 0 else ("低于" if diff < 0 else "正贴")
            dist_txt = "正贴关键位" if abs(diff) < 1e-9 else f"现价{side} `{pct:.2f}%`"
            lines.append(f"   距离：{dist_txt}")
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    # 位信（实时 live 优先）
    conf = item.get("live_level_confidence") or item.get("level_confidence")
    if isinstance(conf, dict):
        grade = conf.get("grade", "C")
        score = conf.get("score", 0)
        label = conf.get("label", "")
        lines.append(f"   位信：{grade}级 · `{score}%` · {label}")
    lines.append(f"   动作：{action}")
    invalid = item.get("invalid_if")
    if invalid and invalid != "见最新分析":
        lines.append(f"   失效：{zh_invalid(invalid)}")
    return "\n".join(lines)


def _level_short(item):
    """从 display_name 取简称（阻1/阻2/支1/支2）。"""
    display = item.get("display_name") or item.get("name", "关键位")
    return display.split("·")[0].strip() if "·" in display else display


def sort_levels_panorama(all_levels):
    """全景排序：阻力区（高→低）在上，支撑区（高→低）在下，现价居中视觉。"""
    res, sup, other = [], [], []
    for x in all_levels:
        s = x.get("side")
        (res if s == "resistance" else sup if s == "support" else other).append(x)
    res.sort(key=lambda x: float(x.get("level", 0) or 0), reverse=True)
    sup.sort(key=lambda x: float(x.get("level", 0) or 0), reverse=True)
    return res + sup + other


def format_level_brief(price, item, symbol="BTCUSDT", triggered=False):
    """v7.5: 未触发关键位的单行简略显示（全景区用）。"""
    short = _level_short(item)
    level = item.get("level", 0)
    parts = [f"{short} `{_fmt_price(symbol, level)}`"]
    try:
        lv = float(level)
        if lv:
            diff = float(price) - lv
            pct = abs(diff) / lv * 100
            side = "上方" if diff > 0 else ("下方" if diff < 0 else "正贴")
            parts.append("正贴" if abs(diff) < 1e-9 else f"现价{side}`{pct:.2f}%`")
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    conf = item.get("live_level_confidence") or item.get("level_confidence")
    if isinstance(conf, dict):
        parts.append(f"{conf.get('grade', 'C')}级`{conf.get('score', 0)}%`")
    line = "· " + " · ".join(parts)
    if triggered:
        line += "  ◀ 已触发"
    return line


def zh_invalid(rule):
    """失效规则英转中。"""
    text = str(rule or "见最新分析")
    text = text.replace("close above", "收盘上破").replace("close below", "收盘下破")
    text = text.replace("price reclaims", "价格收复").replace("reclaim above", "收复上方")
    text = text.replace("below", "下破").replace("above", "上破")
    text = re.sub(r"\b(\d+)m\b", r"\1分钟", text)
    return text


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
    if cvd in {"买", "buy", "BUY"} and item.get("side") == "support":
        score += 4
        basis.append("CVD买盘配合支撑")
    elif cvd in {"卖", "sell", "SELL"} and item.get("side") == "resistance":
        score += 4
        basis.append("CVD卖盘配合阻力")
    elif cvd in {"买", "卖", "buy", "sell", "BUY", "SELL"}:
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
    breached_like = any((x.get("condition") in {"breach", "close_confirm", "combo", "combined", "near_or_breach"}) or "触发" in str(x.get("condition_reason", "")) for x in hits or [])
    if tier == "critical":
        if score >= MIN_CRITICAL_LEVEL_SCORE and (data_q != "C" or xau_single_ok or score >= 82):
            suffix = " · 单源金十降级" if data_q == "C" and xau_single_ok else ""
            return True, f"紧急且位信{score}%{suffix}"
        return False, f"紧急但确认不足：位信{score}% · 数据{data_q}级"
    if tier == "warning":
        if high_priority and breached_like and data_q in ("A", "B"):
            return True, f"高优先级触发且位信{score}% · 数据{data_q}级"
        if high_priority and breached_like and score >= 60 and (data_q != "C" or xau_single_ok):
            suffix = " · 单源金十降级" if data_q == "C" and xau_single_ok else ""
            return True, f"触发且位信{score}%{suffix}"
        # v7.4: medium级breach门槛与 MIN_WARNING_LEVEL_SCORE(65) 统一，
        # 消除 65/68 死区（66分位既进warning池又永远被静默）。
        if breached_like and score >= MIN_WARNING_LEVEL_SCORE and data_q in ("A", "B"):
            return True, f"触发且位信{score}% · 数据{data_q}级"
        return False, f"未达到强确认：位信{score}% · 数据{data_q}级"
    if tier == "invalidated":
        if high_priority and score >= 60:
            return True, f"高优先级计划失效且位信{score}%"
        if score >= MIN_WARNING_LEVEL_SCORE:
            return True, f"计划失效且位信{score}%"
        # v2.1: 失效但位信不足→记录但不静默全部
        return False, f"失效提醒降噪：位信{score}%"
    if tier == "expired":
        if high_priority or score >= 65:
            return True, f"{'高优先级' if high_priority else '位信'+str(score)+'%'}过期"
        return False, f"过期降噪：位信{score}%"
    # v7.4: info 门槛与 MIN_WARNING_LEVEL_SCORE(65) 统一，消除死区
    if tier == "info":
        if high_priority and score >= 60:
            return True, f"高优先级接近提醒·位信{score}%"
        if score >= MIN_WARNING_LEVEL_SCORE:
            return True, f"接近计划位·位信{score}%"
        return False, f"接近降噪：位信{score}%"
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



def enrich_event_with_setup(event, block, hits=None, trigger_kind=None):
    """Attach auto_card latest_setup trace fields to monitor events.

    This closes the chain: auto_card setup -> monitor trigger -> review stats.
    Missing latest_setup is intentionally non-fatal for legacy/manual plans.
    """
    hits = hits or []
    setup = (block or {}).get("latest_setup") if isinstance(block, dict) else None
    event.setdefault("trigger_kind", trigger_kind or event.get("type"))
    event.setdefault("trigger_price", event.get("price"))
    if hits:
        event["trigger_levels"] = [str(x.get("name")) for x in hits if isinstance(x, dict) and x.get("name")]
        first = next((x for x in hits if isinstance(x, dict)), None)
        if first is not None:
            event["trigger_level"] = first.get("level")
            event["trigger_level_name"] = first.get("name")
            if first.get("condition_reason") is not None:
                event["trigger_reason"] = first.get("condition_reason")
            if first.get("live_level_confidence") is not None:
                event["trigger_level_confidence"] = first.get("live_level_confidence")
    if not isinstance(setup, dict) or not setup.get("setup_id"):
        return event
    for key in (
        "setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status",
        "priority_plan", "data_grade", "level_confidence", "engine_confidence",
        "confidence_5", "risk_usd", "rr1", "rr2", "invalid_price", "expires_at",
    ):
        if setup.get(key) is not None:
            event[key] = setup.get(key)
    event["setup_trace"] = {
        "setup_id": setup.get("setup_id"),
        "model_id": setup.get("model_id"),
        "entry_tag": setup.get("entry_tag"),
        "exit_tag": setup.get("exit_tag"),
    }
    event["schema"] = "v2.4"
    return event

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


# v7.5: 突破后就地自动重算结构 — 不再只写 pending 等下一轮 cron。
# 社区共识（Brave 研究）：静态位被突破=该区已失效，需立即生成新结构。
# 做法：真实突破(breached)发生时，立即调 智能更新结构.build_levels_v2 用真实K线
# 重算五模型结构位，原地写回 raw[symbols][symbol][levels]，并标注"突破后自动更新"。
_LAST_AUTO_REFRESH = {}
_AUTO_REFRESH_COOLDOWN = 600  # 同品种10分钟内不重复重算，防突破抖动刷屏


def auto_refresh_structure(raw, symbol, price, breached):
    """突破触发后就地重算结构位。返回 (raw, refreshed: bool)。
    只在真实突破(breached非空)时触发；失败静默退回，不影响主推送。"""
    if not breached:
        return raw, False
    now_ts = time.time()
    if now_ts - _LAST_AUTO_REFRESH.get(symbol, 0) < _AUTO_REFRESH_COOLDOWN:
        return raw, False
    try:
        eng_dir = str(ROOT / "scripts")
        if eng_dir not in sys.path:
            sys.path.insert(0, eng_dir)
        import importlib
        zhi = importlib.import_module("智能更新结构")
        new_levels = zhi.build_levels_v2(symbol, float(price))
        if not new_levels:
            return raw, False
        _LAST_AUTO_REFRESH[symbol] = now_ts
        stamp = now_local().isoformat()
        if isinstance(raw.get("symbols"), dict):
            blk = raw["symbols"].setdefault(symbol, {})
        else:
            blk = raw
        blk["levels"] = new_levels
        blk["analysis_cycle"] = "突破后自动更新 · 五模型结构重算 · 等回踩确认"
        blk["price_at_analysis"] = float(price)
        blk["updated"] = stamp
        blk["plan_id"] = f"{symbol}-{now_local().strftime('%Y%m%d-%H%M')}-auto"
        blk["needs_structure_refresh"] = False
        blk["refresh_reason"] = ""
        blk["auto_refresh"] = {"time": stamp, "trigger": "突破后自动重算", "price": float(price), "n_levels": len(new_levels)}
        log(f"突破自动重算 {symbol}: {len(new_levels)}个新结构位 @ {price}")
        return raw, True
    except Exception as e:
        log(f"突破自动重算失败 {symbol}: {str(e)[:80]}")
        return raw, False


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
    # v2.1: 预算按品种拆分（symbol从key中提取）
    symbol_counts = {}
    for x in history:
        for key in x.get("keys", []):
            sym = key.split(":")[0] if ":" in key else "global"
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
    max_symbol = max(symbol_counts.values()) if symbol_counts else 0
    if tier_count >= ALERT_BUDGET_BY_TIER.get(tier, 3):
        return True
    if max_symbol >= ALERT_BUDGET_GLOBAL:
        return True
    return len(history) >= ALERT_BUDGET_GLOBAL * 2 and tier != "critical"


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


STATUS_ZH = {"A做多": "A做多", "A做空": "A做空", "B等待": "B等待", "X禁做": "X禁做",
             "long": "A做多", "short": "A做空", "wait": "B等待", "ban": "X禁做"}


def _cvd_display(cvd, cvd_quality):
    """CVD '?' / None 兜底为可读文案。"""
    if cvd in (None, "?", "", "不适用"):
        if cvd == "不适用":
            return "不适用（非加密）"
        return f"估算中 · {cvd_quality or 'C级'}"
    return f"{cvd} · {cvd_quality or 'C级'}"


def render_message(head, symbol, price, plan_id, cycle, hits, urgency, cvd=None, cvd_quality=None, reason=None, tier="info", risk_text=None, derivatives_text=None, ls_text=None, taker_text=None, conflict_text=None, model_dir_text=None, setup=None, all_levels=None):
    """v7.4: 序号语义对齐分析卡 v6.8。
    ①品种 ②周期 ③现价 ④状态(A/B/X) ⑤模型 ⑥触发位 ⑦订单流 ⑧衍生 ⑨引擎/冲突 ⑩风控。
    实时触发瞬间无完整分析，④状态/⑤模型 从 latest_setup 读取，缺失则降级文案。"""
    setup = setup or {}
    lines = [head, ""]
    # 全卡统一圈号计数器：头部字段与衍生区共用，全程连续不撞不跳。
    # 触发位子项用 ▸，不占圈号，避免与头部 ①②③ 撞车。
    _n = [0]
    def _seq():
        _n[0] += 1
        return SEQ_NUMS[_n[0] - 1] if _n[0] <= len(SEQ_NUMS) else f"{_n[0]}."
    # 品种
    lines.append(f"{_seq()} 品种：{symbol}.P:{'OANDA' if 'XAU' in symbol.upper() else 'BINANCE'}")
    # 周期（监控触发周期描述）
    lines.append(f"{_seq()} 周期：{cycle}")
    # 现价
    lines.append(f"{_seq()} 现价：`{_fmt_price(symbol, price)}`")
    # 状态（A做多/A做空/B等待/X禁做）— 取自 latest_setup，触发情境无则降级
    raw_status = setup.get("status") or setup.get("direction")
    status_zh = STATUS_ZH.get(str(raw_status), None)
    if status_zh:
        lines.append(f"{_seq()} 状态：{status_zh} · {situation_text(tier)}")
    else:
        lines.append(f"{_seq()} 状态：{situation_text(tier)}")
    # 模型（latest_setup 有才显示）
    model_id = setup.get("model_id")
    if model_id and model_id != "无":
        conf5 = setup.get("confidence_5")
        conf_txt = f" · 置信 {conf5}/5" if conf5 else ""
        lines.append(f"{_seq()} 模型：{model_id}{conf_txt}")
    # 触发位（主体）— 子项用 ▸，不占圈号
    if hits:
        lines.append("")
        for item in hits:
            lines.append(format_hit(price, item, 0, symbol=symbol).rstrip())
        if reason:
            lines.append(f"   原因：{reason}")
    # v7.5: 关键位全景 — 始终列出全部近端阻力/支撑，触发位高亮，未触发位单行简略。
    # 让你在任一位触发时也能看到阻1/阻2/支1/支2 完整结构和各自距离。
    if all_levels:
        hit_names = {h.get("name") for h in (hits or [])}
        panorama = sort_levels_panorama(all_levels)
        if panorama:
            lines.append("")
            lines.append(f"{_seq()} 关键位全景：")
            for item in panorama:
                triggered = item.get("name") in hit_names
                lines.append("   " + format_level_brief(price, item, symbol=symbol, triggered=triggered))
    # 衍生信号区（订单流/衍生/引擎/风控）— 顺序固定，圈号接续头部
    lines.append("")
    extras = [
        ("订单流", _cvd_display(cvd, cvd_quality) if cvd is not None else None),
        ("Taker", taker_text or None),
        ("多空", ls_text or None),
        ("衍生", derivatives_text or None),
        ("引擎", model_dir_text or None),
        ("冲突", conflict_text or None),
        ("风控", risk_text or None),
    ]
    for label, val in extras:
        if val:
            lines.append(f"{_seq()} {label}：{val}")
    # 动作 + 提示：禁止把 critical/warning/info 这类机器枚举暴露给用户。
    urgency_text = str(urgency or "").strip()
    urgency_map = {
        "critical": "突破/触发后先等回踩确认；未确认前不追第一根",
        "warning": "接近关键位，等待5分钟收盘确认和订单流配合",
        "info": "观察为主，未触发前不提前下注",
        "expired": "旧位已过期，不再按旧计划执行",
        "invalidated": "关键位已失效，停止按旧预案执行",
    }
    action_text = urgency_map.get(urgency_text, urgency_text or "等待确认")
    lines.append("")
    lines.append(f"动作：{action_text}")
    lines.append(f"提示：说「分析 {symbol.replace('USDT', '')}」刷新完整卡")
    return "\n".join(lines)


def process_block(raw, symbol, block, state):
    if block.get("monitor_enabled") is False:
        return raw, False
    
    # v6.4: 事件禁做熔断
    if _HAS_BRIDGE:
        banned, ban_reason = bridge_event_ban()
        if banned:
            log(f"事件禁做 {symbol}: {ban_reason}")
            return raw, False
    
    # v7.1: XAUUSD时段过滤 — 只在高流动性时段推送告警
    if "XAU" in str(symbol).upper():
        try:
            from session_filter import should_trade as session_ok
            trade_ok, session_reason = session_ok("XAUUSD", require_kill_zone=False)
            if not trade_ok:
                # 闭市/低流动性 → 静默，不推送
                return raw, False
        except ImportError:
            pass  # session_filter不可用时退化到无过滤
    
    price = get_price(symbol, block)
    if price is None:
        return raw, False
    # P2-3: Fail-Fast 数据完整性 — NaN/无限价格直接拒绝（借鉴NautilusTrader）
    if not isinstance(price, (int, float)) or price != price or abs(price) == float('inf'):
        log(f"数据完整性失败 {symbol}: 价格={price} 非法值，跳过本轮")
        return raw, False
    items = [x for x in normalize_levels(block) if x.get("status", "active") == "active"]
    if not items:
        return raw, False

    plan_id = block.get("plan_id") or raw.get("plan_id") or f"{symbol}-manual"
    setup = block.get("latest_setup") if isinstance(block.get("latest_setup"), dict) else {}
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
    # v6.9: 风险宪法覆盖（Kelly仓位 + 日回撤熔断 + 连亏暂停）
    try:
        gate = apply_risk_constitution(symbol, gate, snapshot)
    except Exception:
        pass  # 宪法模块不可用时退化到原风控
    derivatives_text = bridge_deriv(symbol) if _HAS_BRIDGE else derivatives_line(snapshot)
    # v6.5: 多空比 + Taker + 方向冲突文本
    ls_text = taker_text = conflict_text = ""
    if _HAS_BRIDGE:
        snap = bridge_snap(symbol)
        ls = snap.get("ls", {})
        tk = snap.get("taker", {})
        if ls.get("long_pct"):
            ls_text = f"{ls['long_pct']}%多·{ls.get('dir','')}"
        if tk.get("ratio"):
            taker_text = f"{tk['dir']} {tk['ratio']:.2f}·{tk.get('q','B')}级"
        # 方向冲突检测
        long_pct = ls.get("long_pct", 50)
        taker_dir = tk.get("dir", "neutral")
        funding_flipped = snap.get("funding", {}).get("flipped", False)
        if long_pct > 60 and taker_dir == "sell":
            conflict_text = "多头拥挤vsTaker卖"
        elif long_pct < 40 and taker_dir == "buy":
            conflict_text = "空头拥挤vsTaker买"
        elif funding_flipped:
            conflict_text = f"费率翻转"
    confidence_text = confidence_line(snapshot)
    model_dir_text = ""  # 安全初始化：所有分支使用前确保已赋值

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
                msg = render_message(f"{symbol} · 监控位过期", symbol, price, plan_id, cycle, expired, "旧位已过期，不再按旧计划触发", tier="expired", risk_text=risk_text, derivatives_text=derivatives_text, ls_text=ls_text, taker_text=taker_text, conflict_text=conflict_text, model_dir_text=model_dir_text, setup=setup, all_levels=items)
                pushed = push(msg, target=alert_target_for(symbol))
            else:
                log(f"降噪不推送 {symbol} expired: {push_reason}")
                record_noise(state, symbol, "expired", push_reason)
            event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": "expired", "tier": "expired", "price": price, "levels": event_level_rows(expired), "risk_gate": gate, "confidence": confidence_payload(snapshot), "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": pushed, "schema": "v2.3"}
            enrich_event_with_setup(event, block, expired, trigger_kind="expired")
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
                msg = render_message(f"{symbol} · 计划失效", symbol, price, plan_id, cycle, invalidated, "旧计划已失效，等新分析刷新", reason=reason, tier="invalidated", risk_text=risk_text, derivatives_text=derivatives_text, ls_text=ls_text, taker_text=taker_text, conflict_text=conflict_text, model_dir_text=model_dir_text, setup=setup, all_levels=items)
                pushed = push(msg, target=alert_target_for(symbol))
            else:
                log(f"降噪不推送 {symbol} invalidated: {push_reason}")
                record_noise(state, symbol, "invalidated", push_reason)
            event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": "invalidated", "tier": "invalidated", "price": price, "levels": event_level_rows(invalidated), "risk_gate": gate, "confidence": confidence_payload(snapshot), "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": pushed, "schema": "v2.3"}
            enrich_event_with_setup(event, block, invalidated, trigger_kind="invalidated")
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

    cvd, cvd_quality = bridge_cvd(symbol) if _HAS_BRIDGE else get_cvd(symbol)
    # v6.4: 检查多模型方向翻转
    if _HAS_BRIDGE:
        flipped, old_d, new_d = bridge_dir_flip(symbol)
        if flipped:
            log(f"⚠ 多模型方向翻转 {symbol}: {old_d} → {new_d}")
            push(f"🔄 {symbol} 多模型方向翻转\n旧方向：{old_d}\n新方向：{new_d}\n请检查是否需要更新分析卡", target=alert_target_for(symbol))
    # v6.6: 双置信对比（位信 vs 模型信）
    model_dir_text = ""
    if _HAS_BRIDGE:
        try:
            from system_data_bridge import _LAST as _MCACHE
            last_dir = _MCACHE.get(symbol)
            if last_dir:
                # 从触发位推断结构性方向
                s = "偏多" if any(h.get("side") == "support" for h in (breached + near)) else "偏空" if any(h.get("side") == "resistance" for h in (breached + near)) else ""
                m = last_dir
                if s and m not in ("方向不明/震荡", ""):
                    agree = (s == "偏多" and "多" in m) or (s == "偏空" and "空" in m)
                    model_dir_text = f"引擎判{m} · {'位信一致✓' if agree else '位信矛盾⚠'}"
                else:
                    model_dir_text = f"引擎判{m}"
        except Exception:
            pass
    high_priority_breach = any(x.get("priority") == "high" for x in breached)
    cvd_break = any(x.get("type") in (
        "vwap_reclaim_filter", "retest_short", "break_low", "liquidity_sweep_low",
        "order_block", "breaker_block", "mitigation_block", "rejection_block",
        "wyckoff_sow", "sweep_reclaim"
    ) for x in breached) and cvd == "卖"
    if len(breached) >= 2 or (high_priority_breach and cvd_break):
        tier, head = "critical", f"{symbol} · 紧急关键位"
    elif breached:
        tier, head = "warning", f"{symbol} · 关键位触发"
    else:
        tier, head = "info", f"{symbol} · 接近计划位"
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
        msg = render_message(head, symbol, price, plan_id, cycle, hits, urgency, cvd=cvd, cvd_quality=cvd_quality, tier=tier, risk_text=risk_text, derivatives_text=derivatives_text, ls_text=ls_text, taker_text=taker_text, conflict_text=conflict_text, model_dir_text=model_dir_text, setup=setup, all_levels=items)
        pushed = push(msg, target=alert_target_for(symbol))
    else:
        log(f"降噪不推送 {symbol} {tier}: {push_reason}")
        record_noise(state, symbol, tier, push_reason)

    if breached:
        raw = mark_levels(raw, symbol, {x["name"] for x in breached}, "triggered")
    # v7.5: 突破后就地自动重算结构（推送已发完，用旧位触发；重算供下一轮）。
    # 成功重算则不再写 pending 请求；失败时退回旧的 maybe_request_refresh 机制。
    raw, auto_refreshed = auto_refresh_structure(raw, symbol, price, breached)
    refresh_req = None
    if auto_refreshed:
        push(f"🔁 {symbol} · 结构已自动更新\n触发突破后已重算五模型结构位，等回踩确认\n说「分析 {symbol.replace('USDT', '')}」看完整新卡", target=alert_target_for(symbol))
    else:
        refresh_req = maybe_request_refresh(raw, symbol, block, tier, hits)
        if refresh_req:
            log(f"结构刷新请求: {symbol} {refresh_req['reasons']}")
    trigger_kind = "breach" if breached else "near"
    event = {"time": now_local().isoformat(), "symbol": symbol, "plan_id": plan_id, "type": f"{tier}_{trigger_kind}", "tier": tier, "price": price, "levels": event_level_rows(hits), "cvd": cvd, "cvd_quality": cvd_quality, "risk_gate": gate, "confidence": confidence_payload(snapshot), "refresh_request": refresh_req, "derivatives": (snapshot or {}).get("derivatives", {}), "push_sent": pushed, "push_reason": push_reason, "notified": pushed, "schema": "v2.3"}
    enrich_event_with_setup(event, block, hits, trigger_kind=trigger_kind)
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
        log(f"实时监控 v7.5 | 10s | 接近{NEAR_PCT*100:.1f}% | 突破{BREACH_PCT*100:.1f}% | {'数据桥已接' if _HAS_BRIDGE else '数据桥未接'}")
        state = read_json(STATE_FILE, {"last_alerts": {}})
        while True:
            try:
                # P0-1 fix: 心跳移到循环最顶部，确保每轮先报活
                write_heartbeat("running")
                raw = read_json(LEVELS_FILE, {})
                changed = expire_stale_levels(raw)
                for symbol, block in list(iter_symbol_blocks(raw)):
                    # 每个symbol处理前再刷一次心跳（带symbol名）
                    write_heartbeat("running", symbol)
                    raw, block_changed = process_block(raw, symbol, block, state)
                    changed = changed or block_changed

                if changed:
                    save_json(LEVELS_FILE, raw)
                    save_json(STATE_FILE, state)
                
                # v6.7: 每30分钟回验一次预测（胜率追踪）
                _verify_predictions_if_needed(state)
                
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
