#!/usr/bin/env python
"""Copy a UTF-8 Pine source file to the Windows Unicode clipboard."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    text = args.source.read_text(encoding="utf-8")

    cf_unicode_text = 13
    gmem_moveable = 0x0002
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        raise OSError("OpenClipboard failed")
    handle = None
    try:
        user32.EmptyClipboard()
        payload = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(gmem_moveable, len(payload))
        if not handle:
            raise MemoryError("GlobalAlloc failed")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise MemoryError("GlobalLock failed")
        ctypes.memmove(pointer, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(cf_unicode_text, handle):
            raise OSError("SetClipboardData failed")
        handle = None  # Clipboard owns the allocation after success.
    finally:
        user32.CloseClipboard()

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    print(f"chars={len(normalized)} lines={len(normalized.splitlines())} sha256={digest}")


if __name__ == "__main__":
    main()
