#!/usr/bin/env python3
"""
棠溪 · Telegram 可靠推送 v1.1

目标：关键位/维护报告推送不再只依赖 `hermes send` 或单次 Bot API 请求。
特性：
- 直连 Telegram Bot API，3次重试，指数退避
- 自动读取 TELEGRAM_BOT_TOKEN（环境变量或 Hermes .env）
- 失败消息落盘到 D:/Hermes agent/data/pending_telegram.jsonl
- 支持后续 flush_pending() 补发
- 兼容旧 `telegram_direct.send_telegram_direct()` 调用
"""
from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

API_BASE = "https://api.telegram.org"
TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path("D:/Hermes agent")
PENDING_FILE = REPO_ROOT / "data" / "pending_telegram.jsonl"


def parse_telegram_target(target: str) -> tuple[str, int | None]:
    """解析 telegram:<chat_id>:<thread_id> / telegram:<chat_id>。"""
    s = target.strip()
    if s.startswith("telegram:"):
        s = s[len("telegram:"):]
    parts = s.split(":")
    if len(parts) >= 2 and parts[-1].lstrip("-").isdigit():
        chat_id = ":".join(parts[:-1])
        if chat_id:
            return chat_id, int(parts[-1])
    return s, None


def _env_candidates() -> Iterable[Path]:
    yield Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\.env"))
    yield Path.home() / "AppData" / "Local" / "hermes" / ".env"
    yield Path.home() / ".hermes" / ".env"


_TOKEN_CACHE: str | None = None


def token_from_env_file() -> str | None:
    global _TOKEN_CACHE
    if _TOKEN_CACHE is not None:
        return _TOKEN_CACHE or None
    for path in _env_candidates():
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                if key.strip() == "TELEGRAM_BOT_TOKEN":
                    val = val.strip().strip('"').strip("'")
                    if val:
                        _TOKEN_CACHE = val
                        return val
        except OSError:
            continue
    _TOKEN_CACHE = ""
    return None


def _post_message(target: str, text: str, token: str, parse_mode: str | None, timeout: int) -> tuple[bool, str]:
    chat_id, thread_id = parse_telegram_target(target)
    payload: dict[str, object] = {"chat_id": chat_id, "text": text}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        if body.get("ok"):
            return True, "sent"
        return False, f"api: {body.get('description', 'unknown')}"
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            desc = body.get("description", str(exc))
        except Exception:
            desc = str(exc)
        return False, f"http {exc.code}: {desc}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return False, f"network: {exc}"


def append_pending(target: str, text: str, reason: str, parse_mode: str | None = None) -> Path:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "created_at": datetime.now(TZ).isoformat(),
        "target": target,
        "text": text,
        "parse_mode": parse_mode,
        "reason": reason,
        "attempts": 0,
    }
    with PENDING_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return PENDING_FILE


def send_telegram_reliable(
    target: str,
    text: str,
    token: str | None = None,
    parse_mode: str | None = None,
    timeout: int = 15,
    retries: int = 5,
    persist_on_fail: bool = True,
) -> tuple[bool, str]:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN") or token_from_env_file()
    if not token:
        reason = "missing TELEGRAM_BOT_TOKEN"
        if persist_on_fail:
            append_pending(target, text, reason, parse_mode)
        return False, reason

    last_reason = "not attempted"
    for attempt in range(max(1, retries)):
        ok, reason = _post_message(target, text, token, parse_mode, timeout)
        if ok:
            return True, reason
        last_reason = reason
        # 4xx 通常是 chat/topic/permission 错误，重试没有意义，但保留落盘。
        if reason.startswith("http 4"):
            break
        if attempt < retries - 1:
            time.sleep(min(2 ** attempt, 8))
    if persist_on_fail:
        append_pending(target, text, last_reason, parse_mode)
    return False, last_reason


def flush_pending(limit: int = 20) -> tuple[int, int]:
    if not PENDING_FILE.exists():
        return 0, 0
    rows = []
    for line in PENDING_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    sent = 0
    kept = []
    for row in rows[:limit]:
        ok, reason = send_telegram_reliable(
            row.get("target", "telegram:-1003733144325:416"),
            row.get("text", ""),
            parse_mode=row.get("parse_mode") or None,
            persist_on_fail=False,
        )
        if ok:
            sent += 1
        else:
            row["attempts"] = int(row.get("attempts") or 0) + 1
            row["last_reason"] = reason
            kept.append(row)
    kept.extend(rows[limit:])
    if kept:
        PENDING_FILE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + "\n", encoding="utf-8")
    else:
        PENDING_FILE.unlink(missing_ok=True)
    return sent, len(kept)


# Backward-compatible name used by existing scripts.
def send_telegram_direct(target: str, text: str, token: str | None = None,
                         parse_mode: str | None = None, timeout: int = 10) -> tuple[bool, str]:
    return send_telegram_reliable(target, text, token=token, parse_mode=parse_mode, timeout=timeout, retries=3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="telegram:-1003733144325:416")
    parser.add_argument("text", nargs="?", default="telegram_reliable 自测")
    parser.add_argument("--flush", action="store_true")
    args = parser.parse_args()
    if args.flush:
        sent, kept = flush_pending()
        print(json.dumps({"sent": sent, "kept": kept}, ensure_ascii=False))
        return 0 if kept == 0 else 1
    ok, reason = send_telegram_reliable(args.target, args.text)
    print(json.dumps({"ok": ok, "reason": reason}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
