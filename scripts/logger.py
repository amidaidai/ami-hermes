#!/usr/bin/env python3
"""
棠溪 · 统一日志模块 v1.0
借鉴: NautilusTrader(结构化日志) + Freqtrade(logging最佳实践)
功能: RotatingFileHandler + 统一格式 + 模块级logger
用法:
    from logger import get_logger
    log = get_logger(__name__)
    log.info("消息")
    log.error("错误", exc_info=True)
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
LOG_DIR = ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 格式: [2026-06-18 15:30:00] [INFO] [module_name] 消息
_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root():
    global _configured
    if _configured:
        return
    root = logging.getLogger("tangxi")
    root.setLevel(logging.DEBUG)
    # 文件handler: 5MB × 3份轮转
    fh = RotatingFileHandler(
        LOG_DIR / "trading.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    root.addHandler(fh)
    # 控制台handler (INFO级别)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    root.addHandler(ch)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取模块级logger"""
    _configure_root()
    if not name.startswith("tangxi."):
        name = f"tangxi.{name}"
    return logging.getLogger(name)
