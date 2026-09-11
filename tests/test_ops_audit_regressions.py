import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_preflight as audit


@pytest.fixture
def healthy(monkeypatch):
    monkeypatch.setattr(audit.socket, 'socket', lambda: SimpleNamespace(settimeout=lambda n: None, connect_ex=lambda addr: 0, close=lambda: None))
    monkeypatch.setattr(audit, '_cache_report', lambda name, *a, **k: dict(name=name, fresh=True, age_h=0, symbol='BTCUSDT', status='live', reason=''))
    monkeypatch.setattr(audit, 'strict_market_contracts', lambda: {'btc_five_tf': {'usable': True}, 'xau_pair': {'usable': True}})
    monkeypatch.setattr(audit, 'keylevel_runtime_report', lambda: {'usable': True})
    monkeypatch.setattr(audit, 'tv_business_report', lambda: {'usable': True}, raising=False)
    monkeypatch.setattr(audit, 'read_json', lambda path: {'symbols': {'BTCUSDT': {'levels': [{'enabled': True}]}}} if path.name == 'keylevels_config.json' else {'jobs': []})


@pytest.mark.parametrize('failure', ['cache', 'approved', 'guard'])
def test_critical_failure_changes_exit(healthy, monkeypatch, failure):
    if failure == 'cache':
        monkeypatch.setattr(audit, '_cache_report', lambda name, *a, **k: dict(name=name, fresh=False, age_h=99, symbol='BTCUSDT', status='stale', reason='expired'))
    elif failure == 'approved':
        monkeypatch.setattr(audit, 'read_json', lambda path: {})
    else:
        monkeypatch.setattr(audit, 'keylevel_runtime_report', lambda: {'usable': False, 'reason': 'structure_review_required'})
    assert audit.main() == 1


def test_healthy_preflight_returns_zero(healthy):
    assert audit.main() == 0


@pytest.mark.parametrize('failed_name', [
    'tv_live_BTCUSDT.json', 'tv_live_XAUUSD.json',
    'source_snapshot_BTCUSDT.json', 'source_snapshot_XAUUSD.json',
])
def test_one_unhealthy_core_cache_is_enough_to_fail(healthy, monkeypatch, failed_name):
    monkeypatch.setattr(audit, '_cache_report', lambda name, *a, **k: dict(
        name=name, fresh=name != failed_name, age_h=0, symbol=k['expected_symbol'],
        status='unavailable' if name == failed_name else 'live', reason='',
    ))
    assert audit.main() == 1