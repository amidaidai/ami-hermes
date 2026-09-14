"""pytest 全局配置：在收集任何用例前生效。

安全开关 HANGQING_NO_SEND=1 —— 让行情守望的发送咽喉一律不外发真实消息。
即便将来新增推送通道、或某条用例忘了桩掉发送，也绝不会把测试消息
漏发到 Telegram/Discord。用 setdefault，本地若已显式设别的值则尊重之。

副作用隔离（2026-09-14）：`xau_tv_sync._audit_marker` 会往
`data/xau_tv_sync_runs.jsonl` 追加生产取证行；任何触到 let-路/发布路径的用例
（lease 让路、main() 降级等）都必须写进 tmp_path，绝不污染生产取证文件。
"""
import os

import pytest

os.environ.setdefault("HANGQING_NO_SEND", "1")


@pytest.fixture(autouse=True)
def _isolate_xau_sync_audit_marker(tmp_path, monkeypatch):
    """任何用例的 xau_tv_sync 取证标记都改写到 tmp_path（缺模块时跳过）。"""
    try:
        import xau_tv_sync
    except Exception:  # noqa: BLE001
        return
    monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE", tmp_path / "xau_tv_sync_runs.jsonl")
