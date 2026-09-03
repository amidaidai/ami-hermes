"""Small atomic JSON publication helpers used by runtime state files."""
from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Callable, Iterator
from typing import Any


_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve()).casefold()
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Serialize JSON updates across threads and processes."""
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write_json_unlocked(
    path: str | Path,
    payload: Any,
    *,
    indent: int | None = 2,
) -> Path:
    """Publish a complete JSON document with an atomic replace.

    Readers either see the previous complete file or the new complete file;
    they never observe a partially-written JSON document.  The temporary file
    lives beside the target so ``os.replace`` remains atomic on Windows.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(target))
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    indent: int | None = 2,
) -> Path:
    """Publish JSON under the shared per-path cross-process lock."""
    target = Path(path)
    with _thread_lock(target), _file_lock(target):
        return _atomic_write_json_unlocked(target, payload, indent=indent)


def _atomic_write_text_unlocked(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Publish text without acquiring a caller-held lock."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(target))
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Publish text under the shared per-path cross-process lock."""
    target = Path(path)
    with _thread_lock(target), _file_lock(target):
        return _atomic_write_text_unlocked(target, text, encoding=encoding)


def _append_text_line_unlocked(path: str | Path, line: str, *, encoding: str = "utf-8") -> Path:
    """Append one line when the caller already owns the path lock."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding=encoding, newline="\n") as handle:
        handle.write(line.rstrip("\n") + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return target


def append_text_line(path: str | Path, line: str, *, encoding: str = "utf-8") -> Path:
    """Append one line while serializing writers across processes."""
    target = Path(path)
    with _thread_lock(target), _file_lock(target):
        return _append_text_line_unlocked(target, line, encoding=encoding)


def atomic_update_json(
    path: str | Path,
    updater: Callable[[Any], Any],
    *,
    default: Any,
    indent: int | None = 2,
) -> Any:
    """Read, update under a lock, and atomically publish JSON."""
    target = Path(path)
    lock = _thread_lock(target)
    with lock, _file_lock(target):
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            current = default
        updated = updater(current)
        _atomic_write_json_unlocked(target, updated, indent=indent)
        return updated
