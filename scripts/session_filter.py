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


def get_active_sessions(asset: str = "XAUUSD", dt: datetime = None) -> list[str]:
    """返回当前活跃的交易时段"""
    if dt is None:
        dt = datetime.now(TZ_UTC)
    hour = dt.hour
    
    if asset.upper() in ("BTCUSDT", "BTC", "ETHUSDT"):
        return ["24/7"]
    
    # 黄金/外汇周末休市 → 直接 closed，不按小时判时段
    if is_weekend_closed(dt):
        return ["closed"]
    
    active = []
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
    dt = datetime.now(TZ_UTC)
    
    if asset.upper() in ("BTCUSDT", "BTC"):
        return "24/7 可交易"
    
    if "closed" in sessions:
        return "🔴 闭市"
    
    names = {
        "asian": "亚洲",
        "london": "伦敦",
        "ny": "纽约",
        "overlap": "🔶 伦敦+纽约重叠"
    }
    active_names = [names.get(s, s) for s in sessions]
    
    kz = kill_zone_name(dt)
    if kz:
        kz_names = {
            "london_open": "London Open",
            "london_close": "London Close", 
            "ny_open": "NY Open"
        }
        return f"🟢 {'+'.join(active_names)} · Kill Zone: {kz_names.get(kz, kz)}"
    
    return f"🟢 {'+'.join(active_names)}"


def should_trade(asset: str = "XAUUSD", 
                 require_kill_zone: bool = False,
                 dt: datetime = None) -> tuple[bool, str]:
    """
    综合判断是否应该交易
    
    Returns:
        (should_trade, reason)
    """
    if dt is None:
        dt = datetime.now(TZ_UTC)
    
    # BTC always ok
    if asset.upper() in ("BTCUSDT", "BTC"):
        return True, "BTC 24/7"
    
    # Gold session check
    if not is_gold_trading_time(dt, require_liquidity=True):
        return False, "闭市/低流动性时段"
    
    # Kill zone filter
    if require_kill_zone and not is_kill_zone(dt):
        return False, "非Kill Zone时段"
    
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
