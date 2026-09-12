#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已退役看门狗兼容层。

历史职责：心跳失联时杀旧「行情守望.py」再 Popen 拉起，并可能推 TG:846。
现行监控权威是 keylevel_guard.py + btc_keylevel_guard_watchdog.py。
本文件保留路径以免旧 cron/文档引用 404；运行只打印退役横幅，不拉进程、不推送。
"""
from __future__ import annotations

import sys

RETIRED_AUTHORITY = "keylevel_guard.py"


def main() -> int:
    print(f"已退役·生产权威为 {RETIRED_AUTHORITY}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
