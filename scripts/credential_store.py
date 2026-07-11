#!/usr/bin/env python3
"""棠溪统一凭据读取器：环境变量优先，本地 hermes/secrets 次之。"""
from __future__ import annotations

import os
from pathlib import Path

SECRETS_DIR = Path(__file__).resolve().parents[1] / "hermes" / "secrets"


def read_secret(filename: str, *env_names: str) -> str:
    """读取凭据，不记录、不回显；环境变量优先于本地秘密文件。"""
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        return (SECRETS_DIR / filename).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
