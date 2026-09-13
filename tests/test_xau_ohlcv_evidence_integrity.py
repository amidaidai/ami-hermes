"""Offline identity/time evidence regressions; no shared chart or network."""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import xau_tv_sync as S
import xau_ohlcv_source as X

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def _tv_payload(tf='5m', step=300, offset=600):
    return {'last_5_bars': [
        {'time': NOW.timestamp()-offset, 'open':4300, 'high':4300.01, 'low':4299.99, 'close':4300},
        {'time': NOW.timestamp()-offset+step, 'open':4300, 'high':4300.01, 'low':4299.99, 'close':4300}]}


def test_strict_parser_preserves_closed_bar_time_and_source():
    state = {'symbol': 'OANDA:XAUUSD', 'resolution': '5'}
    out = S._parse_ohlcv(json.dumps(_tv_payload()), json.dumps(state), expected_tf='5m', now=NOW)
    assert out['evidence']['source'] == 'tradingview_mcp'
    assert out['evidence']['symbol'] == 'OANDA:XAUUSD'
    assert out['evidence']['timeframe'] == '5m'
    assert out['evidence']['bar_open_time'] == '2026-09-11T11:50:00+00:00'
    assert out['evidence']['bar_close_time'] == '2026-09-11T11:55:00+00:00'
    assert out['evidence']['closed'] is True
    assert out['high'] - out['low'] < .1  # micro-range alone is not invalid


def test_strict_parser_rejects_duplicate_or_wrong_coverage():
    state = json.dumps({'symbol': 'OANDA:XAUUSD', 'resolution': '5'})
    for step in (0, 60, -300):
        assert S._parse_ohlcv(json.dumps(_tv_payload(step=step)), state, expected_tf='5m', now=NOW) is None
    assert S._parse_ohlcv(json.dumps(_tv_payload(offset=-300)), state, expected_tf='5m', now=NOW) is None


def test_collector_rejects_chart_identity_changed_during_read(monkeypatch):
    monkeypatch.setattr(S, 'TIMEFRAMES', [('5m', '5')])
    async def no_wait(*args): pass
    monkeypatch.setattr(S.asyncio, 'sleep', no_wait)
    states = iter([{'symbol':'OANDA:XAUUSD', 'resolution':'5'},
                   {'symbol':'OANDA:XAUUSD', 'resolution':'15'}])
    async def state(*args): return json.dumps(next(states))
    async def ohlcv(*args): return json.dumps(_tv_payload())
    result = {'timeframes': {}}
    asyncio.run(S._collect_xau_tfs_via_chart(None, result, no_wait, state, ohlcv, lambda x:x))
    assert not result['timeframes']
    assert result['ohlcv_evidence']['5m']['status'] == 'rejected'


def test_twelvedata_requires_response_identity_and_retains_time(monkeypatch):
    values = [{'datetime':'2026-09-11 11:55:00','open':'4300','high':'4301','low':'4299','close':'4300'},
              {'datetime':'2026-09-11 11:50:00','open':'4300','high':'4301','low':'4299','close':'4300'}]
    payload = {'meta':{'symbol':'EUR/USD','interval':'5min','exchange_timezone':'UTC'}, 'values':values}
    monkeypatch.setattr(X, '_http_json', lambda *a, **k:payload)
    assert X._twelvedata_candles('test', '5min') == []
    payload['meta']['symbol'] = 'XAU/USD'
    out = X._twelvedata_candles('test', '5min')
    assert out[0]['evidence']['bar_open_time'] == '2026-09-11T11:50:00+00:00'
    assert X._clean(out[0])['evidence']['same_source_as_chart'] is False
    payload['meta']['interval'] = '1min'
    assert X._twelvedata_candles('test', '5min') == []


def test_chart_parser_rejects_wrong_actual_timeframe():
    payload = {'last_5_bars': [
        {'time': NOW.timestamp()-600, 'open':4300, 'high':4301, 'low':4299, 'close':4300},
        {'time': NOW.timestamp()-300, 'open':4300, 'high':4301, 'low':4299, 'close':4300}]}
    state = {'symbol': 'OANDA:XAUUSD', 'resolution': '15'}
    assert S._parse_ohlcv(json.dumps(payload), json.dumps(state), expected_tf='5m', now=NOW) is None
