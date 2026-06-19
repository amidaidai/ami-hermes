"""pytest 全局配置：在收集任何用例前生效。

安全开关 HANGQING_NO_SEND=1 —— 让行情守望的发送咽喉一律不外发真实消息。
即便将来新增推送通道、或某条用例忘了桩掉发送，也绝不会把测试消息
漏发到 Telegram/Discord。用 setdefault，本地若已显式设别的值则尊重之。
"""
import os

os.environ.setdefault("HANGQING_NO_SEND", "1")
