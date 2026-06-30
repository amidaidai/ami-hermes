#!/usr/bin/env python3
"""
交易执行桥接器 v1.0
五层架构执行层 — 连接 pipeline_integration → trading_system
将信号转换为可追踪的交易事件，写入 trade_events.jsonl
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")
os.makedirs(DATA_DIR, exist_ok=True)

TRADE_EVENTS = os.path.join(DATA_DIR, "trade_events.jsonl")


def log_event(event_type: str, symbol: str, details: dict):
    """写入交易事件日志"""
    event = {
        "ts": datetime.now(TZ).isoformat(),
        "type": event_type,
        "symbol": symbol,
        **details,
    }
    with open(TRADE_EVENTS, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def bridge_signal_to_execution():
    """将最新分析信号桥接到执行层"""
    # 读取最新信号
    signals_file = os.path.join(DATA_DIR, "btc_signals.json")
    try:
        with open(signals_file) as f:
            signals = json.load(f)
    except FileNotFoundError:
        return {"status": "no_signal", "msg": "无信号文件"}
    
    # 读取因子
    factors_file = os.path.join(DATA_DIR, "qlib_factors.json")
    factors = {}
    try:
        with open(factors_file) as f:
            factors = json.load(f).get("factors", {})
    except FileNotFoundError:
        pass
    
    # 读取风控状态
    protection_file = os.path.join(DATA_DIR, "protections_state.json")
    protections = {}
    try:
        with open(protection_file) as f:
            protections = json.load(f)
    except FileNotFoundError:
        pass
    
    price = signals.get("price", 0)
    stage = signals.get("stage", "idle")
    score = signals.get("scoring_total", 0)
    factor_score = factors.get("SIGNAL_SCORE", 0)
    factor_bias = factors.get("SIGNAL_BIAS", "neutral")
    
    # 判断是否值得记录
    is_notable = (
        stage == "entry_ready" or
        abs(factor_score) >= 3 or
        score >= 12 or
        protections.get("breach", False)
    )
    
    if not is_notable:
        return {"status": "quiet", "stage": stage, "price": price}
    
    # 记录事件
    details = {
        "price": price,
        "stage": stage,
        "score": score,
        "factor_score": factor_score,
        "factor_bias": factor_bias,
        "dmi_adx": signals.get("dmi", {}).get("adx", 0),
        "protections": protections.get("active", []),
    }
    
    log_event("signal_check", "BTCUSDT", details)
    
    # 如果有entry_ready信号，记录入场事件
    if stage == "entry_ready":
        direction = signals.get("direction", "wait")
        entry_price = signals.get("entry_price", price)
        log_event("entry_signal", "BTCUSDT", {
            "direction": direction,
            "entry_price": entry_price,
            "score": score,
            "factor_score": factor_score,
        })
    
    return {
        "status": "logged",
        "stage": stage,
        "price": price,
        "factor_bias": factor_bias,
    }


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    result = bridge_signal_to_execution()
    
    if result["status"] in {"no_signal", "quiet"}:
        # 静默：无信号/普通状态只落盘数据，不生成 cron 输出。
        return 0
    else:
        print(f"执行桥 {ts} | {result['stage']} | 因子{result.get('factor_bias','?')} | 已记录trade_events.jsonl")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
