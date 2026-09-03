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
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable
from atomic_json import append_text_line, _append_text_line_unlocked, _atomic_write_text_unlocked, _file_lock, _thread_lock

API_BASE = "https://api.telegram.org"
TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path("D:/Hermes agent")
PENDING_FILE = REPO_ROOT / "data" / "pending_telegram.jsonl"
DEADLETTER_FILE = REPO_ROOT / "data" / "deadletter_telegram.jsonl"
MAX_PENDING_ATTEMPTS = 5
MAX_PENDING_AGE_SECONDS = 7 * 24 * 3600
RATE_LIMIT_FILE = REPO_ROOT / "data" / "telegram_rate_limit.json"
_RATE_LIMIT_UNTIL = 0.0


def _rate_limit_remaining() -> float:
    """Return the local Telegram cooldown, shared by text/photo/flush paths."""
    global _RATE_LIMIT_UNTIL
    now = time.time()
    if _RATE_LIMIT_UNTIL > now:
        return _RATE_LIMIT_UNTIL - now
    try:
        payload = json.loads(RATE_LIMIT_FILE.read_text(encoding="utf-8"))
        until = float(payload.get("until", 0))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        until = 0.0
    _RATE_LIMIT_UNTIL = max(_RATE_LIMIT_UNTIL, until)
    return max(0.0, _RATE_LIMIT_UNTIL - now)


def _set_rate_limit(seconds: float) -> None:
    """Persist a bounded cooldown after Telegram returns HTTP 429."""
    global _RATE_LIMIT_UNTIL
    until = time.time() + min(max(float(seconds), 1.0), 900.0)
    _RATE_LIMIT_UNTIL = max(_RATE_LIMIT_UNTIL, until)
    try:
        RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_FILE.write_text(
            json.dumps({"until": _RATE_LIMIT_UNTIL, "updated_at": datetime.now(TZ).isoformat()}),
            encoding="utf-8",
        )
    except OSError:
        pass


def _is_permanent_delivery_failure(reason: str) -> bool:
    """判断无需继续重试的投递失败。"""
    text = str(reason or "").lower()
    if text.startswith("http 429"):
        return False
    return (
        text.startswith("http 4")
        or text.startswith("api:")
        or text in {
            "automated_delivery_disabled",
            "automated_delivery_target_missing",
            "automated_delivery_target_mismatch",
        }
        or "unsupported parse_mode" in text
    )


def _deadletter_row(row: dict, reason: str) -> dict:
    item = dict(row)
    item["dead_letter"] = True
    item["dead_letter_at"] = datetime.now(TZ).isoformat()
    item["last_reason"] = reason
    return item


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


def configured_automated_target() -> str | None:
    """Return the explicit unattended-delivery target, if configured.

    Automated jobs must not inherit a historical topic from a call site.  The
    target is therefore a separate opt-in setting and must use the Telegram
    target syntax understood by this module.
    """
    target = os.environ.get("TANGXI_AUTOMATED_TG_TARGET", "").strip()
    if not target.startswith("telegram:"):
        return None
    chat_id, _thread_id = parse_telegram_target(target)
    return target if chat_id.strip() else None


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


def _table_cells(line: str) -> list[str] | None:
    """Parse one pipe-table row without treating escaped pipes as columns."""
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    body = stripped[1:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in body:
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        escaped = char == "\\" and not escaped
    cells.append("".join(current).strip())
    return cells


def _is_table_separator(cells: list[str] | None) -> bool:
    if not cells:
        return False
    return all(bool(cell) and set(cell) <= {"-", ":"} and "-" in cell for cell in cells)


def _clean_table_cell(value: str) -> str:
    """Keep RichMarkdown cells short and immune to common inline syntax."""
    value = re.sub(r"[`*_]", "", value)
    value = value.replace("\\|", "／").replace("|", "／")
    value = re.sub(r"\\([\\()[\]{}.!#+\-=])", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def _compact_table_block(block: list[str]) -> list[str]:
    """Canonicalize a table for phone width: max three stable columns."""
    parsed = [_table_cells(row) for row in block]
    if len(parsed) < 2 or not _is_table_separator(parsed[1]):
        return block
    width = len(parsed[0] or [])
    if width < 2:
        return block
    # Telegram mobile clients become hard to read beyond three columns. Keep
    # the first two decision columns and fold all remaining evidence/action
    # columns into one compact detail column.
    target_width = min(width, 3)
    compact: list[list[str]] = []
    for row in parsed:
        cells = list(row or [])
        if len(cells) < width:
            cells.extend([""] * (width - len(cells)))
        if target_width == 3 and width > 3:
            cells = cells[:2] + [" · ".join(cells[2:])]
        else:
            cells = cells[:target_width]
        compact.append([_clean_table_cell(cell) for cell in cells])
    compact[1] = [":---" if i == 0 else "---:" if i == target_width - 1 else "---" for i in range(target_width)]
    return ["| " + " | ".join(row) + " |" for row in compact]


def _normalize_rich_markdown_tables(text: str) -> str:
    """Canonicalize RichMarkdown tables for reliable Telegram mobile layout.

    RichMarkdown is the preferred transport, but Telegram clients differ in
    how they handle block boundaries, inline Markdown, and wide tables. This
    function therefore applies one conservative wire format: blank line before
    each table, no title glued to its header, max three columns, and one-line
    cells. If the rich endpoint is unavailable, callers can safely render this
    same canonical content as a monospaced fallback.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if cur.startswith("表") and nxt.startswith("|") and nxt.endswith("|"):
            i += 1
            continue
        cells = _table_cells(lines[i])
        if cells is not None and i + 1 < len(lines) and _is_table_separator(_table_cells(lines[i + 1])):
            block = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and _table_cells(lines[i]) is not None:
                block.append(lines[i])
                i += 1
            if out and out[-1].strip():
                out.append("")
            out.extend(_compact_table_block(block))
            if i < len(lines) and lines[i].strip():
                out.append("")
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _rich_fallback_text(text: str) -> str:
    """Convert canonical tables to readable labels for legacy Telegram clients.

    Telegram's ordinary sendMessage Markdown/HTML does not have a table
    primitive. This is deliberately a semantic fallback rather than a
    space-padded pseudo-table, so it remains readable on every client.
    """
    normalized = _normalize_rich_markdown_tables(text)
    lines = normalized.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        header = _table_cells(lines[i])
        separator = _table_cells(lines[i + 1]) if i + 1 < len(lines) else None
        if header is not None and _is_table_separator(separator):
            heads = header
            i += 2
            while i < len(lines):
                row = _table_cells(lines[i])
                if row is None:
                    break
                cells = list(row) + [""] * max(0, len(heads) - len(row))
                pairs = [
                    f"{heads[j]}：{cells[j]}"
                    for j in range(min(len(heads), len(cells)))
                    if cells[j]
                ]
                out.append(" · ".join(pairs))
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


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
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            desc = body.get("description", str(exc))
            parameters = body.get("parameters") or {}
            retry_after = parameters.get("retry_after", retry_after)
        except Exception:
            desc = str(exc)
        suffix = f" retry_after={retry_after}" if retry_after not in (None, "") else ""
        if exc.code == 429:
            try:
                _set_rate_limit(float(retry_after or 60))
            except (TypeError, ValueError):
                _set_rate_limit(60)
        return False, f"http {exc.code}: {desc}{suffix}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return False, f"network: {exc}"


def _post_message(target: str, text: str, token: str, parse_mode: str | None, timeout: int) -> tuple[bool, str]:
    remaining = _rate_limit_remaining()
    if remaining > 0:
        return False, f"local_rate_limit_cooldown={remaining:.1f}s"
    rich_requested = parse_mode in {"RichMarkdown", "rich_markdown"}
    rich_auto = parse_mode is None and _contains_markdown_table(text)
    # RichMarkdown selects sendRichMessage; it is never a sendMessage parse_mode.
    if parse_mode in {"RichMarkdown", "rich_markdown"}:
        parse_mode = None
    if rich_requested or rich_auto:
        rich_text = _normalize_rich_markdown_tables(text)
        payload = _build_base_payload(target)
        payload["rich_message"] = {"markdown": rich_text, "skip_entity_detection": False}
        ok, reason = _post_json("sendRichMessage", payload, token, timeout)
        if ok:
            return True, "rich_sent"
        # Older Bot API gateways may not expose sendRichMessage. Never send
        # raw pipes as the fallback: convert each row to labeled text so the
        # message remains readable on every Telegram client.
        fallback = _build_base_payload(target)
        fallback["text"] = _rich_fallback_text(text)
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
    append_text_line(PENDING_FILE, json.dumps(row, ensure_ascii=False))
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
    if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1":
        return False, "automated_delivery_disabled"
    if not configured_automated_target() or target != configured_automated_target():
        return False, "automated_delivery_target_mismatch"
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
            # Telegram 429 is the exception: honor its server-provided
            # Retry-After instead of hammering the endpoint or losing order.
            if reason.startswith("http 429") and attempt < retries - 1:
                match = re.search(r"retry_after=(\d+(?:\.\d+)?)", reason)
                delay = float(match.group(1)) if match else min(2 ** attempt, 8)
                time.sleep(min(max(0.0, delay), 60.0))
                continue
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
    图片发送必须经过与文字相同的显式外发闸门。
    """
    if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1":
        return False, "automated_delivery_disabled"
    configured_target = configured_automated_target()
    if not configured_target or target != configured_target:
        return False, "automated_delivery_target_mismatch"
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or token_from_env_file()
    if not token:
        reason = "missing TELEGRAM_BOT_TOKEN"
        if caption:
            append_pending(target, caption, reason, parse_mode)
        return False, reason
    remaining = _rate_limit_remaining()
    if remaining > 0:
        return False, f"local_rate_limit_cooldown={remaining:.1f}s"
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
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                err_body = json.loads(exc.read().decode("utf-8", errors="replace"))
                desc = err_body.get("description", str(exc))
                retry_after = (err_body.get("parameters") or {}).get("retry_after", retry_after)
            except Exception:
                desc = str(exc)
            last_reason = f"http {exc.code}: {desc}"
            if exc.code == 429:
                try:
                    delay = float(retry_after or 60)
                except (TypeError, ValueError):
                    delay = 60.0
                _set_rate_limit(delay)
                last_reason += f" retry_after={delay:g}"
                if attempt < retries - 1:
                    time.sleep(min(max(0.0, delay), 60.0))
                    continue
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
    # Hold the queue lock for the read/send/rewrite transaction. This is
    # intentionally conservative: a flush is infrequent, and losing a newly
    # appended delivery is worse than briefly delaying one producer.
    with _thread_lock(PENDING_FILE), _file_lock(PENDING_FILE):
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
        dead = []
        now = datetime.now(TZ)
        for row in rows[:limit]:
            target = str(row.get("target") or configured_automated_target() or "").strip()
            attempts = int(row.get("attempts") or 0)
            try:
                created = datetime.fromisoformat(str(row.get("created_at", "")).replace("Z", "+00:00"))
                age_expired = (now - created.astimezone(TZ)).total_seconds() > MAX_PENDING_AGE_SECONDS
            except (TypeError, ValueError, OverflowError):
                age_expired = False
            if not target:
                reason = "automated_delivery_target_missing"
                dead.append(_deadletter_row(row, reason))
                continue
            if attempts >= MAX_PENDING_ATTEMPTS or age_expired:
                reason = "pending_retry_limit_exceeded" if attempts >= MAX_PENDING_ATTEMPTS else "pending_expired"
                dead.append(_deadletter_row(row, reason))
                continue
            ok, reason = send_telegram_reliable(
                target,
                row.get("text", ""),
                parse_mode=row.get("parse_mode") or None,
                persist_on_fail=False,
            )
            if ok:
                sent += 1
            else:
                row["attempts"] = attempts + 1
                row["last_reason"] = reason
                if _is_permanent_delivery_failure(reason) or row["attempts"] >= MAX_PENDING_ATTEMPTS:
                    dead.append(_deadletter_row(row, reason))
                else:
                    kept.append(row)
        kept.extend(rows[limit:])
        for item in dead:
            _append_text_line_unlocked(DEADLETTER_FILE, json.dumps(item, ensure_ascii=False))
        if kept:
            _atomic_write_text_unlocked(
                PENDING_FILE,
                "\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + "\n",
            )
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

    夜间静默：23:00–08:00 不推送（后台计算仍跑，cron 视为正常完成），
    返回 (True, "silent_night") 避免 cron 误判失败 / pending 堆积。
    """
    if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1":
        return True, "automated_delivery_disabled"
    configured_target = configured_automated_target()
    if not configured_target:
        # Missing destination is configuration, not a transient failure. Do not
        # pollute the production retry queue with undeliverable messages.
        return False, "automated_delivery_target_missing"
    # Call sites may retain historical topics; unattended delivery follows the
    # one explicit configured target and never queues a topic mismatch.
    now_h = datetime.now(TZ).hour
    if now_h >= 23 or now_h < 8:
        return True, "silent_night"
    return send_telegram_reliable(configured_target, text, token=token, parse_mode="RichMarkdown", retries=3)


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