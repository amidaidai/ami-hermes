"""Retired monitor/daemon entrypoints must not start processes or send Telegram."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "scripts" / "btc_daemon.py",
    ROOT / "scripts" / "monitor" / "btc_watchdog.py",
    ROOT / "scripts" / "monitor" / "market_watchdog.py",
    ROOT / "scripts" / "btc_keylevel_sentinel.py",
    ROOT / "scripts" / "btc_keylevel_rest_guard.py",
    ROOT / "scripts" / "btc_keylevel_ws_guard.py",
    ROOT / "scripts" / "btc_price_arrival_sentinel.py",
    ROOT / "scripts" / "行情守望.py",
]


def test_retired_entrypoints_exit_zero_with_authority_banner():
    for path in SCRIPTS:
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        assert result.returncode == 0, (path.name, result.returncode, result.stderr)
        combined = (result.stdout or "") + (result.stderr or "")
        assert "已退役" in combined, path.name
        assert "keylevel_guard" in combined, path.name
