#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
只读套利扫描器（per-DEX 资金费率 / 价差）—— 模板与已验证实现
数据面：任何免登录 JSON 的套利扫描站（下面 BASE 换成目标站；本实现按 perpdexlist.com 的实测端点写）
口径铁律：
  1) 只用「已实现资金费」(settled_*)，不用现价差 / 年化快照列
  2) 排除 suspect 与价差 > 5% 的「同名不同工具」对
  3) 输出必须带双边 OI / 成交量 / 场所，以及「成本 → 回本天数」
  4) 取不到的数标 ? / None，绝不当 0

用法：python perp_dex_arb_scan.py [min_vol_usd] [top_n] [--majors BTC,ETH,SOL,HYPE]
依赖：仅标准库；境外站需本机代理（默认 127.0.0.1:7897）
"""
import json, csv, sys, time, urllib.parse, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor

BASE = "https://perpdexlist.com"
PROXY = "http://127.0.0.1:7897"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))  # 显式代理，勿用 ProxyHandler({})

MIN_VOL = float(sys.argv[1]) if len(sys.argv) > 1 else 500_000
TOP_N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
MAJORS = ["BTC", "ETH", "SOL", "HYPE"]

# ---- 免登录端点（实测）-------------------------------------------------
# /api/dashboard/opportunities-v2?mode=basis|funding&sort=<字段>&page=&per_page=&desc=&filters=
#     sort 可用：in_pct(开仓价差) / funding_spread_apr / settled_spread_24h|7d|30d
#     filters 形如 long_vol:100000::;short_vol:100000::
# /api/dashboard/markets-v2?asset=<币>      → 全场所实时 bid/ask/rate/interval_h/volume_24h/open_interest + age
# /api/execcost/live?asset=<币>&sizes=10000,100000,1000000
# /api/execcost/window?asset=<币>&days=<n>  /  /api/execcost/best?days=&size=&class=
# /api/venues                                → 含推荐码，评估变现关系时引用
# ----------------------------------------------------------------------


def api(path, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers={
                "User-Agent": UA, "Accept": "application/json",
                "Referer": BASE + "/arbitrage"})
            with OPENER.open(req, timeout=45) as r:
                return json.loads(r.read())
        except Exception as e:                       # 境外源 TLS 抖动是常态
            last = e
            time.sleep(2 + 2 * i)
    raise last


_CACHE = {}


def prefetch(assets):
    """并行预取：串行取数会撞工具超时。"""
    def one(a):
        out = {}
        for key, path in (("markets", "/api/dashboard/markets-v2?asset=%s"),
                          ("execcost", "/api/execcost/live?asset=%s&sizes=100000")):
            try:
                out[key] = api(path % urllib.parse.quote(a))
            except Exception as e:
                out[key] = {"error": str(e)}
        return a, out
    with ThreadPoolExecutor(max_workers=8) as ex:
        for a, out in ex.map(one, assets):
            _CACHE[a] = out


def live_spread(asset, min_vol=MIN_VOL):
    """全场所实时报价里选最负（做多）/ 最正（做空）的资金费腿，归一化到 %/小时。"""
    m = _CACHE.get(asset, {}).get("markets")
    if m is None:
        try:
            m = api("/api/dashboard/markets-v2?asset=%s" % urllib.parse.quote(asset))
        except Exception:
            return None
    mk = [x for x in m.get("markets", [])
          if (x.get("volume_24h") or 0) >= min_vol and x.get("rate") is not None
          and (x.get("interval_h") or 0) > 0]
    if len(mk) < 2:
        return None
    per_h = lambda x: x["rate"] / x["interval_h"]
    lo, sh = min(mk, key=per_h), max(mk, key=per_h)
    return {"long": lo, "short": sh, "net_per_h": per_h(sh) - per_h(lo)}


def round_trip_bp(asset):
    """$100k 开+平成本：最便宜两场所的 (long_total_bps + short_total_bps) 之和。取不到返回 None。"""
    d = _CACHE.get(asset, {}).get("execcost")
    if not d or "legs" not in d:                     # 并行取数失败 → 串行补一次
        try:
            d = api("/api/execcost/live?asset=%s&sizes=100000" % urllib.parse.quote(asset))
            _CACHE.setdefault(asset, {})["execcost"] = d
        except Exception:
            return None
    legs = []
    for leg in d.get("legs") or []:
        t = next((x for x in (leg.get("tiers") or []) if x.get("notional_usd") == 100000), None)
        if not t:
            continue
        tl, ts = t.get("long_total_bps"), t.get("short_total_bps")
        if tl is None or ts is None:
            continue
        legs.append((leg["exchange"], leg.get("symbol"), tl, ts))
    if len(legs) < 2:
        return None
    legs.sort(key=lambda x: x[2] + x[3])
    return sum(x[2] + x[3] for x in legs[:2])


def main():
    j = api("/api/dashboard/opportunities-v2?mode=funding&sort=settled_spread_7d"
            "&page=1&per_page=500&desc=true")
    gen = (j.get("generated_at") or "")[:19] + "Z"
    cands = []
    for r in j["opportunities"]:
        L, S = r["long"], r["short"]
        if L.get("class") != "CRYPTO" or S.get("class") != "CRYPTO":
            continue                                  # 排除 RWA/股票同名对
        if (L.get("volume_24h") or 0) < MIN_VOL or (S.get("volume_24h") or 0) < MIN_VOL:
            continue
        if r.get("suspect") or (r.get("basis_pct") or 0) > 5:
            continue
        if r.get("settled_spread_7d") is None or r.get("settled_spread_30d") is None:
            continue
        cands.append(r)
    cands.sort(key=lambda r: r["settled_spread_7d"], reverse=True)
    cands = cands[:TOP_N]

    prefetch(list(dict.fromkeys(MAJORS + [r["asset"] for r in cands])))

    print("只读套利扫描 | 本地 %s | 数据时间 %s | 门槛：双边24h量≥$%s"
          % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), gen, f"{MIN_VOL:,.0f}"))
    print("\nA) 主流币实时最优对冲（资金费归一化 %/h）")
    rows = []
    for asset in MAJORS:
        ls = live_spread(asset)
        if not ls:
            print("   %-5s 无足够流动性的双腿" % asset)
            continue
        net_day = ls["net_per_h"] * 100 * 24
        rt = round_trip_bp(asset)
        be = (rt / 100.0) / net_day if (rt and net_day > 0) else None
        print("   %-5s 多 %-16s %+8.5f%%/h (量$%.1fM/OI$%.1fM) | 空 %-16s %+8.5f%%/h (量$%.1fM/OI$%.1fM)"
              " → 净 %+.1f bp/天 (%+.0f%% 年化) 成本 %s 回本 %s"
              % (asset, ls["long"]["exchange"], ls["long"]["rate"] / ls["long"]["interval_h"] * 100,
                 (ls["long"].get("volume_24h") or 0) / 1e6, (ls["long"].get("open_interest") or 0) / 1e6,
                 ls["short"]["exchange"], ls["short"]["rate"] / ls["short"]["interval_h"] * 100,
                 (ls["short"].get("volume_24h") or 0) / 1e6, (ls["short"].get("open_interest") or 0) / 1e6,
                 net_day * 100, net_day * 365,
                 ("%.1f bp" % rt) if rt is not None else "?",
                 ("%.1f 天" % be) if be else "—"))
        rows.append({"asset": asset, "kind": "major",
                     "live_long": "%s:%s %.5f%%/%sh" % (ls["long"]["exchange"], ls["long"]["symbol"],
                                                        ls["long"]["rate"] * 100, ls["long"]["interval_h"]),
                     "live_short": "%s:%s %.5f%%/%sh" % (ls["short"]["exchange"], ls["short"]["symbol"],
                                                         ls["short"]["rate"] * 100, ls["short"]["interval_h"]),
                     "net_pct_per_day": round(net_day, 4), "round_trip_bp": rt,
                     "breakeven_days": round(be, 2) if be else None})

    print("\nB) 按 7 天已实现资金费排序（现价差 + 成本核对）")
    print("%-9s %-22s %-22s %8s %8s %8s %10s %8s" %
          ("币种", "命中多头腿", "命中空头腿", "7d实际%", "30d实际%", "成本bp", "净bp/天", "回本天"))
    for r in cands:
        L, S = r["long"], r["short"]
        ls = live_spread(r["asset"])
        rt = round_trip_bp(r["asset"])
        net_day = (ls["net_per_h"] * 100 * 24) if ls else None
        be = (rt / 100.0) / net_day if (rt and net_day and net_day > 0) else None
        print("%-9s %-22s %-22s %8.3f %8.3f %8s %10s %8s"
              % (r["asset"], "%s %s" % (L["exchange"], str(L["symbol"])[:10]),
                 "%s %s" % (S["exchange"], str(S["symbol"])[:10]),
                 r["settled_spread_7d"] * 100, r["settled_spread_30d"] * 100,
                 ("%.1f" % rt) if rt is not None else "?",
                 ("%+.1f" % (net_day * 100)) if net_day is not None else "?",
                 ("%.1f" % be) if be else "—"))
        rows.append({"asset": r["asset"], "kind": "candidate",
                     "realized_7d_pct": round(r["settled_spread_7d"] * 100, 4),
                     "realized_30d_pct": round(r["settled_spread_30d"] * 100, 4),
                     "listed_long": "%s:%s" % (L["exchange"], L["symbol"]),
                     "listed_short": "%s:%s" % (S["exchange"], S["symbol"]),
                     "net_pct_per_day": round(net_day, 4) if net_day is not None else None,
                     "round_trip_bp": rt,
                     "breakeven_days": round(be, 2) if be else None})

    with open("perp_dex_arb_report.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at_utc": gen, "min_vol": MIN_VOL, "rows": rows},
                  f, ensure_ascii=False, indent=1)
    with open("perp_dex_arb_report.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\n已保存 perp_dex_arb_report.json / .csv（本地留档；推 TG 需用户单独授权）")


if __name__ == "__main__":
    main()
