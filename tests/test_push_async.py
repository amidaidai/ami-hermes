from __future__ import annotations
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
watch_path = ROOT / "scripts" / "行情守望.py"
spec = importlib.util.spec_from_file_location("watch_push_async", watch_path)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def test_push_returns_immediately_even_if_send_blocks(monkeypatch):
    """push() must not block the main loop. Even if the underlying send
    takes 8 seconds, push() should return in well under 1 second by
    handing the work to a background queue worker."""
    delays = []

    def slow_send(args, **kwargs):
        # Simulate a hung Telegram send. The OLD synchronous push would
        # block here for timeout=10 x retries. The async push must NOT.
        time.sleep(8)
        delays.append(time.time())

        class R:
            returncode = 0
            stdout = b""
            stderr = b""
        return R()

    monkeypatch.setattr(watch.subprocess, "run", slow_send)

    t0 = time.time()
    result = watch.push("test message · 紧急")
    elapsed = time.time() - t0

    # push must return fast (queued), not wait for the 8s send
    assert elapsed < 1.0, f"push blocked {elapsed:.2f}s — main loop would stall"
    # contract: returns True meaning "accepted/queued"
    assert result is True


def test_push_subprocess_timeout_is_caught(monkeypatch):
    """A subprocess.TimeoutExpired from a hung send must NOT bubble up
    and crash/stall the caller. The old code caught requests.Timeout,
    which never matches subprocess timeouts."""
    def timing_out_send(args, **kwargs):
        raise watch.subprocess.TimeoutExpired(cmd="send", timeout=10)

    monkeypatch.setattr(watch.subprocess, "run", timing_out_send)

    # Must not raise. Drain the worker to make sure the exception inside
    # the worker thread doesn't escape either.
    result = watch.push("timeout test · 触发")
    assert result is True
    # give the worker a moment to process and swallow the timeout
    watch.drain_push_queue(timeout=12)


def test_drain_push_queue_exists():
    """A helper to flush the queue (used on shutdown / in tests) must exist."""
    assert hasattr(watch, "drain_push_queue")
