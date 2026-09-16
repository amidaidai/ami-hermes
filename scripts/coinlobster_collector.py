#!/usr/bin/env python3
"""
CoinLobster 采集器 v1.1 —— 鲸鱼成交 / 全市场清算级联 / 逐所资金费率 / 情绪

【定位】外部验证层（evidence-only）。只做多源交叉验证的背景与反证，
       不参与主指标授权、不生成 Entry/Stop、不做硬阻断。
       消费方见 docs/指标驱动分析与策略合同.md 的数据源分级。

【为什么是脚本而不是现场调 MCP 工具】54 个工具进目录会污染工具选择；
       采集器走 source_contract 五态信封，cron 读缓存、降级可见、可审计。

【实测口径 2026-09-16】带 key：market_snapshot / market_liquidations /
       oi_funding_history / funding_matrix / whale_radar 全部实时（0.1–0.8 分钟）；
       无 key 则为 30 分钟延迟。工件里的 delay_minutes 由响应自身的时间戳实测得出，
       不照抄服务端自述。

免费档深度限制：whale_radar 只给 BTC 全深度，其余币种只给方向且幅度模糊（blurred）。
key 从环境变量 MCP_COINLOBSTER_API_KEY 读，缺失时回落 hermes profile .env。
本脚本每次运行消耗 6 次调用额度（免费档 200 次/日）。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_contract import write_source_artifact  # noqa: E402

TZ = timezone(timedelta(hours=8))
# 浏览器 UA 是硬要求：默认 python UA 会被 Cloudflare 403
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
MCP_URL = "https://coinlobster.com/mcp"      # key 只能打这里，不要用 /mcp/connector
HERMES_ENV = Path(os.path.expanduser("~/AppData/Local/hermes/.env"))
DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
ARTIFACT = DATA_DIR / "coinlobster_snapshot.json"
SOURCE_ID = "coinlobster_snapshot"
PROXY = "http://127.0.0.1:7897"
LIVE_THRESHOLD_MIN = 5.0      # 超过这个年龄就不许当实时用

# ── 额度自保（2026-09-16）───────────────────────────────────────────────
# 免费档 200 次/日。实测被 cron（core 2 次/轮）+ 按需深采（full 6 次/轮）吃满后，
# 之后每一轮都返回 429 并 exit 1 → 每 30 分钟铸造一条 incident、把 preflight 拖红。
# 额度打满是**状态**不是故障：归为 quota_cooldown、可见降级、exit 0、冷却到次日。
DAILY_CALL_BUDGET = int(os.environ.get("COINLOBSTER_DAILY_BUDGET", "200"))
QUOTA_BREAKER = DATA_DIR / ".coinlobster_quota_breaker.json"
BUDGET_STATE = DATA_DIR / ".coinlobster_daily_budget.json"


def is_daily_quota_error(errors: dict) -> bool:
    """429 + 「当日额度用尽」→ True。

    区分两类 429：短时限流（等几分钟就好）与当日额度打满（今天不会恢复）。
    只有后者才冷却到次日；短时限流仍按失败上报，不用 cooldown 掩盖真问题。
    判据取服务端原文：`code -32029` / `Daily limit reached` / `calls a day`。
    """
    text = " ".join(str(v) for v in (errors or {}).values())
    low = text.lower()
    if "429" not in text and "-32029" not in text:
        return False
    return ("-32029" in text) or ("daily limit" in low) or ("calls a day" in low)


def _next_reset_iso() -> str:
    """冷却终点：次日 00:05（额度按自然日恢复，留 5 分钟余量）。"""
    nxt = datetime.now(TZ).replace(hour=0, minute=5, second=0, microsecond=0) + timedelta(days=1)
    return nxt.isoformat(timespec="seconds")


def quota_breaker_active() -> dict | None:
    """额度冷却中 → 返回 breaker 内容；未冷却/文件坏 → None（不因坏文件停采）。"""
    try:
        payload = json.loads(QUOTA_BREAKER.read_text(encoding="utf-8"))
        until = str(payload.get("until") or "")
        if until and datetime.fromisoformat(until) > datetime.now(TZ):
            return payload
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        pass
    return None


def arm_quota_breaker(reason: str) -> str:
    until = _next_reset_iso()
    try:
        QUOTA_BREAKER.write_text(json.dumps(
            {"until": until, "reason": reason,
             "armed_at": datetime.now(TZ).isoformat(timespec="seconds")},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return until


def calls_used_today() -> int:
    try:
        payload = json.loads(BUDGET_STATE.read_text(encoding="utf-8"))
        if payload.get("date") == datetime.now(TZ).strftime("%Y-%m-%d"):
            return int(payload.get("calls") or 0)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        pass
    return 0


def record_calls(n: int) -> int:
    """记当日成功调用数（只有成功调用才吃额度）。返回累计值。"""
    total = calls_used_today() + max(0, int(n))
    try:
        BUDGET_STATE.write_text(json.dumps(
            {"date": datetime.now(TZ).strftime("%Y-%m-%d"), "calls": total,
             "budget": DAILY_CALL_BUDGET,
             "updated_at": datetime.now(TZ).isoformat(timespec="seconds")},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return total


def write_degraded_artifact(status: str, *, errors: dict | None = None,
                           note: str = "", extra: dict | None = None) -> None:
    """降级落盘：保留上次工件、状态进信封（不静默、不伪装 live、不丢旧数据）。

    注意：旧工件里带 `_source_contract`，直接回灌会被 `_raw_payload` 拆包成
    **旧 payload**，把本轮要写的注记/标记丢掉（实测 degraded_note 消失）。
    所以先把元数据键剥掉再合并。
    """
    prev_payload = {}
    try:
        prev = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        prev_payload = prev.get("payload", prev) if isinstance(prev, dict) else {}
    except (OSError, json.JSONDecodeError):
        prev_payload = {}
    payload = {k: v for k, v in prev_payload.items() if not str(k).startswith("_")} \
        if isinstance(prev_payload, dict) else {}
    if note:
        payload["degraded_note"] = note
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})
    write_source_artifact(
        str(ARTIFACT), SOURCE_ID, payload or {"btc": {}},
        status=status, captured_at=None,
        error=json.dumps(errors, ensure_ascii=False)[:300] if errors else (note or None),
        cached=bool(prev_payload), symbol="BTC")

# 免费档 200 次/日。core = 只采「接进管线」的两格（2 次/轮），
# 按每 20 分钟一次 = 144 次/日，余量留给按需深采；full = 全量 6 次/轮。
PROFILES = {
    "core": [
        ("market_liquidations", {}),
        ("funding_matrix", {"coin": "BTC"}),
    ],
    "full": [
        ("market_snapshot", {"coin": "BTC"}),
        ("market_liquidations", {}),
        ("funding_matrix", {"coin": "BTC"}),
        ("oi_funding_history", {"coin": "BTC", "hours": 24}),
        ("whale_radar", {}),
        ("crypto_news", {"coin": "BTC"}),
    ],
}


def load_key() -> str:
    key = os.environ.get("MCP_COINLOBSTER_API_KEY", "").strip()
    if key:
        return key
    try:
        for line in HERMES_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("MCP_COINLOBSTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _rpc(tool: str, args: dict, key: str, timeout: int = 30):
    """单次工具调用 -> (ok, data_or_error)。直连优先，失败回落本地代理。"""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": tool, "arguments": args}}).encode()
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "User-Agent": UA}
    if key:
        headers["X-API-Key"] = key

    last = "unknown"
    for use_proxy in (False, True):
        handler = urllib.request.ProxyHandler(
            {"http": PROXY, "https": PROXY} if use_proxy else {})
        opener = urllib.request.build_opener(handler)
        try:
            req = urllib.request.Request(MCP_URL, data=payload,
                                         headers=headers, method="POST")
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", "replace")[:160]
            except Exception:  # noqa: BLE001
                pass
            last = f"HTTP {exc.code} {body_text}"
            if exc.code in (401, 403, 429):
                return False, last
            continue
        except Exception as exc:  # noqa: BLE001 - 网络类异常统一降级
            last = f"{type(exc).__name__}: {exc}"
            continue

        obj = None
        if body.lstrip().startswith("{"):
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                last = "bad_json"
        else:
            for line in body.splitlines():
                if line.startswith("data:"):
                    try:
                        obj = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        pass
        if obj is None:
            last = "no_jsonrpc_payload"
            continue
        if "error" in obj:
            return False, str(obj["error"])[:200]
        try:
            return True, json.loads(obj["result"]["content"][0]["text"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            last = f"unparsable_result: {str(obj)[:120]}"
    return False, last


def _age_minutes(now_utc: datetime, *candidates):
    """从响应自身的时间戳里算出最保守的数据年龄（分钟）。"""
    ages = []
    for c in candidates:
        if c is None:
            continue
        dt = None
        if isinstance(c, (int, float)) and c > 1e11:      # epoch ms
            dt = datetime.fromtimestamp(c / 1000, timezone.utc)
        elif isinstance(c, str):
            try:
                dt = datetime.fromisoformat(c.replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if dt is not None:
            ages.append((now_utc - dt).total_seconds() / 60)
    return round(max(ages), 1) if ages else None


def artifact_age_minutes():
    """上一次采集距今多少分钟（读信封的 _source_timestamp）。不可读时返回 None。"""
    try:
        env = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = env.get("_source_timestamp") if isinstance(env, dict) else None
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60


def _trim(series, tail=12):
    return series[-tail:] if isinstance(series, list) else []


def _shape(raw: dict, now_utc: datetime) -> dict:
    """按各工具真实字段结构压成窄结构（字段名来自实测 tools/list + 响应）。"""
    out: dict = {"btc": {}, "liquidations": {}, "funding": {}, "oi_path": {},
                 "whale_radar": {}, "news": {}}
    ages = []
    degraded = []          # 调用成功但上游给空/不可用的格子：必须可见，不许静默假绿

    def _mark(tool, obj):
        """上游显式标 unavailable 时登记降级。"""
        if isinstance(obj, dict) and obj.get("available") is False:
            degraded.append(f"{tool}:{obj.get('note') or 'available=false'}")
            return True
        return False

    # 未纳入本轮 plan 的工具返回 None：整块跳过，避免把"没采"误报成"采空"
    snap = raw.get("market_snapshot")
    if isinstance(snap, dict) and not _mark("market_snapshot", snap):
        st = snap.get("stats_24h") or {}
        out["btc"] = {
            "price": snap.get("price"),
            "oi_usd": snap.get("open_interest_usd"),
            "funding_avg": (snap.get("funding") or {}).get("average_rate"),
            "exchanges_streaming": snap.get("exchanges_streaming"),
            "high24h": st.get("high24h"), "low24h": st.get("low24h"),
            "change24h_pct": st.get("change24h"),
            "stats_age_minutes": snap.get("stats_age_minutes"),
            "vs_history": snap.get("vs_history"),
        }

    liq = raw.get("market_liquidations")
    if isinstance(liq, dict) and not _mark("market_liquidations", liq):
        perp = liq.get("perp_liquidations") or {}
        lend = liq.get("lending_liquidations") or {}
        named = liq.get("named_liquidations") or []
        out["liquidations"] = {
            "summary": liq.get("summary"),
            "as_of": liq.get("as_of"),
            "window": perp.get("window"),
            "count": perp.get("count"),
            "total_usd": perp.get("total_usd"),
            "long_usd": perp.get("long_usd"),
            "short_usd": perp.get("short_usd"),
            "long_share_pct": perp.get("long_share_pct"),
            "dominant_side": perp.get("dominant_side"),
            "last_hour_usd": perp.get("last_hour_usd"),
            "peak_hour": perp.get("peak_hour"),
            "hourly": _trim(perp.get("hourly")),
            "top_coins": (perp.get("top_coins") or [])[:5],
            "biggest": perp.get("biggest"),
            # 与永续两条车道，绝不能相加
            "lending": {"window": lend.get("window"), "count": lend.get("count"),
                        "total_usd": lend.get("total_usd")},
            "named_wallets": [
                {"wallet": n.get("wallet"), "base": n.get("base"),
                 "side": n.get("side"), "usd": n.get("usd")}
                for n in named[:5]
            ],
        }
        ages.append(_age_minutes(now_utc, liq.get("as_of")))

    fm = raw.get("funding_matrix")
    if isinstance(fm, dict) and not _mark("funding_matrix", fm):
        if not fm.get("per_venue"):
            degraded.append("funding_matrix:empty_per_venue")
        rows = []
        for v in (fm.get("per_venue") or []):
            rate = v.get("funding")
            interval = v.get("interval_h") or 8
            rows.append({
                "exchange": v.get("exchange"),
                "rate_pct": round(rate * 100, 5) if isinstance(rate, (int, float)) else None,
                # 归一化到 8h，避免 1h/8h 交易所直接比大小
                "rate_pct_8h": (round(rate * 100 * (8 / interval), 5)
                                if isinstance(rate, (int, float)) and interval else None),
                "interval_h": interval,
            })
        if rows:
            rows.sort(key=lambda r: (r["rate_pct_8h"] is None, -(r["rate_pct_8h"] or 0)))
            out["funding"] = {"summary": fm.get("summary"),
                              "updated_at": fm.get("updated_at"), "per_venue": rows}
            ages.append(_age_minutes(now_utc, fm.get("updated_at")))

    oi = raw.get("oi_funding_history")
    if isinstance(oi, dict) and not _mark("oi_funding_history", oi):
        pts = oi.get("open_interest") or []
        out["oi_path"] = {
            "summary": oi.get("summary"),
            "oi_change_pct_24h": oi.get("oi_change_pct"),
            "points": _trim(pts),
        }
        ages.append(_age_minutes(now_utc, pts[-1].get("t") if pts else None))

    radar = raw.get("whale_radar")
    if isinstance(radar, dict) and not radar.get("windows"):
        degraded.append("whale_radar:empty_windows")
    elif isinstance(radar, dict):
        windows = {}
        for win, rows in (radar.get("windows") or {}).items():
            windows[win] = [
                {"coin": r.get("coin"), "direction": r.get("direction"),
                 "unusual": r.get("unusual"), "net_usd": r.get("netUsd"),
                 "total_usd": r.get("totalUsd"), "multiple": r.get("multiple"),
                 "z": r.get("z"), "venues": r.get("venues"),
                 "blurred": r.get("blurred", False)}
                for r in (rows[:8] if isinstance(rows, list) else [])
            ]
        out["whale_radar"] = {
            "summary": radar.get("summary"),
            "free_coins": radar.get("freeCoins"),
            "locked_count": radar.get("lockedCount"),
            "blurred_magnitude": radar.get("blurredMagnitude"),
            "windows": windows,
        }
        ages.append(_age_minutes(now_utc, radar.get("generatedAt")))

    news = raw.get("crypto_news")
    if isinstance(news, dict) and not _mark("crypto_news", news):
        hs = news.get("headlines") or []
        out["news"] = {
            "sentiment": news.get("sentiment"),
            "score": news.get("sentiment_score"),
            "summary": news.get("summary"),
            "newest_published": hs[0].get("published") if hs else None,
            "newest_title": hs[0].get("title") if hs else None,
        }

    out["provenance_age_minutes"] = max([a for a in ages if a is not None], default=None)
    out["degraded_tools"] = degraded or None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="CoinLobster 采集器（外部验证层）")
    ap.add_argument("--json", action="store_true", help="只打印工件 JSON")
    ap.add_argument("--if-stale-minutes", type=float, default=None,
                    help="仅当上次采集比这个值更旧时才采（供分析入口按需调用，避免烧配额）")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="full",
                    help="core=只采清算级联+逐所费率（2 次/轮，适合 cron）；"
                         "full=全量 6 次/轮（适合按需深采）")
    args = ap.parse_args()
    plan = PROFILES[args.profile]

    if args.if_stale_minutes is not None:
        age = artifact_age_minutes()
        if age is not None and age < args.if_stale_minutes:
            print(f"CoinLobster 工件 {age:.1f} 分钟前采集，未过期（阈值 "
                  f"{args.if_stale_minutes:g} 分钟）→ 跳过采集，不消耗额度")
            return 0

    now = datetime.now(TZ)
    now_utc = datetime.now(timezone.utc)
    ts = f"{now.year}年{now.month}月{now.day}日{now.hour:02d}:{now.minute:02d}"
    key = load_key()

    # ① 额度冷却中（当日已打满）→ 不打 RPC、不刷日志，写 quota_cooldown 后 exit 0。
    brk = quota_breaker_active()
    if brk:
        write_degraded_artifact("quota_cooldown",
                                note=f"当日免费额度已用尽，冷却到 {brk.get('until')}",
                                extra={"profile": args.profile, "call_cost": 0})
        print(f"CoinLobster {ts} | 当日免费额度冷却中（到 {brk.get('until')}）→ 本轮不调用，"
              f"保留上次工件（quota_cooldown，不计失败）")
        return 0

    # ② 额度自保：当日剩余额度不够跑完整计划时，按计划顺序保前面（=核心格），
    #    跳过哪些工具**写进工件**（skipped_tools），绝不静默削源。剩余为 0 → 软冷却。
    used = calls_used_today()
    remaining = max(0, DAILY_CALL_BUDGET - used)
    skipped: list[str] = []
    if remaining < len(plan):
        skipped = [tool for tool, _ in plan[remaining:]]
        plan = plan[:remaining]
    if not plan:
        write_degraded_artifact("quota_cooldown",
                                note=f"当日额度已用 {used}/{DAILY_CALL_BUDGET}，剩余不足一次采集",
                                extra={"profile": args.profile, "call_cost": 0,
                                       "skipped_tools": skipped})
        print(f"CoinLobster {ts} | 当日额度已用 {used}/{DAILY_CALL_BUDGET}，剩余不足 → "
              f"本轮不调用（quota_cooldown，不计失败）")
        return 0

    raw, errors = {}, {}
    for tool, params in plan:
        ok, data = _rpc(tool, params, key)
        if ok:
            raw[tool] = data
        else:
            errors[tool] = data
        time.sleep(0.25)
    if raw:
        record_calls(len(raw))

    if not raw:
        if is_daily_quota_error(errors):
            until = arm_quota_breaker("HTTP 429 daily limit reached")
            write_degraded_artifact("quota_cooldown", errors=errors,
                                    note=f"当日免费额度已用尽，冷却到 {until}",
                                    extra={"profile": args.profile, "call_cost": len(plan),
                                           "skipped_tools": skipped or None})
            print(f"CoinLobster {ts} | 当日免费额度已用尽（quota_cooldown）→ 冷却到 {until}，"
                  f"保留上次工件（降级可见，不计失败）")
            return 0
        write_degraded_artifact("unavailable", errors=errors,
                                extra={"profile": args.profile, "call_cost": len(plan)})
        print(f"CoinLobster {ts} | 全部工具失败，保留上次工件（降级可见）")
        return 1

    shaped = _shape(raw, now_utc)
    shaped["ts"] = ts
    shaped["tier"] = "signed_in_free" if key else "keyless"
    age = shaped.get("provenance_age_minutes")
    shaped["delay_minutes"] = int(round(age)) if age is not None else (0 if key else 30)
    shaped["usable_as_live"] = bool(age is not None and age <= LIVE_THRESHOLD_MIN)
    shaped["partial_errors"] = errors or None
    shaped["call_cost"] = len(plan)
    shaped["profile"] = args.profile
    # 2026-09-16：额度自保跳过的工具与当日用量必须可见（不静默削源）。
    shaped["skipped_tools"] = skipped or None
    shaped["budget_used_today"] = calls_used_today()
    shaped["budget"] = DAILY_CALL_BUDGET

    write_source_artifact(
        str(ARTIFACT), SOURCE_ID, shaped,
        status="live", captured_at=int(time.time() * 1000),
        error=json.dumps(errors, ensure_ascii=False) if errors else None,
        symbol="BTC")

    if args.json:
        print(json.dumps(shaped, ensure_ascii=False, indent=2))
        return 0

    btc = shaped["btc"]
    liq = shaped["liquidations"]
    radar_rows = (shaped["whale_radar"].get("windows") or {}).get("4h") or []
    unusual = [r["coin"] for r in radar_rows if r.get("unusual")]
    head = f"CoinLobster {ts} [{args.profile}] |"
    if btc.get("price"):
        head += (f" BTC {btc.get('price')} OI ${(btc.get('oi_usd') or 0) / 1e9:.2f}B")
    head += (f" 24h清算 ${(liq.get('total_usd') or 0) / 1e6:.0f}M"
             f" (多占 {liq.get('long_share_pct')}%)")
    print(head)
    print(f"  档位 {shaped['tier']} | 实测延迟 {shaped['delay_minutes']} 分钟 "
          f"| 可当实时 {shaped['usable_as_live']}")
    ven = (shaped["funding"].get("per_venue") or [])
    if ven:
        print(f"  费率8h最高 {ven[0]['exchange']} {ven[0]['rate_pct_8h']}% "
              f"| 最低 {ven[-1]['exchange']} {ven[-1]['rate_pct_8h']}%")
    print(f"  异动币(4h) {','.join(unusual) or '无'} | "
          f"情绪 {shaped['news'].get('sentiment')}({shaped['news'].get('score')})")
    deg = shaped.get("degraded_tools")
    if errors or deg:
        parts = []
        if errors:
            parts.append(f"调用失败 {list(errors)}")
        if deg:
            parts.append(f"上游空/不可用 {deg}")
        print(f"  降级：{' | '.join(parts)}")
    return 0

# ── 读侧：卡面/消费方用的三态判定（纯文件读，不发网络请求）──────────────────
# 与采集侧的两个概念必须分开：
#   payload.usable_as_live  = 采集当刻上游数据是否实时（上游延迟 ≤ 5 分钟）
#   读侧 state             = 工件采集距今多久（cron 20 分钟一轮，阈值取 25 分钟）
READ_FRESH_MINUTES = 25.0      # ≤ 25 分钟 = 新鲜（对齐 cron 9,29,49 的 20 分钟周期 + 余量）
READ_STALE_MINUTES = 90.0      # 25–90 = 陈旧（可作背景，不许当实时）；> 90 = 不可用


def read_state(fresh_minutes: float = READ_FRESH_MINUTES,
               stale_minutes: float = READ_STALE_MINUTES) -> tuple[dict, float | None, str]:
    """读工件并判定读侧三态。返回 (payload, read_age_minutes, state)。

    state: "live"(新鲜) / "stale"(陈旧) / "unavailable"(缺失、超龄或信封非 live)。
    工件缺失、损坏、超龄一律 unavailable —— 绝不拿旧缓存冒充实时。
    """
    try:
        env = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, None, "unavailable"
    if not isinstance(env, dict):
        return {}, None, "unavailable"
    payload = env.get("payload") if isinstance(env.get("payload"), dict) else env
    age = artifact_age_minutes()
    if age is None or str(env.get("_source_status") or "live") != "live":
        return payload, age, "unavailable"
    if age > stale_minutes:
        return payload, age, "unavailable"
    return payload, age, ("live" if age <= fresh_minutes else "stale")


def read_evidence(symbol: str = "BTC", **kwargs) -> tuple[str, str]:
    """卡面 ③ 多源表「外部验证」行的读数。返回 (text, state)。

    只服务 BTC（采集器即 BTC 口径）；其它品种返回空串 —— 不占位、不拿 BTC 冒充。
    陈旧态照样给数，但必须带读数年龄，让卡面自己说清「这是背景不是实时」。
    """
    if "BTC" not in str(symbol or "").upper():
        return "", "unavailable"
    payload, age, state = read_state(**kwargs)
    if state == "unavailable" or not isinstance(payload, dict):
        return "", "unavailable"
    liq = payload.get("liquidations") or {}
    total = liq.get("total_usd")
    if not total:
        return "", "unavailable"
    parts = [f"级联 ${total / 1e6:.0f}M"]
    if liq.get("long_share_pct") is not None:
        _dom = {"long": "多单", "short": "空单"}.get(
            str(liq.get("dominant_side") or "").lower(), "多单")
        parts.append(f"{_dom}占{liq.get('long_share_pct')}%")
    venues = (payload.get("funding") or {}).get("per_venue") or []
    rates = [v.get("rate_pct_8h") for v in venues if v.get("rate_pct_8h") is not None]
    if rates:
        parts.append(f"费8h {max(rates):.4f}~{min(rates):.4f}%")
    if payload.get("degraded_tools"):
        parts.append("部分降级")
    text = " · ".join(parts)
    if state == "stale":
        text += f"（工件 {age:.0f} 分前·仅背景）"
    elif payload.get("usable_as_live") is False:
        text += "（上游非实时）"
    return text, state


if __name__ == "__main__":
    sys.exit(main())
