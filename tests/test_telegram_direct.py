from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import telegram_direct as td


def test_parse_target_with_thread():
    chat_id, thread_id = td.parse_telegram_target("telegram:-1003733144325:416")
    assert chat_id == "-1003733144325"
    assert thread_id == 416


def test_parse_target_without_thread():
    chat_id, thread_id = td.parse_telegram_target("telegram:-1003733144325")
    assert chat_id == "-1003733144325"
    assert thread_id is None


def test_parse_target_bare_chat_id():
    chat_id, thread_id = td.parse_telegram_target("-1003733144325:416")
    assert chat_id == "-1003733144325"
    assert thread_id == 416


def test_build_payload_includes_thread():
    payload = td.build_payload("-1003733144325", 416, "hello")
    assert payload["chat_id"] == "-1003733144325"
    assert payload["message_thread_id"] == 416
    assert payload["text"] == "hello"


def test_build_payload_no_thread_omits_key():
    payload = td.build_payload("-1003733144325", None, "hi")
    assert "message_thread_id" not in payload
    assert payload["text"] == "hi"


def test_send_telegram_direct_handles_missing_token(monkeypatch):
    # 无 token 时返回 False，不抛异常
    # v7.6: 还需屏蔽 .env 文件兜底，否则真实环境会读到 token
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(td, "_token_from_env_file", lambda: None)
    ok, reason = td.send_telegram_direct("telegram:-1003733144325:416", "test", token=None)
    assert ok is False
    assert "token" in reason.lower()
