#!/usr/bin/env python3
"""
棠溪 · Telegram Bot API 直连推送 v1.0

替代旧的 subprocess → hermes_cli.main send 子进程方式。
直接 HTTP POST 到 Telegram Bot API，省去每条消息一个 Python 子进程的开销，
也避免子进程超时拖垮调用方。

用法:
    from telegram_direct import send_telegram_direct
    ok, reason = send_telegram_direct("telegram:-1003733144325:416", "消息")

v1.1：优先委托 `telegram_reliable.send_telegram_reliable()`，失败落盘到
`D:/Hermes agent/data/pending_telegram.jsonl`，兼容历史调用。

token 来源优先级:
    1. 显式传入 token 参数
    2. 环境变量 TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import urllib.request
import urllib.error

try:
    from telegram_reliable import (
        send_telegram_reliable as _reliable_send,
        _normalize_rich_markdown_tables,
        _rich_fallback_text,
    )
except Exception:  # noqa: BLE001 - standalone fallback keeps old behavior usable
    _reliable_send = None

    def _normalize_rich_markdown_tables(text: str) -> str:
        return text

    def _rich_fallback_text(text: str) -> str:
        # Without the reliable module there is no table parser available; still
        # avoid leaking raw pipe syntax through the ordinary sendMessage path.
        return text.replace("|", "／")


def _local_rate_limit_remaining() -> float:
    try:
        from telegram_reliable import _rate_limit_remaining
        return _rate_limit_remaining()
    except Exception:
        return 0.0


def _note_rate_limit(seconds: float) -> None:
    try:
        from telegram_reliable import _set_rate_limit
        _set_rate_limit(seconds)
    except Exception:
        pass


def _canonical_rich_text(text: str) -> str:
    """Use the same mobile-safe table wire format as the reliable sender."""
    return _normalize_rich_markdown_tables(text)


def _fallback_plain_text(text: str) -> str:
    """Use semantic rows when the standalone rich endpoint is unavailable."""
    return _rich_fallback_text(text)


def _retry_after_from_error(error_body: dict) -> float:
    try:
        return float((error_body.get("parameters") or {}).get("retry_after") or 60)
    except (TypeError, ValueError):
        return 60.0


API_BASE = "https://api.telegram.org"


def parse_telegram_target(target: str) -> tuple[str, int | None]:
    """解析 'telegram:<chat_id>:<thread_id>' / 'telegram:<chat_id>' / '<chat_id>:<thread_id>'。

    返回 (chat_id, thread_id)。thread_id 可能为 None。
    chat_id 可能为负数（群组），保留字符串形式。
    """
    s = target.strip()
    if s.startswith("telegram:"):
        s = s[len("telegram:"):]
    # chat_id 可能以 '-' 开头（群组/超级群），thread_id 是末尾的纯数字段
    parts = s.split(":")
    if len(parts) >= 2 and parts[-1].lstrip("-").isdigit() and len(parts) > 1:
        # 末段是 thread_id，前面拼回 chat_id
        thread_id = int(parts[-1])
        chat_id = ":".join(parts[:-1])
        # 若前段为空（只有一段被当成 thread），回退
        if chat_id:
            return chat_id, thread_id
    return s, None


def build_payload(chat_id: str, thread_id: int | None, text: str,
                  parse_mode: str | None = None) -> dict:
    """构造 sendMessage/sendRichMessage 请求体。thread_id 为 None 时不带该键。"""
    payload: dict[str, object] = {"chat_id": chat_id}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode in {"RichMarkdown", "rich_markdown"}:
        payload["rich_message"] = {
            "markdown": _canonical_rich_text(text),
            "skip_entity_detection": False,
        }
    else:
        payload["text"] = text
        if parse_mode:
            payload["parse_mode"] = parse_mode
    return payload


_ENV_TOKEN_CACHE: str | None = None


def _token_from_env_file() -> str | None:
    """从 Hermes .env 文件兜底读取 TELEGRAM_BOT_TOKEN。

    watchdog 用 subprocess.Popen 重启行情守望时不继承父进程环境变量，
    导致子进程 os.environ 里没有 token → 推送报 missing TELEGRAM_BOT_TOKEN。
    这里直接读 .env 文件保证无论谁拉起进程都能拿到 token。结果缓存避免反复 IO。
    """
    global _ENV_TOKEN_CACHE
    if _ENV_TOKEN_CACHE is not None:
        return _ENV_TOKEN_CACHE or None
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\hermes\.env"),
        os.path.expanduser("~/AppData/Local/hermes/.env"),
        os.path.expanduser("~/.hermes/.env"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            _ENV_TOKEN_CACHE = val
                            return val
        except (OSError, UnicodeDecodeError):
            continue
    _ENV_TOKEN_CACHE = ""
    return None


def send_telegram_direct(target: str, text: str, token: str | None = None,
                         parse_mode: str | None = None,
                         timeout: int = 10) -> tuple[bool, str]:
    """直连 Telegram Bot API 发送消息。

    返回 (成功, 原因)。任何网络/HTTP 异常都被吞掉返回 (False, reason)，绝不外抛。

    v9.8：默认 parse_mode 改为 RichMarkdown（真表格渲染）。调用方未显式指定时，
    表格类消息走 sendRichMessage 而非纯文本退化。
    """
    # Every direct/legacy entry point is closed by default. Unattended delivery
    # must explicitly opt in and use the configured target; this also protects
    # the standalone fallback when telegram_reliable cannot be imported.
    if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1":
        return False, "automated_delivery_disabled"
    configured_target = os.environ.get("TANGXI_AUTOMATED_TG_TARGET", "").strip()
    if not configured_target.startswith("telegram:") or target != configured_target:
        return False, "automated_delivery_target_mismatch"
    if parse_mode is None:
        parse_mode = "RichMarkdown"
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN") or _token_from_env_file()
    if not token:
        return False, "missing TELEGRAM_BOT_TOKEN"

    if _reliable_send is not None:
        return _reliable_send(
            target,
            text,
            token=token,
            parse_mode=parse_mode,
            timeout=timeout,
            retries=3,
            persist_on_fail=True,
        )

    remaining = _local_rate_limit_remaining()
    if remaining > 0:
        return False, f"local_rate_limit_cooldown={remaining:.1f}s"

    chat_id, thread_id = parse_telegram_target(target)
    rich_requested = parse_mode in {"RichMarkdown", "rich_markdown"}
    payload = build_payload(chat_id, thread_id, text, parse_mode=parse_mode)
    method = "sendRichMessage" if rich_requested else "sendMessage"
    url = f"{API_BASE}/bot{token}/{method}"

    for attempt in range(3):
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
                if body.get("ok"):
                    return True, "sent"
                reason = f"api error: {body.get('description', 'unknown')}"
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
                desc = err_body.get("description", str(e))
            except Exception:
                err_body = {}
                desc = str(e)
            if e.code == 429:
                delay = _retry_after_from_error(err_body)
                _note_rate_limit(delay)
                return False, f"http 429: {desc} retry_after={delay:g}"
            if 400 <= e.code < 500:
                # RichMarkdown is a separate endpoint. If that endpoint is
                # unavailable, retry once as readable labeled text instead of
                # ever sending raw pipe-table syntax through sendMessage.
                if rich_requested:
                    payload = {"chat_id": chat_id}
                    if thread_id is not None:
                        payload["message_thread_id"] = thread_id
                    payload["text"] = _fallback_plain_text(text)
                    method = "sendMessage"
                    url = f"{API_BASE}/bot{token}/{method}"
                    rich_requested = False
                    continue
                return False, f"http {e.code}: {desc}"
            reason = f"http {e.code}: {desc}"
        except (urllib.error.URLError, OSError, ValueError) as e:
            reason = f"network: {e}"
        if attempt < 2:
            import time
            time.sleep(1)
    return False, reason


if __name__ == "__main__":
    import sys
    tgt = sys.argv[1] if len(sys.argv) > 1 else "telegram:-1003733144325:416"
    msg = sys.argv[2] if len(sys.argv) > 2 else "telegram_direct 自测"
    print(send_telegram_direct(tgt, msg))
