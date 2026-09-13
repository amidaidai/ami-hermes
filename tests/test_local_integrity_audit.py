"""Local audit never equates completed process with valid evidence."""
import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'scripts/maintenance/local_integrity_audit.py'


def load():
    spec = importlib.util.spec_from_file_location('local_integrity_audit', P)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_contract_source_is_failed(tmp_path):
    result = load().inspect_repository(tmp_path)
    assert result['ok'] is False
    assert result['scope'] == 'local_static_only'
    assert result['tradingview_live_verified'] is False


def test_existing_python_syntax_error_is_failed(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / 'bad.py').write_text('def broken(:', encoding='utf-8')
    result = load().inspect_repository(tmp_path)
    assert 'scripts/bad.py' in result['syntax_errors']


def test_archive_is_not_active_code(tmp_path):
    archive = tmp_path / 'scripts/_disabled'
    archive.mkdir(parents=True)
    (archive / 'old.py').write_text('def old(:', encoding='utf-8')
    assert not load().inspect_repository(tmp_path)['syntax_errors']
