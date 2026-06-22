#!/usr/bin/env python3
"""BTC alert pusher v6 — 新格式自带分层方向，推送器仅读取→分块→发送。"""
import os, sys

from telegram_direct import send_telegram_direct

DIR = os.path.expanduser("~/AppData/Local/hermes/data")
PENDING = os.path.join(DIR, "btc_pending.txt")
TARGET = "telegram:-1003733144325:386"
MAX_TELEGRAM_CHARS = 3900


def log_ascii(message: str) -> None:
    safe = message.encode("ascii", "replace").decode("ascii")
    sys.stdout.write(safe.rstrip() + "\n")
    sys.stdout.flush()


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def truncate_file(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.truncate(0)


def telegram_chunks(text: str) -> list[str]:
    """Split into Telegram-safe chunks at line boundaries."""
    chunks = []
    current = []
    current_len = 0
    for line in text.splitlines():
        add_len = len(line) + 1
        if current and current_len + add_len > MAX_TELEGRAM_CHARS:
            chunks.append("\n".join(current).rstrip())
            current = [line]
            current_len = add_len
        else:
            current.append(line)
            current_len += add_len
    if current:
        chunks.append("\n".join(current).rstrip())
    return [c for c in chunks if c.strip()]


if __name__ == "__main__":
    if not os.path.exists(PENDING):
        sys.exit(0)

    size = os.path.getsize(PENDING)
    if size == 0:
        sys.exit(0)

    raw = read_text(PENDING)
    if not raw.strip():
        truncate_file(PENDING)
        sys.exit(0)

    # 新格式 v3.3 自带方向/分层 — 直接发送，不做二次加工
    chunks = telegram_chunks(raw.strip())
    if not chunks:
        truncate_file(PENDING)
        sys.exit(0)

    for idx, chunk in enumerate(chunks, start=1):
        ok, reason = send_telegram_direct(TARGET, chunk)
        if not ok:
            log_ascii(f"ERROR btc_push_cron send failed chunk={idx}/{len(chunks)} reason={reason}")
            sys.exit(1)

    truncate_file(PENDING)
    sys.exit(0)
