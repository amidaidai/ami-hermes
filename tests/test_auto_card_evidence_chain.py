"""Offline transport fixtures, NOT observed live Pine evidence."""
import sys
import time
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import auto_card as card
import tv_data_bridge as bridge


def chain(monkeypatch, mutate=None):
    now = int(time.time() * 1000)
    close = now - 1000
    data = {'success': True, 'symbol': 'BINANCE:BTCUSDT.P', 'resolution': '15', 'studies': [
        {'name': 'SVP+ICT+VWAP+CVD', 'id': 'main-study', 'values': {
            'MCP Evidence Pack': '202609052111',
            'MCP Evidence Bar Time': str(close - 900000),
            'MCP Evidence Close Time': str(close)}}]}
    if mutate:
        mutate(data)
    monkeypatch.setattr(bridge, '_tv_json', lambda *a, **kw: data)
    indicators = bridge.read_indicators('BINANCE:BTCUSDT.P')
    cache = {'symbol': 'BINANCE:BTCUSDT.P', 'timeframe': '15', 'timestamp': now / 1000,
             'indicators': indicators, 'grade': 'A多', 'treatment': '允许',
             'decision_table': {'方向': '偏多', '进场': '100', '止损': '99', '目标': '103'}}
    engine = {'_tv_live_status': {'usable': True}, '_snapshot_status': {'age_hours': 0},
              '_tv_five_tf_required': True, '_tv_five_tf_status': {'usable': True},
              '_cross_validation': {'hard_blockers': [], 'warnings': []}}
    assert card._inject_tv_live_pine(engine, cache)
    main = card._tv_main_from_dmi(engine['_tv_pine'])
    return main, engine


def resolve(main, engine):
    return card._resolve_card_final_verdict('BTCUSDT', {'status': 'A多', 'direction': 'long', 'data_grade': 'A'},
        engine, main, {'asset_is_crypto': True, 'valid_code': 2, 'aligned': True}, {'atr': 1}, 'fvg_pullback')


def test_transport_to_resolver_preserves_verified_evidence(monkeypatch):
    main, engine = chain(monkeypatch)
    final = resolve(main, engine)
    frozen = engine['_decision_snapshot']
    assert frozen['schema_version'] == 20260905
    assert frozen['main']['location_valid'] is True
    assert frozen['main']['trigger_confirmed'] is True
    assert frozen['main']['bar_closed'] is True
    assert frozen['main']['tv_live_verified'] is True
    assert frozen['main']['tv_five_tf_verified'] is True
    assert frozen['main']['cross_source_hard_blockers'] == []
    assert not {'location', 'trigger', 'bar_closed'} & set(final['blockers'])


@pytest.mark.parametrize('key,value', [
    ('MCP Evidence Pack', None), ('MCP Evidence Pack', '202.61B'),
    ('MCP Evidence Pack', '202609050111'),
    ('MCP Evidence Close Time', 0),
])
def test_invalid_production_evidence_cannot_authorize(monkeypatch, key, value):
    main, engine = chain(monkeypatch, lambda d: d['studies'][0]['values'].update({key: value}))
    final = resolve(main, engine)
    assert final['executable'] is False
    assert engine['_evidence_status']['usable'] is False
    assert (final['entry'], final['stop'], final['target']) == (None, None, None)


def test_shadow_serializes_complete_frozen_inputs(monkeypatch):
    import shadow_calibration
    main, engine = chain(monkeypatch)
    engine['_shadow_enabled'] = True
    captured = []
    monkeypatch.setattr(shadow_calibration, 'append_shadow_signal', lambda path, row: captured.append(row))
    final = resolve(main, engine)
    assert len(captured) == 1
    row = captured[0]
    assert row['schema_version'] == 20260905
    assert row['main'] == engine['_decision_snapshot']['main']
    assert row['dual'] == engine['_decision_snapshot']['dual']
    assert row['final_verdict'] == final


@pytest.mark.parametrize('symbol,valid', [
    ('BTCUSDT', True), ('BINANCE:BTCUSDT.P', True),
    ('BYBIT:BTCUSDT.P', False), ('BINANCE:BTCUSDT', False),
])
def test_requested_explicit_product_identity(monkeypatch, symbol, valid):
    main, engine = chain(monkeypatch)
    main['direction'] = 'long'
    card._bind_main_evidence(symbol, main)
    assert main['location_valid'] is valid
