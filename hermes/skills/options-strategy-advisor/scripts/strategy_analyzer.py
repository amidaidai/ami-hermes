#!/usr/bin/env python3
"""期权策略 P/L 模拟器 —— options-strategy-advisor 的 scripts/strategy_analyzer.py。

2026-09-13 补齐：SKILL.md 的「Scripts」段一直列着本文件，但从未随技能落地。

支持两件 SKILL.md 承诺的事（Step 5 策略 P/L 模拟 + Step 6 ASCII 图）：
  · 多腿策略的到期损益、最大盈利/最大亏损、盈亏平衡点、总 Greeks；
  · 期权腿可手工给权利金（`@3.50`），也可省略由 Black-Scholes 用 --volatility 定价。

用法（腿的写法：`<buy|sell> <张数> <call|put> <行权价> [@权利金]`，股票腿用 `stock`）：

    # 牛市看涨价差
    python3 scripts/strategy_analyzer.py --stock-price 180 --volatility 0.25 --days 30 \\
        --leg "buy 1 call 180" --leg "sell 1 call 185"

    # 备兑开仓（100 股 + 卖 1 张 call）
    python3 scripts/strategy_analyzer.py --stock-price 180 --volatility 0.25 --days 30 \\
        --leg "buy 100 stock 180" --leg "sell 1 call 185 @3.50"

    # 铁鹰（四腿）
    python3 scripts/strategy_analyzer.py --stock-price 180 --volatility 0.22 --days 30 \\
        --leg "sell 1 put 175" --leg "buy 1 put 170" \\
        --leg "sell 1 call 185" --leg "buy 1 call 190"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from black_scholes import bs_greeks, bs_price, normalise_vol  # noqa: E402

MULTIPLIER = 100  # 美股期权每张 100 股


class Leg:
    def __init__(self, side: str, qty: float, kind: str, strike: float,
                 premium: float | None = None):
        self.side = side
        self.qty = qty
        self.kind = kind
        self.strike = strike
        self.premium = premium

    @property
    def sign(self) -> int:
        return 1 if self.side == "buy" else -1

    def expiry_value(self, spot: float) -> float:
        """该腿在到期日的价值（每 1 单位），股票腿按现价差计。"""
        if self.kind == "stock":
            return spot - self.strike
        if self.kind == "call":
            return max(0.0, spot - self.strike)
        return max(0.0, self.strike - spot)

    def label(self) -> str:
        prem = f" @{self.premium:.2f}" if self.premium is not None else ""
        unit = "股" if self.kind == "stock" else "张"
        return f"{self.side} {self.qty:g} {unit} {self.kind} {self.strike:g}{prem}"


def parse_leg(text: str) -> Leg:
    parts = text.replace("@", " @ ").split()
    if len(parts) < 4:
        raise ValueError(f"腿格式不对: {text!r}（应为 <buy|sell> <数量> <call|put|stock> <行权价> [@权利金]）")
    side = parts[0].lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"腿方向必须是 buy/sell: {text!r}")
    qty = float(parts[1])
    kind = parts[2].lower()
    if kind not in ("call", "put", "stock"):
        raise ValueError(f"腿类型必须是 call/put/stock: {text!r}")
    strike = float(parts[3])
    premium = None
    if len(parts) >= 6 and parts[4] == "@":
        premium = float(parts[5])
    elif len(parts) >= 5:
        premium = float(parts[4].lstrip("@"))
    return Leg(side, qty, kind, strike, premium)


def price_missing_premiums(legs: list[Leg], spot: float, days: float,
                           vol: float, rate: float, div: float) -> None:
    """没给权利金的期权腿用 Black-Scholes 定价，保证模拟可复现。"""
    T = max(days, 0.0) / 365.0
    for leg in legs:
        if leg.kind == "stock" or leg.premium is not None:
            continue
        leg.premium = bs_price(spot, leg.strike, T, rate, vol, div, leg.kind)


def position_pnl(legs: list[Leg], spot: float) -> float:
    """到期日总损益（美元）。期权按每张 100 股，股票按 1 股 1 美元。"""
    total = 0.0
    for leg in legs:
        if leg.kind == "stock":
            total += leg.sign * leg.qty * (spot - leg.strike)
        else:
            intrinsic = leg.expiry_value(spot)
            prem = leg.premium or 0.0
            total += leg.sign * leg.qty * MULTIPLIER * (intrinsic - prem)
    return total


def net_cashflow(legs: list[Leg]) -> float:
    """建仓现金流：正=净收入(credit)，负=净支出(debit)。"""
    flow = 0.0
    for leg in legs:
        if leg.kind == "stock":
            continue
        flow -= leg.sign * leg.qty * MULTIPLIER * (leg.premium or 0.0)
    return flow


def breakevens(spots: list[float], pnls: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(spots)):
        a, b = pnls[i - 1], pnls[i]
        if a == 0:
            out.append(spots[i - 1])
        elif (a < 0 < b) or (a > 0 > b):
            # 线性插值零点
            t = abs(a) / (abs(a) + abs(b))
            out.append(spots[i - 1] + t * (spots[i] - spots[i - 1]))
    return out


def position_greeks(legs: list[Leg], spot: float, days: float,
                    vol: float, rate: float, div: float) -> dict[str, float]:
    T = max(days, 0.0) / 365.0
    tot = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for leg in legs:
        if leg.kind == "stock":
            tot["delta"] += leg.sign * leg.qty
            continue
        g = bs_greeks(spot, leg.strike, T, rate, vol, div, leg.kind)
        for k in tot:
            tot[k] += leg.sign * leg.qty * MULTIPLIER * g[k]
    return tot


def diagram(spots: list[float], pnls: list[float], width: int = 58,
            height: int = 13) -> str:
    """到期损益图：以零轴为基线填充（盈利 █ / 亏损 ░），直觉上等同券商 payoff 图。"""
    lo, hi = min(pnls), max(pnls)
    span = (hi - lo) or 1.0
    # 纵轴留一点余量，避免极值贴边
    top = hi + span * 0.06
    bottom = lo - span * 0.06
    span = top - bottom
    zero_row = round((0.0 - bottom) / span * height)

    grid = [[" "] * width for _ in range(height + 1)]
    for col in range(width):
        idx = round(col / max(1, width - 1) * (len(spots) - 1))
        pnl = pnls[idx]
        row = round((pnl - bottom) / span * height)
        char = "█" if pnl > 0 else ("░" if pnl < 0 else "─")
        lo_row, hi_row = sorted((row, zero_row))
        for r in range(lo_row, hi_row + 1):
            grid[r][col] = char

    lines = []
    for r in range(height, -1, -1):
        level = bottom + span * r / height
        lines.append(f"{level:>9,.0f} |" + "".join(grid[r]))
    lines.append(" " * 10 + "+" + "-" * width)
    left, right = f"{spots[0]:,.0f}", f"{spots[-1]:,.0f}"
    lines.append(" " * 11 + left + " " * max(1, width - len(left) - len(right)) + right)
    lines.append(" " * (10 + width // 2 - 4) + "标的价")
    lines.append("  图例：█ 盈利   ░ 亏损   ─ 零轴")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="期权策略 P/L 模拟（多腿）")
    p.add_argument("--leg", action="append", default=[],
                   help='腿，可重复。例："buy 1 call 180"、"sell 1 call 185 @3.50"、"buy 100 stock 180"')
    p.add_argument("--stock-price", type=float, required=True, help="标的现价")
    p.add_argument("--days", type=float, default=30.0, help="距到期天数（默认 30）")
    p.add_argument("--volatility", "--iv", dest="volatility", type=float, default=0.25,
                   help="用于给未标价的腿定价（默认 0.25）")
    p.add_argument("--risk-free", type=float, default=0.053)
    p.add_argument("--dividend-yield", type=float, default=0.0)
    p.add_argument("--range", type=float, default=0.30, help="价格扫描幅度（默认 ±30%%）")
    p.add_argument("--points", type=int, default=241, help="扫描点数")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.leg:
        print("错误：至少给一条 --leg", file=sys.stderr)
        return 2
    try:
        legs = [parse_leg(t) for t in args.leg]
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 3

    spot, vol = args.stock_price, normalise_vol(args.volatility)
    price_missing_premiums(legs, spot, args.days, vol, args.risk_free, args.dividend_yield)

    lo = spot * (1 - args.range)
    hi = spot * (1 + args.range)
    spots = [lo + (hi - lo) * i / (args.points - 1) for i in range(args.points)]
    pnls = [position_pnl(legs, s) for s in spots]

    flow = net_cashflow(legs)
    has_stock = any(l.kind == "stock" for l in legs)
    max_profit, max_loss = max(pnls), min(pnls)
    # 有股票腿时损益两翼通常不封顶，用扫描区间标注为「区间内」
    be = breakevens(spots, pnls)
    greeks = position_greeks(legs, spot, args.days, vol, args.risk_free, args.dividend_yield)

    result = {
        "stock_price": spot,
        "days": args.days,
        "volatility": vol,
        "legs": [l.label() for l in legs],
        "net_cashflow": round(flow, 2),
        "net_cashflow_kind": "credit" if flow > 0 else ("debit" if flow < 0 else "flat"),
        "max_profit_in_range": round(max_profit, 2),
        "max_loss_in_range": round(max_loss, 2),
        "breakevens": [round(b, 4) for b in be],
        "position_greeks": {k: round(v, 4) for k, v in greeks.items()},
        "scan_range": [round(lo, 2), round(hi, 2)],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"\n期权策略 P/L 模拟 · 标的 {spot:,.2f} · {args.days:g} DTE · σ {vol*100:.1f}%")
    print("-" * 70)
    for leg in legs:
        print(f"  {leg.label()}")
    print("-" * 70)
    kind = "贷方净收入" if flow > 0 else ("借方净支出" if flow < 0 else "零成本")
    print(f"  建仓现金流        {flow:+,.2f} 美元（{kind}）")
    print(f"  扫描区间内最大盈利 {max_profit:+,.2f}")
    print(f"  扫描区间内最大亏损 {max_loss:+,.2f}")
    print(f"  盈亏平衡点        {', '.join(f'{b:,.2f}' for b in be) if be else '区间内无'}")
    print(f"  持仓 Greeks       Δ {greeks['delta']:+,.2f}   Γ {greeks['gamma']:+.3f}   "
          f"Θ {greeks['theta']:+,.2f}/日   ν {greeks['vega']:+,.2f}/1%   "
          f"ρ {greeks['rho']:+,.2f}/1%")
    print("-" * 70)
    print(diagram(spots, pnls))
    print()
    if has_stock:
        print("  注：含股票腿，扫描区间外仍有敞口——最大盈利/亏损仅表示区间内极值。")
    print(f"  扫描区间 {lo:,.2f} ~ {hi:,.2f}；欧式定价，未计买卖价差、佣金与提前行权。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
