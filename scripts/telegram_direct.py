#!/usr/bin/env python3
"""
棠溪 · Telegram Bot API 直连推送 v1.0

替代旧的 subprocess → hermes_cli.main send 子进程方式。
直接 HTTP POST 到 Telegram Bot API，省去每条消息一个 Python 子进程的开销，
也避免子进程超时拖垮调用方。

用法:
    from telegram_direct import send_telegram_direct
    ok, reason = send_telegram_direct("telegram:-1003733144325:416", "消息")

token 来源优先级:
    1. 显式传入 token 参数
    2. 环境变量 TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error


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
    """构造 sendMessage 请求体。thread_id 为 None 时不带该键。"""
    payload = {"chat_id": chat_id, "text": text}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return payload


def send_telegram_direct(target: str, text: str, token: str | None = None,
                         parse_mode: str | None = None,
                         timeout: int = 10) -> tuple[bool, str]:
    """直连 Telegram Bot API 发送消息。

    返回 (成功, 原因)。任何网络/HTTP 异常都被吞掉返回 (False, reason)，绝不外抛。
    """
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return False, "missing TELEGRAM_BOT_TOKEN"

    chat_id, thread_id = parse_telegram_target(target)
    payload = build_payload(chat_id, thread_id, text, parse_mode=parse_mode)
    url = f"{API_BASE}/bot{token}/sendMessage"
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
                if body.get("ok"):
                    return True, "sent"
                return False, f"api error: {body.get('description', 'unknown')}"
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
                desc = err_body.get("description", str(e))
            except Exception:
                desc = str(e)
            # 4xx 客户端错误重试无意义，直接返回
            if 400 <= e.code < 500:
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
