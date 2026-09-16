#!/usr/bin/env python3
"""OKX 公共逐笔强平读取器（免 key / 免登录）—— 清算维度的第二源。

为什么存在
----------
清算渠道盘点（2026-09-15）结论：CoinGlass 网页端热力图只覆盖 `Binance_BTCUSDT`
（其它品种服务端 `code=40000` 门控），且只给「24h 堆积强度」（相对刻度，非 USD）。
要回答「当下这波是谁在被强平」，需要**逐笔强平事件**。OKX 公共接口
`/api/v5/public/liquidation-orders` 免 key 提供最近约 24h 的强平明细，覆盖
BTC / ETH / SOL 等 SWAP，2026-09-15 实测直连与代理均可达。

契约（2026-09-15 实测）
----------------------
- `instType=SWAP` + `uly=<COIN>-USDT` + `state=filled` + `limit<=100`（500 回 HTTP 400）
- 每页最多 100 笔、按时间倒序；往旧翻页用 `after=<最旧一笔 ts>`，`before` 用于取更新数据
- `details[] = {bkPx 破产价, posSide long/short, side buy/sell, sz 张数, ts 毫秒}`
- 方向语义：`posSide=long, side=sell` → 多单被强平；`posSide=short, side=buy` → 空单被强平
- 名义估算 = `sz × ctVal × bkPx`；`ctVal` 实测 BTC 0.01 / ETH 0.1 / SOL 1
  （来源 `/api/v5/public/instruments`）。该值是**估算**，卡面必须带「估算」口径，
  不得写成交易所口径的爆仓金额。

缓存与降级
----------
`data/liquidation_flow.json` 保存**滚动 24h 事件窗**（每轮增量合并去重），因为交易所
单页只回 100 笔、且只保留最近约 24h。cron 断档期间会丢事件 —— 缓存里的
`coverage_from` 如实记录实际覆盖起点，不假装全天齐全。
状态四态对齐系统降级契约：live / stale_cache / unavailable（cache 仅用于进程内回退）。

仅用于人工分析，不接自动下单。
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

SOURCE = "okx_public"
OKX_BASE = "https://www.okx.com"
LIQ_PATH = "/api/v5/public/liquidation-orders"
INSTR_PATH = "/api/v5/public/instruments"
PAGE_LIMIT = 100                  # OKX 硬上限：limit=500 回 HTTP 400（实测）
WINDOW_S = 24 * 3600              # 事件窗 24h
CACHE_MAX_AGE_S = 1800            # 超过 30 分钟即视为陈旧，卡面不得照抄
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_REPO_ROOT, "data", "liquidation_flow.json")

# 合约面值兜底（运行时以 /public/instruments 返回为准）
CT_VAL_FALLBACK = {"BTC": 0.01, "ETH": 0.1, "SOL": 1.0}
DEFAULT_COINS = ("BTC", "ETH")


def _opener():
    """沿用仓库约定：Hermes 环境带 HTTPS_PROXY 时走系统代理，否则直连。"""
    if os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"):
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(path: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = OKX_BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "accept": "application/json"})
    with _opener().open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def contract_value(coin: str, timeout: int = 20) -> float:
    """合约面值（每张对应的币数）。取不到时回退内置表，不猜 0。"""
    inst = f"{coin.upper()}-USDT-SWAP"
    try:
        payload = _get(INSTR_PATH, {"instType": "SWAP", "instId": inst}, timeout=timeout)
        row = (payload.get("data") or [{}])[0]
        val = float(row.get("ctVal") or 0)
        if val > 0:
            return val
    except Exception:
        pass
    return float(CT_VAL_FALLBACK.get(coin.upper(), 0.0))


def fetch_page(uly: str, after_ts: int | None = None, limit: int = PAGE_LIMIT,
               timeout: int = 20) -> list[dict[str, Any]]:
    """拉一页强平明细（≤100 笔，时间倒序）。`after_ts` 往旧翻页。"""
    params: dict[str, Any] = {"instType": "SWAP", "uly": uly, "state": "filled",
                              "limit": min(int(limit), PAGE_LIMIT)}
    if after_ts:
        params["after"] = str(int(after_ts))
    payload = _get(LIQ_PATH, params, timeout=timeout)
    code = str(payload.get("code"))
    if code != "0":
        raise ValueError(f"OKX 返回异常：code={code} msg={payload.get('msg')}")
    rows: list[dict[str, Any]] = []
    for group in payload.get("data") or []:
        rows.extend(group.get("details") or [])
    return rows


def normalize(rows: list[dict[str, Any]], ct_val: float) -> list[list[Any]]:
    """明细 → `[ts_ms, side, price, contracts]`；`side` 是**被强平的方向**。

    名义估算在统计阶段按 `contracts × ct_val × price` 现算，避免缓存里存派生值。
    """
    out: list[list[Any]] = []
    for row in rows:
        try:
            pos_side = str(row.get("posSide") or "").lower()
            if pos_side not in ("long", "short"):
                continue
            ts = int(row.get("ts") or row.get("time") or 0)
            price = float(row.get("bkPx") or 0)
            contracts = float(row.get("sz") or 0)
        except (TypeError, ValueError):
            continue
        if ts <= 0 or price <= 0 or contracts <= 0:
            continue
        out.append([ts, pos_side, round(price, 6), round(contracts, 8)])
    return out


def _event_key(ev: list[Any]) -> tuple:
    return (int(ev[0]), str(ev[1]), float(ev[2]), float(ev[3]))


def merge_events(old: list[list[Any]], new: list[list[Any]], now_ms: int,
                 window_s: int = WINDOW_S) -> list[list[Any]]:
    """增量合并 + 去重 + 裁掉窗口外；返回按时间升序的事件表。"""
    floor = int(now_ms - window_s * 1000)
    seen: dict[tuple, list[Any]] = {}
    for ev in list(old or []) + list(new or []):
        try:
            if int(ev[0]) < floor:
                continue
            seen[_event_key(ev)] = [int(ev[0]), str(ev[1]), float(ev[2]), float(ev[3])]
        except (TypeError, ValueError, IndexError):
            continue
    return [seen[k] for k in sorted(seen)]


def _notional_usd(ev: list[Any], ct_val: float) -> float:
    return float(ev[3]) * float(ct_val) * float(ev[2])


def stats(events: list[list[Any]], ct_val: float, now_ms: int | None = None) -> dict[str, Any]:
    """窗口统计：近 1h / 24h 的多单与空单强平名义（估算）+ 最大单笔 + 最近一笔。"""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)

    def _window(secs: int) -> dict[str, Any]:
        floor = now_ms - secs * 1000
        long_usd = short_usd = 0.0
        long_n = short_n = 0
        for ev in events:
            if int(ev[0]) < floor:
                continue
            usd = _notional_usd(ev, ct_val)
            if ev[1] == "long":
                long_usd += usd
                long_n += 1
            else:
                short_usd += usd
                short_n += 1
        return {"long_usd": round(long_usd, 2), "short_usd": round(short_usd, 2),
                "long_count": long_n, "short_count": short_n,
                "net_usd": round(long_usd - short_usd, 2), "count": long_n + short_n}

    biggest = None
    if events:
        ev = max(events, key=lambda e: _notional_usd(e, ct_val))
        biggest = {"ts": int(ev[0]), "side": ev[1], "price": ev[2],
                   "contracts": ev[3], "notional_usd": round(_notional_usd(ev, ct_val), 2)}
    last = None
    if events:
        ev = max(events, key=lambda e: int(e[0]))
        last = {"ts": int(ev[0]), "side": ev[1], "price": ev[2],
                "contracts": ev[3], "notional_usd": round(_notional_usd(ev, ct_val), 2)}
    total = len(events)
    coverage_s = 0.0
    if total:
        coverage_s = (max(int(e[0]) for e in events) - min(int(e[0]) for e in events)) / 1000
    return {
        "ct_val": ct_val,
        "coverage_from": int(min((int(e[0]) for e in events), default=0)),
        "coverage_to": int(max((int(e[0]) for e in events), default=0)),
        "coverage_hours": round(coverage_s / 3600, 2),
        "events": total,
        "w1h": _window(3600),
        "w24h": _window(WINDOW_S),
        "biggest": biggest,
        "last": last,
        "notional_note": "名义为估算（张数×合约面值×破产价）",
    }


def fetch_recent(coin: str = "BTC", pages: int = 3, limit: int = PAGE_LIMIT,
                 timeout: int = 20) -> dict[str, Any]:
    """连续翻页取最近 `pages × limit` 笔强平。"""
    coin = coin.upper()
    uly = f"{coin}-USDT"
    ct_val = contract_value(coin, timeout=timeout)
    collected: list[list[Any]] = []
    after: int | None = None
    for _ in range(max(1, int(pages))):
        rows = fetch_page(uly, after_ts=after, limit=limit, timeout=timeout)
        if not rows:
            break
        collected.extend(normalize(rows, ct_val))
        oldest = min(int(r.get("ts") or 0) for r in rows if r.get("ts"))
        if not oldest or (after is not None and oldest >= after):
            break
        after = oldest
    return {"coin": coin, "ct_val": ct_val, "events": collected}


def refresh_cache(coins: tuple[str, ...] = DEFAULT_COINS, pages: int = 6,
                  cache_path: str | None = None, timeout: int = 20) -> dict[str, Any]:
    """刷一轮并落盘（增量合并滚动 24h 窗）。单个品种失败不影响其它品种。"""
    path = cache_path or CACHE_PATH
    now_ms = int(time.time() * 1000)
    prev = load_cache(path)
    prev_coins = (prev or {}).get("coins") or {}
    now_s = int(time.time())
    record: dict[str, Any] = {"source": SOURCE, "fetched_at": now_s, "updated_epoch": now_s,
                              "status": "live", "error": None, "coins": {}}
    errors = []
    for coin in coins:
        coin = coin.upper()
        old_events = ((prev_coins.get(coin) or {}).get("events")) or []
        res = None
        last_exc: Exception | None = None
        for attempt in (1, 2, 3):
            # 2026-09-15：实测单次 SSL 抖动（UNEXPECTED_EOF_WHILE_READING）会让整轮降级，
            # 而该降级此前被写成**顶层** status → 一个品种失败就把 BTC 卡面清算行整行抹掉。
            # 抖动出现频率不低（当日晚 20:30、22:50 各一次），故给两次重试。
            try:
                res = fetch_recent(coin, pages=pages, timeout=timeout)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        if res is None:
            errors.append(f"{coin}: {type(last_exc).__name__}: {last_exc}")
            if old_events:
                # 保留上一轮事件（标注降级），不伪造新数据
                record["coins"][coin] = {
                    "ct_val": float((prev_coins.get(coin) or {}).get("ct_val") or 0) or
                    float(CT_VAL_FALLBACK.get(coin, 0.0)),
                    "events": old_events,
                    "stale": True,
                    "status": "stale_cache",
                }
            continue
        merged = merge_events(old_events, res["events"], now_ms)
        record["coins"][coin] = {"ct_val": res["ct_val"], "events": merged,
                                 "stale": False, "status": "live"}
    # 顶层状态 = 品种级聚合：**任一品种 live 即 live**。卡面与看门狗各按自己需要的粒度读：
    # 卡面读 coins.<COIN>.status（单源失败只影响该品种），看门狗读顶层 status。
    live_coins = [c for c, v in (record["coins"] or {}).items() if (v or {}).get("status") == "live"]
    if live_coins:
        record["status"] = "live"
        record["live_coins"] = live_coins
    elif record["coins"]:
        record["status"] = "stale_cache"
    else:
        record["status"] = "unavailable"
    if errors:
        record["error"] = " | ".join(errors)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return record


def load_cache(cache_path: str | None = None) -> dict[str, Any] | None:
    path = cache_path or CACHE_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _fmt_usd(value: float) -> str:
    v = float(value or 0)
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _span_label(coverage_hours: float, target_h: float) -> str:
    """覆盖不足目标窗口时必须把真实覆盖写进标签：不把 4 小时的数据标成「近24h」。"""
    ch = float(coverage_hours or 0)
    if ch >= target_h * 0.95:
        return f"近{target_h:g}h"
    if target_h <= 1:
        return f"窗{max(ch * 60, 1):.0f}m"
    return f"窗{max(ch, 0.1):.1f}h"


def flow_text(coin: str = "BTC", cache_path: str | None = None,
              max_age_s: int = CACHE_MAX_AGE_S, now: float | None = None) -> str:
    """卡面短句（三态可见，不拿旧值冒充实时）：

      新鲜 → `清算流1h 多$1.2M/空$0.4M · 24h 多$8.9M/空$6.1M · 近笔 77188 空$0.06M`
      陈旧 → `清算流 陈旧(需刷新)`
      不可用 → `清算流 不可用`
    """
    coin = str(coin or "").upper()
    rec = load_cache(cache_path)
    if not rec:
        return "清算流 不可用"
    age = (now if now is not None else time.time()) - float(rec.get("fetched_at") or 0)
    if age > max_age_s:
        return "清算流 陈旧(需刷新)"
    info = ((rec.get("coins") or {}).get(coin)) or {}
    events = info.get("events") or []
    if not events:
        return "清算流 不可用"
    ct_val = float(info.get("ct_val") or CT_VAL_FALLBACK.get(coin, 0.0))
    st = stats(events, ct_val)
    w1, w24 = st["w1h"], st["w24h"]
    covered_h = float(st.get("coverage_hours") or 0)
    bits = [f"清算流{_span_label(covered_h, 1)} 多{_fmt_usd(w1['long_usd'])}"
            f"/空{_fmt_usd(w1['short_usd'])}",
            f"{_span_label(covered_h, 24)} 多{_fmt_usd(w24['long_usd'])}"
            f"/空{_fmt_usd(w24['short_usd'])}"]
    last = st["last"]
    if last:
        bits.append(f"近笔 {last['price']:,.0f} {'多' if last['side'] == 'long' else '空'}"
                    f"{_fmt_usd(last['notional_usd'])}")
    if info.get("stale"):
        bits.append("沿用上轮")
    return " · ".join(bits) + "（估算）"


# ── 多源聚合（OKX 逐笔 + 币安 WS 流）2026-09-15 ─────────────────────────────
# OKX 事件第 4 列是**张数**（需 × ctVal × price），币安 WS 第 4 列是**币数**
# （× price 即 USD）。两源口径不同，必须先折成 USD 再合并 —— 否则聚合数是错的。
WS_CACHE_PATH = os.path.join(_REPO_ROOT, "data", "liquidation_ws.json")
WS_MAX_AGE_S = 900                # 采集器每 ≤60s 刷时间戳；15 分钟无更新即视为停摆


def okx_usd_events(events: list[list[Any]], ct_val: float) -> list[list[Any]]:
    """OKX 事件（张数）→ USD 名义事件表。"""
    out: list[list[Any]] = []
    for ev in events or []:
        try:
            out.append([int(ev[0]), str(ev[1]), float(ev[2]),
                        float(ev[3]) * float(ct_val) * float(ev[2])])
        except (TypeError, ValueError, IndexError):
            continue
    return out


def load_ws_usd_events(coin: str = "BTC", cache_path: str | None = None,
                       max_age_s: int = WS_MAX_AGE_S,
                       now: float | None = None) -> dict[str, Any]:
    """读币安 WS 采集器缓存 → USD 名义事件表 `[[ts, side, price, usd], ...]`。

    返回 {status: live|stale_cache|unavailable, events, age_s, error}。状态三态可见，
    陈旧缓存只用于**标注**，卡面不得把它当实时（调用方按 status 决定是否采用）。
    """
    path = cache_path or WS_CACHE_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception as exc:
        return {"status": "unavailable", "events": [], "age_s": None,
                "error": f"{type(exc).__name__}: {exc}"}
    age = (now if now is not None else time.time()) - float(rec.get("updated_epoch") or 0)
    info = ((rec.get("coins") or {}).get(str(coin).upper())) or {}
    events: list[list[Any]] = []
    for row in info.get("events") or []:
        try:
            events.append([int(row[0]), str(row[1]), float(row[2]),
                           float(row[3]) * float(row[2])])
        except (TypeError, ValueError, IndexError):
            continue
    if not events:
        status = "unavailable"
    elif rec.get("status") == "live" and age <= max_age_s:
        status = "live"
    else:
        status = "stale_cache"
    return {"status": status, "events": events, "age_s": round(age, 1),
            "error": None if status == "live" else (rec.get("error") or "缓存陈旧或为空")}


def stats_usd(events_usd: list[list[Any]], now_ms: int | None = None) -> dict[str, Any]:
    """窗口统计（事件已是 USD 名义，不再乘合约面值）。"""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    rows: list[tuple[int, str, float, float]] = []
    for ev in events_usd or []:
        try:
            rows.append((int(ev[0]), str(ev[1]), float(ev[2]), float(ev[3])))
        except (TypeError, ValueError, IndexError):
            continue

    def _window(secs: int) -> dict[str, Any]:
        floor = now_ms - secs * 1000
        long_usd = short_usd = 0.0
        long_n = short_n = 0
        for ts, side, _px, usd in rows:
            if ts < floor:
                continue
            if side == "long":
                long_usd += usd
                long_n += 1
            else:
                short_usd += usd
                short_n += 1
        return {"long_usd": round(long_usd, 2), "short_usd": round(short_usd, 2),
                "long_count": long_n, "short_count": short_n,
                "net_usd": round(long_usd - short_usd, 2), "count": long_n + short_n}

    coverage_s = 0.0
    if rows:
        coverage_s = (max(r[0] for r in rows) - min(r[0] for r in rows)) / 1000
    last = None
    if rows:
        ts, side, px, usd = max(rows, key=lambda r: r[0])
        last = {"ts": ts, "side": side, "price": px, "notional_usd": round(usd, 2)}
    biggest = None
    if rows:
        ts, side, px, usd = max(rows, key=lambda r: r[3])
        biggest = {"ts": ts, "side": side, "price": px, "notional_usd": round(usd, 2)}
    return {"events": len(rows), "coverage_hours": round(coverage_s / 3600, 2),
            "w1h": _window(3600), "w24h": _window(WINDOW_S),
            "last": last, "biggest": biggest,
            "notional_note": "名义为估算（OKX=张数×合约面值×破产价；币安WS=币数×均成交价）"}


def multi_source_text(coin: str = "BTC", okx_cache_path: str | None = None,
                      ws_cache_path: str | None = None,
                      max_age_s: int = CACHE_MAX_AGE_S, now: float | None = None) -> str:
    """卡面短句：**规模口径以 OKX 逐笔为准**，币安 WS 只作存在性附注。

    为什么不让币安进规模合计：币安 forceOrder 流自 2021-04-27 起只推「最多 1 条/秒的
    快照」（官方变更日志），与 OKX 逐笔相加会**系统性低估**币安侧规模 —— 比不给数字更糟。

      新鲜 → `清算流OKX 近1h 多$1.2M/空$0.4M · 窗18.5h … · 近笔 76,869 多$131 · 币安快照3笔/1h`
      OKX 不可用但币安有 → `清算流 币安快照3笔/1h·规模口径不可用(OKX无数据)`
      全不可用 → `清算流 不可用`
    """
    coin = str(coin or "").upper()
    now_s = now if now is not None else time.time()
    rec = load_cache(okx_cache_path)
    okx_events: list[list[Any]] = []
    okx_stale = False
    if rec and (now_s - float(rec.get("fetched_at") or 0)) <= max_age_s:
        info = ((rec.get("coins") or {}).get(coin)) or {}
        raw = info.get("events") or []
        ct_val = float(info.get("ct_val") or CT_VAL_FALLBACK.get(coin, 0.0))
        okx_events = okx_usd_events(raw, ct_val)
        okx_stale = bool(info.get("stale"))
    ws = load_ws_usd_events(coin, cache_path=ws_cache_path, now=now_s)
    ws_events = ws["events"] if ws["status"] == "live" else []
    ws_note = ""
    if ws_events:
        floor = int((now_s - 3600) * 1000)
        recent = [e for e in ws_events if int(e[0]) >= floor]
        ws_note = f"币安快照{len(recent)}笔/1h" if recent else f"币安快照{len(ws_events)}笔/24h"

    if not okx_events:
        if ws_note:
            return f"清算流 {ws_note}·规模口径不可用(OKX无数据)"
        return "清算流 不可用"

    st = stats_usd(okx_events, now_ms=int(now_s * 1000))
    covered_h = float(st.get("coverage_hours") or 0)
    w1, w24 = st["w1h"], st["w24h"]
    bits = [f"清算流OKX {_span_label(covered_h, 1)} 多{_fmt_usd(w1['long_usd'])}"
            f"/空{_fmt_usd(w1['short_usd'])}",
            f"{_span_label(covered_h, 24)} 多{_fmt_usd(w24['long_usd'])}"
            f"/空{_fmt_usd(w24['short_usd'])}"]
    # 近 1h 为 0 且最新事件已超 1 小时：这是「上游停更/接口冻结」而非「市场无强平」。
    # 只印 $0/$0 会被读成后者（实测 2026-09-16 OKX BTC 腿停更 162 分，卡面照印 0）。
    # 数据本身照旧展示，只在读数后面追加事件年龄 —— 降级必须可见，不许静默零值。
    _okx_stalled = False
    if w1["count"] == 0 and st.get("last"):
        _last_age_min = (now_s * 1000 - float(st["last"]["ts"])) / 60000.0
        if _last_age_min >= 60:
            _okx_stalled = True
            bits.append(f"⚠最新事件{_last_age_min:.0f}分前(疑似停更)")
    last = st["last"]
    if last:
        bits.append(f"近笔 {last['price']:,.0f} {'多' if last['side'] == 'long' else '空'}"
                    f"{_fmt_usd(last['notional_usd'])}")
    if okx_stale:
        bits.append("OKX沿用上轮")
    if ws_note:
        # 规模口径唯一是 OKX 逐笔；币安 forceOrder 自 2021 起只推「最多 1 条/秒的快照」，
        # 相加会系统性低估 → 停更期间必须点明「仅存在性」，别让读者拿笔数当规模。
        if _okx_stalled:
            ws_note += "(仅存在性·不计入规模)"
        bits.append(ws_note)
    return " · ".join(bits) + "（估算）"


def summarize(coin: str = "BTC", pages: int = 3) -> str:
    res = fetch_recent(coin, pages=pages)
    st = stats(res["events"], res["ct_val"])
    lines = [f"OKX 逐笔强平 · {res['coin']}-USDT-SWAP · 面值 {res['ct_val']} {res['coin']}/张"
             f" · 本轮取 {len(res['events'])} 笔",
             f"覆盖 {time.strftime('%m-%d %H:%M', time.localtime(st['coverage_from'] / 1000))}"
             f" ~ {time.strftime('%m-%d %H:%M', time.localtime(st['coverage_to'] / 1000))}",
             f"近 1h：多单 {st['w1h']['long_count']} 笔 {_fmt_usd(st['w1h']['long_usd'])}"
             f" / 空单 {st['w1h']['short_count']} 笔 {_fmt_usd(st['w1h']['short_usd'])}",
             f"{_span_label(st['coverage_hours'], 24)}：多单 {st['w24h']['long_count']} 笔"
             f" {_fmt_usd(st['w24h']['long_usd'])}"
             f" / 空单 {st['w24h']['short_count']} 笔 {_fmt_usd(st['w24h']['short_usd'])}"]
    if st["biggest"]:
        b = st["biggest"]
        lines.append(f"最大单笔：{time.strftime('%m-%d %H:%M', time.localtime(b['ts'] / 1000))} "
                     f"{'多' if b['side'] == 'long' else '空'}单 {b['contracts']} 张 @{b['price']:,.1f}"
                     f" ≈ {_fmt_usd(b['notional_usd'])}")
    lines.append("名义为估算（张数×合约面值×破产价），非交易所口径爆仓额")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="OKX 公共逐笔强平读取器（免 key）")
    ap.add_argument("--coin", default="BTC", help="BTC / ETH / SOL …")
    ap.add_argument("--pages", type=int, default=6, help="翻页数（每页 100 笔）")
    ap.add_argument("--refresh-cache", action="store_true", help="刷新滚动缓存并落盘")
    ap.add_argument("--coins", default="BTC,ETH", help="--refresh-cache 的品种列表")
    ap.add_argument("--json-out", default=None, help="原始归一化 JSON 落盘（调试）")
    args = ap.parse_args()

    if args.refresh_cache:
        coins = tuple(c.strip().upper() for c in args.coins.split(",") if c.strip())
        rec = refresh_cache(coins, pages=args.pages)
        print(f"[{rec['status']}] 刷新 {','.join(coins)}"
              f" 事件数 " + ", ".join(f"{c}:{len((v or {}).get('events') or [])}"
                                     for c, v in (rec["coins"] or {}).items()))
        if rec.get("error"):
            print("error:", rec["error"])
        for coin in coins:
            print(" ", flow_text(coin))
        return 0 if rec["status"] == "live" else 1

    try:
        print(summarize(args.coin, pages=args.pages))
    except Exception as exc:
        print(f"[unavailable] {args.coin}: {type(exc).__name__}: {exc}")
        return 1
    if args.json_out:
        res = fetch_recent(args.coin, pages=args.pages)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
        print(f"\n归一化 JSON 已写入 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
