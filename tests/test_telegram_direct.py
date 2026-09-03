from __future__ import annotations
import json
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


def test_build_payload_rich_markdown_uses_rich_message():
    payload = td.build_payload("-1003733144325", 416, "| A | B |\n|---|---|\n| 1 | 2 |", parse_mode="RichMarkdown")
    assert payload["chat_id"] == "-1003733144325"
    assert payload["message_thread_id"] == 416
    assert "text" not in payload
    assert payload["rich_message"] == {
        "markdown": "| A | B |\n| :--- | ---: |\n| 1 | 2 |",
        "skip_entity_detection": False,
    }


def test_reliable_auto_routes_markdown_table_to_send_rich(monkeypatch):
    import telegram_reliable as tr  # type: ignore[import-not-found]

    calls = []

    def fake_post_json(method, payload, token, timeout):
        calls.append((method, payload))
        return True, "sent"

    monkeypatch.setattr(tr, "_post_json", fake_post_json)
    ok, reason = tr._post_message(
        "telegram:-1003733144325:416",
        "表1\n| A | B |\n|:--|:--|\n| 1 | 2 |",
        "token",
        None,
        10,
    )
    assert ok is True
    assert reason == "rich_sent"
    assert calls[0][0] == "sendRichMessage"
    normalized = calls[0][1]["rich_message"]["markdown"]
    assert normalized.startswith("| A | B |")
    assert "表1" not in normalized


def test_reliable_strips_table_title_lines_for_rich_markdown():
    import telegram_reliable as tr  # type: ignore[import-not-found]

    text = "首行\n\n表1 · 行情全景\n| A | B |\n|:--|:--|\n| 1 | 2 |"
    normalized = tr._normalize_rich_markdown_tables(text)
    assert "表1 · 行情全景" not in normalized
    assert "| A | B |" in normalized


def test_reliable_compacts_wide_tables_and_cleans_inline_markdown():
    import telegram_reliable as tr  # type: ignore[import-not-found]

    text = (
        "| 优先级 | 条件 | 动作 | R:R |\n"
        "|:---|:---|---|---:|\n"
        "| ⭐主推 | `77,369`确认 | 多｜损 77,100 | 1:2.4 |"
    )
    normalized = tr._normalize_rich_markdown_tables(text)
    rows = [line for line in normalized.splitlines() if line.startswith("|")]
    assert len(rows) == 3
    assert all(len(tr._table_cells(row) or []) == 3 for row in rows)
    assert "⭐主推" in rows[2]
    assert "`" not in normalized
    assert "1:2.4" in normalized


def test_reliable_preserves_non_table_pipe_text():
    import telegram_reliable as tr  # type: ignore[import-not-found]

    text = "路径 A | B\n下一行"
    assert tr._normalize_rich_markdown_tables(text) == text


def test_rich_fallback_never_sends_raw_pipe_table():
    import telegram_reliable as tr  # type: ignore[import-not-found]

    text = "| 指标 | 读数 | 状态 |\n|:---|:---|:---|\n| OI | 107,616 | 持平 |"
    fallback = tr._rich_fallback_text(text)
    assert "|" not in fallback
    assert "指标：OI" in fallback
    assert "读数：107,616" in fallback


def test_send_telegram_direct_fallback_rich_uses_send_rich(monkeypatch):
    # Force legacy fallback path (no telegram_reliable import) and verify endpoint.
    monkeypatch.setattr(td, "_reliable_send", None)
    monkeypatch.setattr(td, "_token_from_env_file", lambda: "token")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TANGXI_ENABLE_AUTOMATED_TG", "1")
    monkeypatch.setenv("TANGXI_AUTOMATED_TG_TARGET", "telegram:-1003733144325:416")
    seen = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, timeout=10):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResp()

    monkeypatch.setattr(td.urllib.request, "urlopen", fake_urlopen)
    ok, reason = td.send_telegram_direct(
        "telegram:-1003733144325:416",
        "| A | B |\n|---|---|\n| 1 | 2 |",
        parse_mode="RichMarkdown",
    )
    assert ok is True
    assert reason == "sent"
    assert seen["url"].endswith("/sendRichMessage")
    assert "rich_message" in seen["body"]


def test_send_telegram_direct_handles_missing_token(monkeypatch):
    # 无 token 时返回 False，不抛异常
    # v7.6: 还需屏蔽 .env 文件兜底，否则真实环境会读到 token
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TANGXI_ENABLE_AUTOMATED_TG", raising=False)
    monkeypatch.delenv("TANGXI_AUTOMATED_TG_TARGET", raising=False)
    monkeypatch.setattr(td, "_token_from_env_file", lambda: None)
    ok, reason = td.send_telegram_direct("telegram:-1003733144325:416", "test", token=None)
    assert ok is False
    assert reason == "automated_delivery_disabled"
