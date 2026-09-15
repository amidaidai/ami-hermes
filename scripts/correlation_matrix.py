#!/usr/bin/env python3
"""
棠溪 · 多资产相关性矩阵 v1.1
社区2026共识：多策略/多资产同向 = 组合级风险失控

功能:
  1. BTC vs XAU 滚动相关性（7d/30d）——走 Binance fapi 日线，不再依赖 source_snapshots
  2. 当前相关性体制判决（正相关/负相关/独立）
  3. 多资产头寸风险调整倍数

用法:
  python scripts/correlation_matrix.py          # 打印当前状态
  python scripts/correlation_matrix.py --json   # JSON输出
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
CORR_FILE = DATA / "correlation_state.json"
FAPI = "https://fapi.binance.com"
PROXY = "http://127.0.0.1:7897"


def _get(url, timeout=12):
    last = None
    for opener in (
        urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})),
        urllib.request.build_opener(),
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
    raise last


def load_price_series(symbol: str, lookback_days: int = 30) -> list[float]:
    """从 Binance fapi 日线加载收盘价序列"""
    klines = _get(f"{FAPI}/fapi/v1/klines?symbol={symbol}&interval=1d&limit={lookback_days}")
    return [float(k[4]) for k in klines]  # close


# ---- 黄金腿的合规口径（2026-09-15 审计发现：原来直接拿 Binance XAUUSDT 当「XAU」）----
# 用户铁律：禁拿加密合约冒充 OANDA 黄金。取数优先序：
#   1) OANDA/TwelveData 现货日线（xau_ohlcv_source，与图表 OANDA:XAUUSD 同源）
#   2) Binance XAUUSDT —— 只作为**代理腿**，必须明标，并与现货基准比偏差；
#      偏差超阈值就降级：不给仓位建议（可见降级，不硬拦截）
GOLD_PROXY_SYMBOL = "XAUUSDT"
GOLD_SPOT_REFS = ("tv_live_XAUUSD.json", "source_snapshot_XAUUSD.json")
GOLD_PROXY_MAX_DEV_PCT = 1.0
# 2026-09-15 起 XAU TV 同步已暂停（用户决定：只要 BTC 的）→ 现货基准文件会停更。
# 拿陈旧价当「校准基准」比不校准更危险（会把代理腿偏差算歪），所以加时效闸：
# 超过这个年龄就当基准不可用（下游走「无法校准」分支，仍明标代理腿）。
GOLD_SPOT_REF_MAX_AGE_MIN = 60.0


def gold_spot_reference() -> float | None:
    """OANDA:XAUUSD 现货基准价（TV 现场同步产物），用于校准代理腿。

    时效闸：文件超过 GOLD_SPOT_REF_MAX_AGE_MIN 视为不可用（XAU 同步已暂停时会命中）。
    """
    for name in GOLD_SPOT_REFS:
        p = DATA / name
        if not p.exists():
            continue
        try:
            age_min = (time.time() - p.stat().st_mtime) / 60.0
        except OSError:
            continue
        if age_min > GOLD_SPOT_REF_MAX_AGE_MIN:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key in ("last_price", "price", "close"):
            v = d.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
        px = (d.get("prices") or {}).get("primary") if isinstance(d.get("prices"), dict) else None
        if isinstance(px, (int, float)) and px > 0:
            return float(px)
    return None


def load_gold_series(lookback_days: int = 30) -> tuple[list[float], str, float | None]:
    """黄金腿取数。返回 (序列, 来源标签, 与现货基准的偏差%)。"""
    # 1) 合规现货源（当前 token/key 缺失时返回空）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import xau_ohlcv_source as _xs
        frames = _xs.fetch_all(count=lookback_days) or {}
        for src, tf in frames.items():
            bars = (tf or {}).get("1D") or (tf or {}).get("1d")
            if isinstance(bars, list) and len(bars) >= 3:
                closes = [float(b["close"]) for b in bars
                          if isinstance(b, dict) and b.get("close")]
                if len(closes) >= 3:
                    return closes, f"{src}_spot", 0.0
    except Exception:
        pass
    # 2) 代理腿（明标）
    series = load_price_series(GOLD_PROXY_SYMBOL, lookback_days)
    dev = None
    ref = gold_spot_reference()
    if ref and series:
        dev = round((series[-1] - ref) / ref * 100, 3)
    return series, f"binance_{GOLD_PROXY_SYMBOL.lower()}_proxy", dev


def pearson_r(x: list[float], y: list[float]) -> float:
    """Pearson 相关系数"""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0

    x = x[-n:]
    y = y[-n:]

    mx = sum(x) / n
    my = sum(y) / n

    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = sum((xi - mx) ** 2 for xi in x)
    dy = sum((yi - my) ** 2 for yi in y)

    den = (dx * dy) ** 0.5
    return num / den if den > 0 else 0.0


def compute_correlation() -> dict:
    """计算 BTC vs XAU 相关性（黄金腿来源明标；代理腿偏差过大 → 降级）"""
    btc_prices = load_price_series("BTCUSDT", 30)
    xau_prices, gold_source, gold_dev = load_gold_series(30)

    if len(btc_prices) < 3 or len(xau_prices) < 3:
        return {
            "status": "data_insufficient",
            "btc_samples": len(btc_prices),
            "xau_samples": len(xau_prices),
            "correlation": 0.0,
            "regime": "未知",
            "diversification_benefit": 0.0,
            "gold_source": gold_source,
        }

    # 全量相关
    corr_full = pearson_r(btc_prices, xau_prices)

    # 短期相关（后1/3样本）
    n_short = max(3, min(len(btc_prices), len(xau_prices)) // 3)
    corr_short = pearson_r(btc_prices[-n_short:], xau_prices[-n_short:])

    # 体制判决
    if corr_full > 0.5:
        regime = "强正相关"
        diversification = 0.1  # 几乎不分散
    elif corr_full > 0.2:
        regime = "弱正相关"
        diversification = 0.3
    elif corr_full > -0.2:
        regime = "独立/弱相关"
        diversification = 0.6
    elif corr_full > -0.5:
        regime = "弱负相关"
        diversification = 0.4  # 负相关有分散但注意方向
    else:
        regime = "强负相关"
        diversification = 0.3  # 强负相关=对冲好但要防方向反转

    # 体制变化检测
    trend = "稳定"
    if abs(corr_short - corr_full) > 0.3:
        trend = "转正" if corr_short > corr_full else "转负"

    proxy = gold_source.endswith("_proxy")
    degraded = bool(proxy and gold_dev is not None and abs(gold_dev) > GOLD_PROXY_MAX_DEV_PCT)
    warn = None
    if proxy:
        warn = (f"黄金腿=Binance {GOLD_PROXY_SYMBOL}（**代理**·非 OANDA 现货）"
                + (f"，与 OANDA:XAUUSD 现货偏差 {gold_dev:+.2f}%" if gold_dev is not None
                   else "，现货基准不可用（无法校准）"))
        if degraded:
            warn += f" → 偏差 >{GOLD_PROXY_MAX_DEV_PCT}%：相关性仅供参考，本轮不给仓位建议"

    return {
        "status": "proxy_degraded" if degraded else "ok",
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
        "btc_samples": len(btc_prices),
        "xau_samples": len(xau_prices),
        "gold_source": gold_source,
        "gold_deviation_pct": gold_dev,
        "warning": warn,
        "correlation_full": round(corr_full, 3),
        "correlation_short": round(corr_short, 3),
        "regime": regime,
        "trend": trend,
        "diversification_benefit": round(diversification, 2),
        "advice": _correlation_advice(corr_full, trend, regime) + (f"｜{warn}" if warn else ""),
    }


def _correlation_advice(corr: float, trend: str, regime: str) -> str:
    """根据相关性给出建议"""
    if abs(corr) < 0.2:
        return "BTC+XAU独立运行·可同时持仓·各走各的风险预算"
    if corr > 0.5:
        return f"BTC+XAU强正相关{corr=:.2f}·同时持仓视为组合风险叠加·建议减总仓30%"
    if corr < -0.5:
        return "BTC+XAU强负相关·天然对冲·一方盈利可cover另一方·但注意方向反转风险"
    if trend == "转正":
        return "相关性正在转正·注意组合风险收敛·减仓观望"
    return f"相关性{corr=:.2f}·{regime}·分散效果一般"


def multi_asset_risk_multiplier(positions: dict[str, float]) -> float:
    """
    多资产风险调整倍数

    Args:
        positions: {"BTCUSDT": risk_usd, "XAUUSD": risk_usd}

    Returns: 乘数（≤1.0），乘到每笔 risk_usd 上
    """
    if len(positions) < 2:
        return 1.0

    corr_state = compute_correlation()
    if corr_state["status"] not in ("ok", "proxy_degraded"):
        return 1.0
    # 代理腿偏差过大 → 不给减仓建议（可见降级：相关性仍展示，但不动仓位）
    if corr_state["status"] == "proxy_degraded":
        return 1.0

    corr = corr_state["correlation_full"]

    # 强正相关 = 组合风险加倍 → 各减30%
    if corr > 0.5:
        return 0.7
    # 弱正相关 → 各减15%
    elif corr > 0.2:
        return 0.85
    # 强负相关 = 好的分散 → 不减
    elif corr < -0.3:
        return 1.0
    # 其他 → 标准
    return 1.0


def save_correlation_state():
    """保存当前相关性状态"""
    state = compute_correlation()
    CORR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CORR_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def load_correlation_state() -> dict:
    """读取缓存的相关性状态"""
    if CORR_FILE.exists():
        try:
            return json.loads(CORR_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return compute_correlation()


# ═══ CLI ═══
if __name__ == "__main__":
    if "--json" in sys.argv or "-j" in sys.argv:
        state = compute_correlation()
        print(json.dumps(state, indent=2, ensure_ascii=False))
    elif "--save" in sys.argv:
        state = save_correlation_state()
        print(f"已保存: corr={state['correlation_full']} regime={state['regime']}")
    elif "--multiplier" in sys.argv:
        bal = 67.52
        btc_risk = 0.68
        xau_risk = 0.68
        mult = multi_asset_risk_multiplier({"BTCUSDT": btc_risk, "XAUUSD": xau_risk})
        print(f"多资产风险乘数: {mult:.2f}")
        print(f"BTC调整后: {btc_risk * mult:.2f}U")
        print(f"XAU调整后: {xau_risk * mult:.2f}U")
    else:
        state = compute_correlation()
        print(f"BTC vs XAU 相关性矩阵")
        print(f"  黄金腿来源: {state.get('gold_source')}"
              + (f"（与 OANDA 现货偏差 {state['gold_deviation_pct']:+.2f}%）"
                 if state.get("gold_deviation_pct") is not None else ""))
        print(f"  全量相关: {state['correlation_full']}")
        print(f"  短期相关: {state['correlation_short']}")
        print(f"  体制: {state['regime']} 趋势: {state['trend']}")
        print(f"  分散效益: {state['diversification_benefit']}")
        print(f"  建议: {state['advice']}")
