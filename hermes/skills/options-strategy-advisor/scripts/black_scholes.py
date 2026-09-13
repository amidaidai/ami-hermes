#!/usr/bin/env python3
"""Black-Scholes 定价引擎 + Greeks —— options-strategy-advisor 技能的核心脚本。

2026-09-13 补齐：SKILL.md 一直让读者跑 `python3 scripts/black_scholes.py`，
但这个文件从未随技能落地（技能只有 SKILL.md，是个空壳）。
本实现严格对齐 SKILL.md 里承诺的 CLI 形态：

    python3 scripts/black_scholes.py
    python3 scripts/black_scholes.py --ticker AAPL --api-key $FMP_API_KEY
    python3 scripts/black_scholes.py --stock-price 180 --strike 185 --days 30 --volatility 0.25
    python3 scripts/black_scholes.py --stock-price 180 --strike 175 --days 30 --option-type put

设计取舍：
  · 无 API key 也能跑（用手工输入的价格/波动率）——与 SKILL.md 的「Optional: FMP API key」一致；
  · FMP 取价先直连、失败再走本地代理（境外源在本机需代理才稳）；
  · 只用欧式定价并在输出里显式声明，不假装支持美式提前行权；
  · 同时提供 `solve_iv` 反解隐含波动率（SKILL.md 的 Step 2 需要它）。
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
from pathlib import Path

try:  # scipy 更快更准，缺失时用 math.erf 兜底
    from scipy.stats import norm as _norm  # type: ignore

    def _cdf(x: float) -> float:
        return float(_norm.cdf(x))

    def _pdf(x: float) -> float:
        return float(_norm.pdf(x))
except Exception:  # pragma: no cover
    def _cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _pdf(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

LOCAL_PROXY = os.environ.get("TANGXI_PROXY", "http://127.0.0.1:7897")
SECRETS = Path("D:/Hermes agent/hermes/secrets")


# ───────────────────────── 定价核心 ─────────────────────────

def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        raise ValueError("S/K/T/sigma 必须为正数（T 为剩余年限）")
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_price(S: float, K: float, T: float, r: float, sigma: float,
             q: float = 0.0, option_type: str = "call") -> float:
    """欧式期权理论价。option_type: call / put。"""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_q, disc_r = math.exp(-q * T), math.exp(-r * T)
    if option_type.lower().startswith("c"):
        return S * disc_q * _cdf(d1) - K * disc_r * _cdf(d2)
    return K * disc_r * _cdf(-d2) - S * disc_q * _cdf(-d1)


def bs_greeks(S: float, K: float, T: float, r: float, sigma: float,
              q: float = 0.0, option_type: str = "call") -> dict[str, float]:
    """Delta / Gamma / Theta(每日) / Vega(每1%) / Rho(每1%)。"""
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_q, disc_r = math.exp(-q * T), math.exp(-r * T)
    sqrt_t = math.sqrt(T)
    call = option_type.lower().startswith("c")

    delta = disc_q * (_cdf(d1) if call else _cdf(d1) - 1.0)
    gamma = disc_q * _pdf(d1) / (S * sigma * sqrt_t)
    vega = S * disc_q * _pdf(d1) * sqrt_t / 100.0
    theta_annual = (
        -S * disc_q * _pdf(d1) * sigma / (2.0 * sqrt_t)
        + (q * S * disc_q * (_cdf(d1) if call else -_cdf(-d1)))
        + (r * K * disc_r * (-_cdf(d2) if call else _cdf(-d2)))
    )
    rho = (K * T * disc_r * (_cdf(d2) if call else -_cdf(-d2))) / 100.0
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_annual / 365.0,
        "vega": vega,
        "rho": rho,
    }


def solve_iv(market_price: float, S: float, K: float, T: float, r: float,
             q: float = 0.0, option_type: str = "call",
             lo: float = 1e-4, hi: float = 5.0, tol: float = 1e-6,
             max_iter: int = 200) -> float | None:
    """由市场价反解隐含波动率（二分法，区间内单调）。解不出返回 None。"""
    low = bs_price(S, K, T, r, lo, q, option_type)
    high = bs_price(S, K, T, r, hi, q, option_type)
    if not (low - tol <= market_price <= high + tol):
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        price = bs_price(S, K, T, r, mid, q, option_type)
        if abs(price - market_price) < tol:
            return mid
        if price < market_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ───────────────────────── FMP 取价 ─────────────────────────

def _read_secret(name: str) -> str:
    try:
        return (SECRETS / name).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _http_json(url: str, use_proxy: bool) -> dict:
    handlers = []
    if use_proxy:
        handlers.append(urllib.request.ProxyHandler({"http": LOCAL_PROXY, "https": LOCAL_PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": "tangxi-options/1.0"})
    with opener.open(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_fmp_quote(ticker: str, api_key: str) -> dict:
    """返回 {'price': float, 'dividend_yield': float, 'source': str}；失败抛异常。

    境外源在本机直连不稳，故先直连再退本地代理（两者都失败才报错）。
    """
    url = (f"https://financialmodelingprep.com/stable/quote"
           f"?symbol={urllib.parse.quote(ticker)}&apikey={api_key}")
    last: Exception | None = None
    for use_proxy in (False, True):
        try:
            data = _http_json(url, use_proxy)
            break
        except Exception as exc:  # noqa: PERF203
            last = exc
    else:
        raise RuntimeError(f"FMP 取价失败（直连与代理均不通）: {last}")
    if isinstance(data, dict) and data.get("Error Message"):
        raise RuntimeError(f"FMP 拒绝: {data['Error Message']}")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"FMP 返回空: {str(data)[:120]}")
    row = data[0]
    return {
        "price": float(row.get("price") or 0),
        "dividend_yield": float(row.get("dividendYield") or 0) / 100.0,
        "source": "FMP" + ("·代理" if use_proxy else "·直连"),
    }


# ───────────────────────── CLI ─────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Black-Scholes 欧式期权定价 + Greeks（options-strategy-advisor）")
    p.add_argument("--ticker", help="股票代码，用于从 FMP 取现价（如 AAPL）")
    p.add_argument("--api-key", help="FMP API key；缺省读环境变量 FMP_API_KEY 或 secrets 文件")
    p.add_argument("--stock-price", type=float, help="现价（手工输入，优先于 --ticker 取价）")
    p.add_argument("--strike", type=float, default=100.0, help="行权价（默认 100）")
    p.add_argument("--days", type=float, default=30.0, help="距到期日历天数（默认 30）")
    p.add_argument("--volatility", "--iv", dest="volatility", type=float,
                   help="波动率，小数或百分数皆可（0.25 或 25 都理解为 25%%）")
    p.add_argument("--option-type", default="call", choices=["call", "put"])
    p.add_argument("--risk-free", type=float, default=0.053, help="无风险利率（默认 5.3%%）")
    p.add_argument("--dividend-yield", type=float, default=None, help="股息率（默认取 FMP 或 0）")
    p.add_argument("--contracts", type=int, default=1, help="张数（用于计算总金额）")
    p.add_argument("--market-price", type=float,
                   help="给定期权市场价时反解隐含波动率")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    return p


def normalise_vol(raw: float | None) -> float:
    """容错解析波动率：0.25 与 25 都理解为 25%。"""
    if raw is None:
        return 0.25
    return raw / 100.0 if raw > 3.0 else raw


_normalise_vol = normalise_vol  # 兼容内部旧调用名


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    price = args.stock_price
    div_yield, price_source = (args.dividend_yield if args.dividend_yield is not None else 0.0), "手工输入"
    if price is None and args.ticker:
        key = args.api_key or os.environ.get("FMP_API_KEY") or _read_secret("fmp_api_key.txt")
        if not key:
            print("错误：--ticker 需要 FMP key（--api-key / FMP_API_KEY / "
                  "hermes/secrets/fmp_api_key.txt 任一）", file=sys.stderr)
            return 2
        try:
            q = fetch_fmp_quote(args.ticker, key)
        except Exception as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 3
        price, price_source = q["price"], q["source"]
        if args.dividend_yield is None:
            div_yield = q["dividend_yield"]
    if not price:
        price = 100.0
        price_source = "默认值(未提供现价)"

    sigma = _normalise_vol(args.volatility)
    T = max(args.days, 0.0) / 365.0
    r, K = args.risk_free, args.strike

    try:
        price_theo = bs_price(price, K, T, r, sigma, div_yield, args.option_type)
        greeks = bs_greeks(price, K, T, r, sigma, div_yield, args.option_type)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 4

    iv_solved = None
    if args.market_price is not None:
        iv_solved = solve_iv(args.market_price, price, K, T, r, div_yield, args.option_type)

    result = {
        "ticker": args.ticker or "-",
        "price_source": price_source,
        "stock_price": round(price, 4),
        "strike": K,
        "days_to_expiry": args.days,
        "years_to_expiry": round(T, 6),
        "volatility": sigma,
        "risk_free_rate": r,
        "dividend_yield": div_yield,
        "option_type": args.option_type,
        "contracts": args.contracts,
        "theoretical_price": round(price_theo, 4),
        "premium_total": round(price_theo * 100 * args.contracts, 2),
        "greeks": {k: round(v, 6) for k, v in greeks.items()},
        "implied_volatility": round(iv_solved, 6) if iv_solved is not None else None,
    }
    result["moneyness"] = ("ITM" if (price > K) == (args.option_type == "call")
                           else "OTM" if price != K else "ATM")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    g = result["greeks"]
    print(f"\nBlack-Scholes 定价 · {args.ticker or '手工输入'} · {args.option_type.upper()}")
    print("-" * 64)
    print(f"  现价 S            {price:,.4f}   ({price_source})")
    print(f"  行权价 K          {K:,.4f}     ({result['moneyness']})")
    print(f"  剩余期限          {args.days:g} 天 (T={T:.6f} 年)")
    print(f"  波动率 σ          {sigma*100:.2f}%")
    print(f"  无风险利率 r      {r*100:.2f}%      股息率 q {div_yield*100:.2f}%")
    print("-" * 64)
    print(f"  理论价            {price_theo:,.4f}   每张 {price_theo*100:,.2f} 美元"
          f"   × {args.contracts} 张 = {result['premium_total']:,.2f}")
    print(f"  Greeks            Δ {g['delta']:+.4f}   Γ {g['gamma']:.6f}   "
          f"Θ {g['theta']:+.4f}/日   ν {g['vega']:+.4f}/1%   ρ {g['rho']:+.4f}/1%")
    if iv_solved is not None:
        print(f"  由市场价 {args.market_price:.4f} 反解 IV = {iv_solved*100:.2f}%")
    print("-" * 64)
    print("  说明：欧式定价。美式提前行权、买卖价差、流动性、除息日影响均未建模；")
    print("       实际下单价请以券商报价为准。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
