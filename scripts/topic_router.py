#!/usr/bin/env python3
"""
话题路由器 v1.0 — 按品种自动路由Telegram话题

映射（待棠溪确认后更新）:
  BTCUSDT   → topic 416 (当前分析主话题·暂用)
  XAUUSD    → topic 416 (暂用)
  山寨币     → topic 416 (暂用)

用法:
  from topic_router import route_send
  route_send("BTCUSDT", "BTC分析卡内容...", screenshot_path=None)
"""

import subprocess, sys, os, json
from pathlib import Path

ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
GROUP_ID = "-1003733144325"

# 话题映射 — 待棠溪确认后更新
TOPIC_MAP = {
    "BTCUSDT": 386,     # BTC专属话题
    "XAUUSD": 385,      # XAU黄金专属话题
    "ETHUSDT": 416,     # 山寨币默认
    "SOLUSDT": 416,
    "default": 416,
}


def get_topic(symbol: str) -> int:
    """获取品种对应的Telegram话题ID。"""
    return TOPIC_MAP.get(symbol, TOPIC_MAP["default"])


def get_target(symbol: str) -> str:
    """生成 send_message target 字符串。"""
    topic = get_topic(symbol)
    return f"telegram:{GROUP_ID}:{topic}"


def route_send(symbol: str, message: str, screenshot_path: str = None) -> bool:
    """
    按品种路由发送消息到Telegram。
    
    Args:
        symbol: BTCUSDT·XAUUSD·ETHUSDT等
        message: 消息正文
        screenshot_path: 可选截图路径
    
    Returns: 是否成功
    """
    target = get_target(symbol)
    
    # 构建完整消息
    full_msg = message
    if screenshot_path and Path(screenshot_path).exists():
        full_msg += f"\nMEDIA:{screenshot_path}"
    
    # 调用 Hermes send_message
    try:
        cp = subprocess.run(
            ["hermes", "send-message", target, full_msg],
            capture_output=True, text=True, timeout=15,
            cwd=str(ROOT),
        )
        return cp.returncode == 0
    except Exception:
        return False


def update_topic_map(btc_topic: int, xau_topic: int, alt_topic: int):
    """更新话题映射（持久化到文件）。"""
    TOPIC_MAP["BTCUSDT"] = btc_topic
    TOPIC_MAP["XAUUSD"] = xau_topic
    TOPIC_MAP["default"] = alt_topic
    
    # 持久化
    config = {
        "group_id": GROUP_ID,
        "topics": {
            "BTC": btc_topic,
            "XAU": xau_topic,
            "altcoins": alt_topic,
        },
        "updated": __import__("datetime").datetime.now().isoformat(),
    }
    config_file = ROOT / "data" / "topic_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    
    return config
