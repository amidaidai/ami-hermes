"""XAU-only OHLC evidence. Collection time never replaces candle time."""
from datetime import datetime, timezone, timedelta
import math

SECONDS = {'1D': 86400, '4h': 14400, '1h': 3600, '15m': 900, '5m': 300}
IDENTITIES = {'tradingview_mcp': 'OANDA:XAUUSD', 'oanda': 'XAU_USD', 'twelvedata': 'XAU/USD'}


def timestamp(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            n = float(value)
            if abs(n) >= 1e12:
                n /= 1000
            return datetime.fromtimestamp(n, timezone.utc)
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        # No guessed local timezone. Provider adapters explicitly assign UTC.
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def evidence(source, symbol, tf, opened, *, next_open=None, now=None, closed=False):
    now = now or datetime.now(timezone.utc)
    start = timestamp(opened)
    if source not in IDENTITIES or symbol != IDENTITIES[source] or tf not in SECONDS or start is None:
        return None
    end = start + timedelta(seconds=SECONDS[tf])
    following = timestamp(next_open) if next_open is not None else None
    if next_open is not None and (following is None or following < end):
        return None
    if not closed and following is None:
        return None
    if end > now or (following is not None and following > now):
        return None
    return {'source': source, 'symbol': symbol, 'timeframe': tf,
            'bar_open_time': start.isoformat(), 'bar_close_time': end.isoformat(),
            'next_bar_open_time': following.isoformat() if following else None,
            'observed_at': now.isoformat(), 'closed': True,
            'closure_basis': 'provider_complete' if closed else 'next_bar_boundary',
            'same_source_as_chart': source in ('tradingview_mcp', 'oanda')}
