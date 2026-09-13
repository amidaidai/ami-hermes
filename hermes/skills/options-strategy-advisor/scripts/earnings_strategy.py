#!/usr/bin/env python3
"""财报期期权策略分析 —— options-strategy-advisor 的 scripts/earnings_strategy.py。

2026-09-13 补齐：SKILL.md 的「Scripts」段一直列着本文件，但从未随技能落地。

对应 SKILL.md 的 Use Case 3（"Should I trade options before NVDA earnings?"）：
  1. 取财报日期与距今天数（可用 --ticker 由 FMP 取，也可 --days-to-earnings 直接给）
  2. 用现价 + IV + DTE 估「隐含预期波动幅度」（expected move）
  3. 横向对比跨式 / 宽跨式 / 铁鹰 的成本、平衡点与最大亏损
  4. 显式给出 IV 波动率压缩（IV crush）风险提示
  5. 有历史数据时算 HV，做 IV vs HV 的贵/便宜判断

用法：

    # 手工输入（无需 API key）
    python3 scripts/earnings_strategy.py --stock-price 180 --iv 0.60 \
        --days-to-earnings 3 --days 7

    # 由 FMP 取现价与财报日
    python3 scripts/earnings_strategy.py --ticker NVDA --api-key $FMP_API_KEY --iv 0.55
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from black_scholes import bs_price, normalise_vol  # noqa: E402

MULTIPLIER = 100
SECRETS = Path("D:/Hermes agent/hermes/secrets")
LOCAL_PROXY = os.environ.get("TANGXI_PROXY", "http://127.0.0.1:7897")


def _read_secret(name: str) -> str:
    try:
        return (SECRETS / name).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _fmp(path: str, api_key: str):
    url = f"https://financialmodelingprep.com/stable/{path}&apikey={api_key}" \
        if "?" in path else f"https://financialmodelingprep.com/stable/{path}?apikey={api_key}"
    last: Exception | None = None
    for use_proxy in (False, True):
        handlers = ([urllib.request.ProxyHandler({"http": LOCAL_PROXY, "https": LOCAL_PROXY})]
                    if use_proxy else [urllib.request.ProxyHandler({})])
        try:
            with urllib.request.build_opener(*handlers).open(
                    urllib.request.Request(url, headers={"User-Agent": "tangxi-options/1.0"}),
                    timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: PERF203
            last = exc
    raise RuntimeError(f"FMP 请求失败（直连与代理均不通）: {last}")


def fetch_profile(ticker: str, api_key: str) -> dict:
    """取现价与股息率。"""
    data = _fmp(f"quote?symbol={urllib.parse.quote(ticker)}", api_key)
    if isinstance(data, dict) and data.get("Error Message"):
        raise RuntimeError(f"FMP 拒绝: {data['Error Message']}")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"FMP 返回空: {str(data)[:120]}")
    row = data[0]
    return {"price": float(row.get("price") or 0),
            "dividend_yield": float(row.get("dividendYield") or 0) / 100.0}


def fetch_earnings_days(ticker: str, api_key: str) -> tuple[int | None, str]:
    """距下一次财报的日历天数。返回 (天数, 状态说明) —— 取不到就如实说明原因。

    2026-09-13 实测踩坑记录：
      · ``/stable/earnings-calendar?symbol=X`` **会忽略 symbol 参数**，返回全市场
        的日历（实测传 AAPL 却回来 FDX）。用它算 DTE 会得到一个完全无关的日期 ——
        典型的「有数据但错」，比取不到更危险。
      · 正确端点是 ``/stable/earnings?symbol=X``，它确实只返回该标的记录
        （AAPL 实测 165 条，下一次 2026-10-29）。
      · 该端点加 ``limit`` 参数会触发 402，所以不带 limit，在本地筛。
    """
    try:
        data = _fmp(f"earnings?symbol={urllib.parse.quote(ticker)}", api_key)
    except Exception as exc:
        return None, f"取财报日失败：{exc}"
    if not isinstance(data, list) or not data:
        return None, "该端点未返回记录"
    symbols = {str(r.get("symbol")).upper() for r in data if isinstance(r, dict)}
    if symbols and ticker.upper() not in symbols:
        return None, f"端点未按 symbol 过滤（返回了 {sorted(symbols)[:3]}），拒绝据此推算 DTE"
    today = datetime.now(timezone.utc).date()
    future: list = []
    for row in data:
        raw = row.get("date")
        if not raw:
            continue
        try:
            d = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= today:
            future.append(d)
    if not future:
        return None, "没有未来日期的财报记录"
    return (min(future) - today).days, f"来自 FMP（{min(future).isoformat()}）"


def historical_vol(prices: list[float], window: int = 30) -> float | None:
    """年化历史波动率（对数收益标准差 × √252）。样本不足返回 None。"""
    if len(prices) < window + 1:
        return None
    rets = [math.log(prices[i] / prices[i - 1])
            for i in range(1, len(prices))
            if prices[i - 1] > 0 and prices[i] > 0]
    if len(rets) < window:
        return None
    sample = rets[-window:]
    mean = sum(sample) / len(sample)
    var = sum((x - mean) ** 2 for x in sample) / max(1, len(sample) - 1)
    return math.sqrt(var) * math.sqrt(252)


def fetch_hv(ticker: str, api_key: str, window: int = 30) -> float | None:
    try:
        data = _fmp(f"historical-price-eod/light?symbol={urllib.parse.quote(ticker)}", api_key)
    except Exception:
        return None
    if not isinstance(data, list) or len(data) < window + 1:
        return None
    # FMP 返回新→旧，转成旧→新
    closes = [float(r["price"]) for r in reversed(data) if r.get("price")]
    return historical_vol(closes, window)


def strategy_block(spot: float, vol: float, dte: float, rate: float, div: float) -> list[dict]:
    """三种财报常用结构：跨式 / 宽跨式 / 铁鹰。回报里明确写清最坏情况。"""
    T = max(dte, 0.0) / 365.0
    # 常用做法：跨式买 ATM；宽跨式买 ±1 个预期波动；铁鹰卖 ±1 个预期波动
    expected_move = spot * vol * math.sqrt(T) if T > 0 else 0.0
    atm_k = round(spot)
    upper_k = round(spot + expected_move)
    lower_k = round(spot - expected_move)
    wing = max(1.0, round(expected_move * 0.5))

    def prem(k: float, kind: str) -> float:
        return bs_price(spot, k, T, rate, vol, div, kind)

    call_atm, put_atm = prem(atm_k, "call"), prem(atm_k, "put")
    call_up, put_dn = prem(upper_k, "call"), prem(lower_k, "put")
    ic_short_call, ic_short_put = prem(upper_k, "call"), prem(lower_k, "put")
    ic_long_call = prem(upper_k + wing, "call")
    ic_long_put = prem(max(1.0, lower_k - wing), "put")

    straddle_cost = (call_atm + put_atm) * MULTIPLIER
    strangle_cost = (call_up + put_dn) * MULTIPLIER
    ic_credit = ((ic_short_call + ic_short_put) - (ic_long_call + ic_long_put)) * MULTIPLIER
    ic_width = wing * MULTIPLIER

    return [
        {
            "name": "买入跨式 Long Straddle",
            "legs": [f"buy 1 {atm_k}C @{call_atm:.2f}", f"buy 1 {atm_k}P @{put_atm:.2f}"],
            "cost_or_credit": -straddle_cost,
            "breakevens": [atm_k - (call_atm + put_atm), atm_k + (call_atm + put_atm)],
            "max_loss": -straddle_cost,
            "max_profit": "无限（任一方向大幅波动）",
            "note": "需要实际波动 > 隐含预期，IV 高时最容易两头亏时间价值",
        },
        {
            "name": "买入宽跨式 Long Strangle",
            "legs": [f"buy 1 {upper_k}C @{call_up:.2f}", f"buy 1 {lower_k}P @{put_dn:.2f}"],
            "cost_or_credit": -strangle_cost,
            "breakevens": [lower_k - (call_up + put_dn), upper_k + (call_up + put_dn)],
            "max_loss": -strangle_cost,
            "max_profit": "无限（任一方向大幅波动）",
            "note": "成本低于跨式，但要求的波动幅度更大",
        },
        {
            "name": "卖出铁鹰 Short Iron Condor",
            "legs": [f"sell 1 {lower_k}P / buy 1 {max(1.0, lower_k - wing)}P",
                     f"sell 1 {upper_k}C / buy 1 {upper_k + wing}C"],
            "cost_or_credit": ic_credit,
            "breakevens": [lower_k + ic_credit / MULTIPLIER, upper_k - ic_credit / MULTIPLIER],
            "max_loss": ic_credit - ic_width,
            "max_profit": ic_credit,
            "note": "赌财报后落在区间内；赚 IV crush，但尾部风险由买入翼封顶",
        },
    ]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="财报期期权策略分析")
    p.add_argument("--ticker", help="股票代码（可自动取现价/财报日/HV）")
    p.add_argument("--api-key", help="FMP key；缺省读 FMP_API_KEY 或 secrets 文件")
    p.add_argument("--stock-price", type=float, help="现价（优先于 --ticker 取价）")
    p.add_argument("--iv", type=float, required=True, help="当前隐含波动率（0.6 或 60 皆可）")
    p.add_argument("--days-to-earnings", type=float, help="距财报天数（不给则由 FMP 取）")
    p.add_argument("--days", type=float, help="期权到期天数（默认 = 距财报天数 + 1，否则 7）")
    p.add_argument("--risk-free", type=float, default=0.053)
    p.add_argument("--dividend-yield", type=float, default=0.0)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    key = args.api_key or os.environ.get("FMP_API_KEY") or _read_secret("fmp_api_key.txt")

    spot = args.stock_price
    div = args.dividend_yield
    source = "手工输入"
    if spot is None:
        if not (args.ticker and key):
            print("错误：需要 --stock-price，或 --ticker 配上 FMP key", file=sys.stderr)
            return 2
        try:
            prof = fetch_profile(args.ticker, key)
        except Exception as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 3
        spot, div, source = prof["price"], (args.dividend_yield or prof["dividend_yield"]), "FMP"

    dte_earnings = args.days_to_earnings
    earnings_note = "手工输入"
    if dte_earnings is None and args.ticker and key:
        dte_earnings, earnings_note = fetch_earnings_days(args.ticker, key)
    if dte_earnings is None:
        print(f"错误：无法确定距财报天数（{earnings_note}）—— 请用 --days-to-earnings 给出",
              file=sys.stderr)
        return 4

    dte = args.days if args.days is not None else max(dte_earnings + 1.0, 1.0)
    vol = normalise_vol(args.iv)
    iv_crush_window = dte_earnings <= 1.0

    hv = fetch_hv(args.ticker, key) if (args.ticker and key) else None
    expected_move = spot * vol * math.sqrt(max(dte, 0.0) / 365.0)
    blocks = strategy_block(spot, vol, dte, args.risk_free, div)

    iv_verdict = None
    if hv:
        ratio = vol / hv
        if ratio >= 1.25:
            iv_verdict = f"IV 是 HV 的 {ratio:.2f} 倍 → 期权偏贵，优先考虑卖方结构（铁鹰/信用价差）"
        elif ratio <= 0.85:
            iv_verdict = f"IV 是 HV 的 {ratio:.2f} 倍 → 期权偏便宜，可考虑买方结构（跨式/宽跨式）"
        else:
            iv_verdict = f"IV≈HV（{ratio:.2f} 倍）→ 无明显贵贱，按方向观点选结构"

    result = {
        "ticker": args.ticker or "-",
        "price_source": source,
        "stock_price": round(spot, 4),
        "iv": vol,
        "hv_30d": round(hv, 4) if hv else None,
        "iv_vs_hv": iv_verdict,
        "days_to_earnings": dte_earnings,
        "earnings_date_source": earnings_note,
        "days_to_expiry": dte,
        "expected_move_abs": round(expected_move, 4),
        "expected_move_pct": round(expected_move / spot * 100, 3) if spot else None,
        "iv_crush_imminent": iv_crush_window,
        "strategies": blocks,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"\n财报期期权策略分析 · {args.ticker or '手工输入'} · 现价 {spot:,.2f} ({source})")
    print("=" * 74)
    print(f"  距财报            {dte_earnings:g} 天（{earnings_note}）   期权到期 {dte:g} 天")
    print(f"  隐含波动率 IV     {vol*100:.1f}%", end="")
    if hv:
        print(f"      30日历史波动 HV {hv*100:.1f}%")
    else:
        print("      （未取到 HV）")
    print(f"  隐含预期波动      ±{expected_move:,.2f} 美元 (±{expected_move/spot*100:.2f}%)")
    if iv_crush_window:
        print("  ⚠️  财报在 24 小时内：IV crush 风险最高，买方结构极易两头亏")
    if iv_verdict:
        print(f"  贵贱判断          {iv_verdict}")
    print("=" * 74)
    for b in blocks:
        print(f"\n  【{b['name']}】")
        for leg in b["legs"]:
            print(f"     {leg}")
        flow = b["cost_or_credit"]
        print(f"     现金流        {flow:+,.2f} 美元（{'净收入' if flow > 0 else '净支出'}）")
        print(f"     平衡点        {', '.join(f'{x:,.2f}' for x in b['breakevens'])}")
        print(f"     最大亏损      {b['max_loss']:+,.2f} 美元")
        print(f"     最大盈利      {b['max_profit'] if isinstance(b['max_profit'], str) else format(b['max_profit'], '+,.2f')}")
        print(f"     说明          {b['note']}")
    print("\n" + "-" * 74)
    print("  结论口径：财报前买方结构要赌「实际波动 > 隐含预期」，卖方结构要赌「落区间内」。")
    print("  两者都要先看 IV vs HV —— IV 已明显高于 HV 时，买期权是在为已知风险付溢价。")
    print("  本分析为欧式理论定价，未含买卖价差、佣金与提前行权；下单价以券商为准。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
