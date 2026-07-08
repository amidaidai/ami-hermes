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


def _contains_markdown_table(text: str) -> bool:
    """Detect GitHub/Rich-Markdown pipe tables.

    Telegram normal sendMessage MarkdownV2 does not render tables. Bot API 10.1
    rich messages do render Markdown pipe tables when sent through
    sendRichMessage with rich_message.markdown, so table-like push cards must be
    routed there instead of plain sendMessage.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    for i in range(len(lines) - 1):
        header = lines[i]
        sep = lines[i + 1]
        if not (header.startswith("|") and header.endswith("|") and "|" in header.strip("|")):
            continue
        cells = [c.strip() for c in sep.strip("|").split("|")]
        if cells and all(c.replace(":", "").replace("-", "").strip() == "" and "-" in c for c in cells):
            return True
    return False


def _normalize_rich_markdown_tables(text: str) -> str:
    """Make Telegram RichMarkdown table parsing reliable on mobile.

    Bot API 10.1 RichMarkdown parses a pipe table into RichBlockTable when the
    table starts directly at the block boundary. Standalone Chinese title lines
    such as "表1 · 行情全景" immediately before the pipe header make Telegram keep
    the following table as paragraph text on some clients/server parses. Drop
    those redundant title lines; the table headers carry the section meaning.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if cur.startswith("表") and "·" in cur and nxt.startswith("|") and nxt.endswith("|"):
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _build_base_payload(target: str) -> dict[str, object]:
    chat_id, thread_id = parse_telegram_target(target)
    payload: dict[str, object] = {"chat_id": chat_id}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    return payload


def _post_json(method: str, payload: dict[str, object], token: str, timeout: int) -> tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/bot{token}/{method}",
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


def _post_message(target: str, text: str, token: str, parse_mode: str | None, timeout: int) -> tuple[bool, str]:
    rich_requested = parse_mode in {"RichMarkdown", "rich_markdown"}
    rich_auto = parse_mode is None and _contains_markdown_table(text)
    if rich_requested or rich_auto:
        rich_text = _normalize_rich_markdown_tables(text)
        payload = _build_base_payload(target)
        payload["rich_message"] = {"markdown": rich_text, "skip_entity_detection": False}
        ok, reason = _post_json("sendRichMessage", payload, token, timeout)
        if ok:
            return True, "rich_sent"
        # If Telegram rejects the new endpoint/format, preserve delivery for
        # non-explicit auto-detected tables but make the downgrade visible.
        if rich_requested:
            return False, reason
        fallback = _build_base_payload(target)
        fallback["text"] = text
        ok2, reason2 = _post_json("sendMessage", fallback, token, timeout)
        if ok2:
            return True, f"sent_plain_after_rich_fail:{reason}"
        return False, f"rich:{reason}; plain:{reason2}"

    payload = _build_base_payload(target)
    payload["text"] = text
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return _post_json("sendMessage", payload, token, timeout)


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


def send_telegram_photo(
    target: str,
    photo_path: str,
    caption: str | None = None,
    parse_mode: str | None = None,
    timeout: int = 20,
    retries: int = 3,
) -> tuple[bool, str]:
    """直连 Bot API sendPhoto 发送图片（如主周期 TradingView 截图）。

    返回 (成功, 原因)。失败落盘到 pending（含 caption），供后续补发。
    caption 走 RichMarkdown 时 Telegram 会尝试渲染，但图片 caption 对
    RichMarkdown 表格支持不稳定，建议 caption 留空或纯文字。
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or token_from_env_file()
    if not token:
        reason = "missing TELEGRAM_BOT_TOKEN"
        if caption:
            append_pending(target, caption, reason, parse_mode)
        return False, reason
    if not photo_path or not Path(photo_path).exists():
        reason = f"photo not found: {photo_path}"
        if caption:
            append_pending(target, caption, reason, parse_mode)
        return False, reason

    chat_id, thread_id = parse_telegram_target(target)
    last_reason = "not attempted"
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error
    for attempt in range(max(1, retries)):
        try:
            boundary = f"----tangxi{int(time.time()*1000)}"
            parts: list[bytes] = []
            # chat_id
            parts.append(f"--{boundary}\r\n".encode("utf-8"))
            parts.append(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
            parts.append(f"{chat_id}\r\n".encode("utf-8"))
            if thread_id is not None:
                parts.append(f"--{boundary}\r\n".encode("utf-8"))
                parts.append(b'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n')
                parts.append(f"{thread_id}\r\n".encode("utf-8"))
            if caption:
                parts.append(f"--{boundary}\r\n".encode("utf-8"))
                parts.append(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
                parts.append(f"{caption}\r\n".encode("utf-8"))
            if parse_mode:
                parts.append(f"--{boundary}\r\n".encode("utf-8"))
                parts.append(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n')
                parts.append(f"{parse_mode}\r\n".encode("utf-8"))
            # photo file
            parts.append(f"--{boundary}\r\n".encode("utf-8"))
            parts.append(
                f'Content-Disposition: form-data; name="photo"; filename="{Path(photo_path).name}"\r\n'.encode("utf-8")
            )
            parts.append(b"Content-Type: image/png\r\n\r\n")
            with open(photo_path, "rb") as fp:
                parts.append(fp.read())
            parts.append(b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))
            body = b"".join(parts)
            req = _urllib_request.Request(
                f"{API_BASE}/bot{token}/sendPhoto",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            with _urllib_request.urlopen(req, timeout=timeout) as resp:
                rb = json.loads(resp.read().decode("utf-8", errors="replace"))
            if rb.get("ok"):
                return True, "photo_sent"
            last_reason = f"api: {rb.get('description', 'unknown')}"
        except _urllib_error.HTTPError as exc:
            try:
                desc = json.loads(exc.read().decode("utf-8", errors="replace")).get("description", str(exc))
            except Exception:
                desc = str(exc)
            last_reason = f"http {exc.code}: {desc}"
            if 400 <= exc.code < 500:
                break
        except (OSError, ValueError, TimeoutError) as exc:
            last_reason = f"network: {exc}"
        if attempt < retries - 1:
            time.sleep(min(2 ** attempt, 8))
    if caption:
        append_pending(target, caption, last_reason, parse_mode)
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


def push_tg_rich(target: str, text: str, token: str | None = None) -> tuple[bool, str]:
    """棠溪统一推送：纯 Markdown 管道表 → Telegram RichMarkdown 真表格。

    不走 hermes send / cron 的 MarkdownV2 退化通道，直接 sendRichMessage
    渲染真表格。供所有推 TG 的 no_agent 脚本调用。失败落盘 pending。
    """
    return send_telegram_reliable(target, text, token=token, parse_mode="RichMarkdown", retries=3)


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
