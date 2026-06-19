from __future__ import annotations
import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# 双保险：进程级关闭真实外发。即便 stub 漏掉某条通道，
# _send_one 顶部的 NO_SEND 开关也会拦下，绝不漏发真实消息到 Telegram/Discord。
os.environ.setdefault("HANGQING_NO_SEND", "1")

watch_path = ROOT / "scripts" / "行情守望.py"
spec = importlib.util.spec_from_file_location("watch_push_async", watch_path)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def test_push_returns_immediately_even_if_send_blocks(monkeypatch):
    """push() 绝不能阻塞主循环。即便底层发送要 8 秒，push() 也应在 1 秒内返回，
    把活儿交给后台队列 worker。

    注意：stub 的是 _send_one（所有发送的唯一咽喉），不是 subprocess.run。
    旧测试只 patch subprocess.run，但 Telegram 走 telegram_direct 直连 HTTP，
    patch 形同虚设，worker 会把真实消息漏发出去。
    """
    sent = []

    def slow_send(target, msg):
        # 模拟一个卡死的发送：旧的同步 push 会在这里阻塞 timeout×retries，
        # 异步 push 绝不能阻塞。
        time.sleep(8)
        sent.append((target, msg))
        return True

    monkeypatch.setattr(watch, "_send_one", slow_send)

    t0 = time.time()
    result = watch.push("test message · 紧急")
    elapsed = time.time() - t0

    # push 必须快速返回（入队），而不是等 8 秒发送
    assert elapsed < 1.0, f"push 阻塞了 {elapsed:.2f}s — 主循环会卡死"
    # 契约：返回 True 表示已接受/入队
    assert result is True

    # 在 monkeypatch 还原前把队列排空，确保 worker 用的是 stub 而非真实发送。
    watch.drain_push_queue(timeout=20)


def test_push_subprocess_timeout_is_caught(monkeypatch):
    """卡死发送抛出的超时异常绝不能冒泡，否则会拖垮调用方。
    在 worker 线程内必须被吞掉。"""
    def timing_out_send(target, msg):
        raise watch.subprocess.TimeoutExpired(cmd="send", timeout=10)

    monkeypatch.setattr(watch, "_send_one", timing_out_send)

    # 不得抛异常。排空队列以确认 worker 线程内的异常也没逃逸。
    result = watch.push("timeout test · 触发")
    assert result is True
    watch.drain_push_queue(timeout=12)


def test_drain_push_queue_exists():
    """排空队列的辅助函数（关停/测试用）必须存在。"""
    assert hasattr(watch, "drain_push_queue")


def test_no_send_switch_blocks_real_send(monkeypatch):
    """HANGQING_NO_SEND=1 时，_send_one 必须在触达任何真实通道前短路返回 True，
    且不调用 telegram_direct / subprocess。"""
    monkeypatch.setenv("HANGQING_NO_SEND", "1")

    called = {"sub": False}

    def tripwire(*a, **k):
        called["sub"] = True
        class R:
            returncode = 0
            stdout = b""
            stderr = b""
        return R()

    monkeypatch.setattr(watch.subprocess, "run", tripwire)
    ok = watch._send_one("telegram:-1003733144325:416", "should not send")
    assert ok is True
    assert called["sub"] is False, "NO_SEND 开启时不应触达 subprocess 发送"
