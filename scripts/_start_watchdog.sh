#!/usr/bin/env bash
# 启动 watchdog（带 .env token 注入），用 hermes venv 的 python
cd "/d/Hermes agent" || exit 1
ENV_FILE="$LOCALAPPDATA/hermes/.env"
TOKEN_LINE=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1)
TOKEN_VAL=${TOKEN_LINE#TELEGRAM_BOT_TOKEN=}
TOKEN_VAL=${TOKEN_VAL//\"/}
export TELEGRAM_BOT_TOKEN="$TOKEN_VAL"
VENV_PY="$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe"
exec "$VENV_PY" "scripts/watchdog.py"
