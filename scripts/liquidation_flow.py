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
        try:
            res = fetch_recent(coin, pages=pages, timeout=timeout)
        except Exception as exc:
            errors.append(f"{coin}: {type(exc).__name__}: {exc}")
            if old_events:
                # 保留上一轮事件（标注降级），不伪造新数据
                record["coins"][coin] = {
                    "ct_val": float((prev_coins.get(coin) or {}).get("ct_val") or 0) or
                    float(CT_VAL_FALLBACK.get(coin, 0.0)),
                    "events": old_events,
                    "stale": True,
                }
            continue
        merged = merge_events(old_events, res["events"], now_ms)
        record["coins"][coin] = {"ct_val": res["ct_val"], "events": merged, "stale": False}
    if errors:
        record["status"] = "stale_cache" if record["coins"] else "unavailable"
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
