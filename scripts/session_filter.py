#!/usr/bin/env python3
"""
棠溪 · 交易时段过滤器 v1.0
借鉴: BAKOME Gold Scalper (MIT License)
适配: BTC 24/7 + XAU London/NY 时段
"""

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

TZ_UTC = timezone.utc
TZ_CST = timezone(timedelta(hours=8))  # 北京时间

# ═══ 黄金交易时段 (UTC) ═══
# London: 07:00-17:00 UTC = 15:00-01:00 CST
# NY:     12:00-22:00 UTC = 20:00-06:00 CST
# Overlap: 12:00-17:00 UTC = 20:00-01:00 CST (最佳)

GOLD_SESSIONS = {
    "asian":     (0, 6),     # 08:00-14:00 CST (低波动)
    "london":    (7, 17),    # 15:00-01:00 CST (主力)
    "ny":        (12, 22),   # 20:00-06:00 CST (主力)
    "overlap":   (12, 17),   # 20:00-01:00 CST (最佳)
}

# Kill Zones (Silver Bullet windows)
GOLD_KILL_ZONES = {
    "london_open":  (8, 10),    # London Open: 08:00-10:00 UTC
    "london_close": (15, 16),   # London Close: 15:00-16:00 UTC
    "ny_open":      (12, 14),   # NY Open: 12:00-14:00 UTC
}

BTC_ACTIVE_HOURS = None  # None = 24/7, BTC always tradeable


# ═══ 黄金/外汇周末休市窗口 (UTC) ═══
# 收盘: 周五 21:00 UTC (纽约盘结束)
# 开盘: 周日 22:00 UTC (悉尼盘开始)
# 期间(周六全天 + 周五晚 + 周日早)市场关闭，不应推送告警。
def is_weekend_closed(dt: datetime = None) -> bool:
    """黄金/外汇是否处于周末休市窗口 (UTC基准)。BTC不受影响。"""
    if dt is None:
        dt = datetime.now(TZ_UTC)
    wd = dt.weekday()  # 周一=0 … 周五=4 周六=5 周日=6
    hour = dt.hour
    if wd == 5:                       # 周六全天休市
        return True
    if wd == 4 and hour >= 21:        # 周五 21:00 UTC 后收盘
        return True
    if wd == 6 and hour < 22:         # 周日 22:00 UTC 前未开盘
        return True
    return False


@dataclass
class SessionConfig:
    """时段配置"""
    asset: str = "XAUUSD"
    trade_asian: bool = False
    trade_london: bool = True
    trade_ny: bool = True
    use_kill_zones: bool = False  # 只在Kill Zone出信号


def get_asset_class(asset: str) -> str:
    """统一资产分类"""
    su = str(asset).upper()
    if "XAU" in su or "GOLD" in su:
        return "gold"
    if "CALL" in su or "PUT" in su or (su.endswith(("C", "P")) and any(c.isdigit() for c in su)):
        return "option"
    forex = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]
    if any(x in su for x in forex) and not su.endswith("USDT"):
        return "forex"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su:
        return "crypto"
    if su.isalpha() and len(su) <= 5:
        return "stock"
    return "other"

# ═══ 股票/外汇时段 (UTC) ═══
# 简化为主要市场开放窗口
STOCK_SESSIONS = {
    "us": (13, 21),      # 约 21:00-05:00 CST (美股)
    "asia": (0, 6),      # 亚洲
}

FOREX_SESSIONS = {
    "london": (7, 17),
    "ny": (12, 22),
    "overlap": (12, 17),
}

def get_active_sessions(asset: str = "XAUUSD", dt: datetime = None) -> list[str]:
    """返回当前活跃的交易时段 (多资产版)"""
    if dt is None:
        dt = datetime.now(TZ_UTC)
    hour = dt.hour
    ac = get_asset_class(asset)

    if ac == "crypto":
        return ["24/7"]

    if is_weekend_closed(dt) and ac != "crypto":
        return ["closed"]

    active = []
    if ac == "gold":
        for name, (start, end) in GOLD_SESSIONS.items():
            if start <= hour < end:
                active.append(name)
    elif ac == "forex":
        for name, (start, end) in FOREX_SESSIONS.items():
            if start <= hour < end:
                active.append(name)
    elif ac == "stock":
        if 13 <= hour < 21:
            active.append("us_market")
    else:
        for name, (start, end) in GOLD_SESSIONS.items():
            if start <= hour < end:
                active.append(name)

    return active if active else ["closed"]


def is_gold_trading_time(dt: datetime = None, require_liquidity: bool = True) -> bool:
    """
    黄金是否在交易时段
    
    Args:
        dt: UTC时间
        require_liquidity: 是否要求高流动性时段(London或NY)
    """
    if dt is None:
        dt = datetime.now(TZ_UTC)
    
    sessions = get_active_sessions("XAUUSD", dt)
    
    if "closed" in sessions:
        return False
    
    if require_liquidity:
        return bool({"london", "ny", "overlap"} & set(sessions))
    
    return True


def is_kill_zone(dt: datetime = None) -> bool:
    """是否在Kill Zone(Silver Bullet窗口)"""
    if dt is None:
        dt = datetime.now(TZ_UTC)
    hour = dt.hour
    
    for name, (start, end) in GOLD_KILL_ZONES.items():
        if start <= hour < end:
            return True
    return False


def kill_zone_name(dt: datetime = None) -> str:
    """当前Kill Zone名称"""
    if dt is None:
        dt = datetime.now(TZ_UTC)
    hour = dt.hour
    
    for name, (start, end) in GOLD_KILL_ZONES.items():
        if start <= hour < end:
            return name
    return ""


def session_status(asset: str = "XAUUSD") -> str:
    """返回可读的时段状态字符串"""
    sessions = get_active_sessions(asset)
    if asset.upper() in ("BTCUSDT", "BTC"):
        return "24/7 可交易"
    if "closed" in sessions:
        return "🔴 闭市"
    names = {
        "asian": "亚洲",
        "london": "伦敦",
        "ny": "纽约",
        "overlap": "🔶 伦敦+纽约重叠",
        "us_market": "美股"
    }
    active_names = [names.get(s, s) for s in sessions]
    return f"🟢 {'+'.join(active_names)}"

def require_liquidity_for_gold(dt: datetime = None) -> bool:
    if dt is None:
        dt = datetime.now(TZ_UTC)
    sessions = get_active_sessions("XAUUSD", dt)
    return any(s in sessions for s in ["london", "ny", "overlap"])

def has_min_liquidity(symbol: str, snapshot: dict = None) -> bool:
    """F轮简单流动性门槛：crypto 优先高量，gold/forex 用时段，stock 用美股时段。"""
    ac = get_asset_class(symbol)
    if ac == "crypto":
        if snapshot:
            q = snapshot.get("quality", "B")
            try:
                conf = float(snapshot.get("confidence", 0) or 0)
            except (TypeError, ValueError):
                conf = 0
            try:
                spread = float(snapshot.get("price_spread_pct", 0) or 0)
            except (TypeError, ValueError):
                spread = 0
            if q in ("A", "A-", "B+"):
                return True
            return q == "B" and conf >= 70 and spread <= 0.5
        return True  # crypto 24/7，缺快照时不因数据桥空值静默
    if ac == "gold":
        return require_liquidity_for_gold()
    return True  # 其他由 should_trade 控制

def should_trade(asset: str = "XAUUSD", 
                 require_kill_zone: bool = False,
                 dt: datetime = None) -> tuple[bool, str]:
    """
    综合判断是否应该交易 (全面多资产版 2026)
    Returns: (should_trade, reason)
    """
    if dt is None:
        dt = datetime.now(TZ_UTC)

    ac = get_asset_class(asset)

    if ac == "crypto":
        return True, "crypto 24/7"

    if is_weekend_closed(dt):
        return False, "周末闭市"

    active = get_active_sessions(asset, dt)
    if "closed" in active:
        return False, "闭市/低流动性时段"

    if ac == "gold":
        if require_kill_zone and not is_kill_zone(dt):
            return False, "非Kill Zone时段"
        if require_liquidity_for_gold(dt):
            return True, f"黄金高流动性 · {'+'.join(active)}"
        return True, session_status(asset)

    if ac == "forex":
        if any(x in active for x in ["london", "ny", "overlap"]):
            return True, f"外汇主要交易时段 · {'+'.join(active)}"
        return False, "外汇非主要时段（建议避开亚洲）"

    if ac == "stock":
        if "us_market" in active:
            return True, "美股交易时段"
        return False, "美股休市/盘前盘后"

    if ac == "option":
        underlying = ''.join(c for c in asset if not c.isdigit()).replace("CALL","").replace("PUT","").rstrip("CP")
        return should_trade(underlying or asset, require_kill_zone, dt)

    return True, session_status(asset)


# ═══ 回测用时间过滤 ═══

def filter_by_time(asset: str, dt_str: str, 
                   require_liquidity: bool = False,
                   require_kill_zone: bool = False) -> bool:
    """从回测时间戳判断是否应交易"""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_UTC)
    except (ValueError, TypeError):
        return True  # 无法解析时默认允许
    
    ok, _ = should_trade(asset, require_kill_zone, dt)
    return ok


if __name__ == "__main__":
    print(f"当前状态: {session_status('XAUUSD')}")
    print(f"Kill Zone: {is_kill_zone()} ({kill_zone_name()})")
    print(f"可交易: {should_trade('XAUUSD')}")
    print(f"可交易(BTC): {should_trade('BTCUSDT')}")
