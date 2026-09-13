"""Bounded local-only monthly integrity audit; no collectors, TV or delivery."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {'_disabled', '_disabled_20260829', '_archive', '__pycache__'}
DEPENDENCIES = ('requests', 'pydantic', 'aiohttp', 'numpy', 'pandas', 'websockets')
CONTRACT_FILES = ('scripts/tv_indicator_contract.py', 'scripts/indicator_source_audit.py',
                  'scripts/tv_indicator_alignment_check.py', 'scripts/decision_loop.py',
                  'scripts/go_nogo_gate.py', 'scripts/render_tv_card.py', 'scripts/render_v96.py')


def inspect_repository(root: Path = ROOT) -> dict:
    errors = []
    count = 0
    for path in sorted((root / 'scripts').rglob('*.py')):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        count += 1
        try:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
        except (SyntaxError, UnicodeError, OSError):
            errors.append(path.relative_to(root).as_posix())
    missing = [name for name in CONTRACT_FILES if not (root / name).is_file()]
    dependencies = {name: importlib.util.find_spec(name) is not None for name in DEPENDENCIES}
    return {'scope': 'local_static_only', 'tradingview_live_verified': False,
            'external_sources_verified': False, 'tests_executed': False,
            'collected_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'python_files': count, 'syntax_errors': errors, 'missing_contract_files': missing,
            'dependencies_discoverable': dependencies,
            'ok': not errors and not missing and all(dependencies.values())}


def main() -> int:
    report = inspect_repository()
    output = ROOT / 'data/maintenance/local_integrity_audit.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, output)
    # no-agent cron is configured deliver=local; no messaging import here.
    print(json.dumps({'ok': report['ok'], 'scope': report['scope'], 'report': str(output)}, ensure_ascii=False))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
