#!/usr/bin/env python3
"""
棠溪 · 硬止损执行模块 v1.0
从"建议型"风控 → "执行型"风控

功能:
  1. 分析卡→止损单: 根据操作段入场/止损/仓位 → Binance挂STOP_MARKET止损
  2. 止盈挂单: 可选LIMIT止盈
  3. 仓位计算: 基于账户余额+杠杆+风险金额

用法:
  from hard_stop import execute_stop_loss
  result = execute_stop_loss(symbol="BTCUSDT", direction="short",
                              entry=64308, stop=64510, risk_usd=2.03,
                              leverage=100, account_balance=67.52)
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, sys, os, subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"


def position_size(entry: float, stop: float, risk_usd: float,
                   leverage: int = 100, account_balance: float = 67.52,
                   atr_value: float = None) -> dict:
    """
    仓位计算 · 基于风险金额 + ATR自适应（v2.0社区增强）
    
    Returns:
        {
            "quantity": float,        # 合约张数
            "notional": float,        # 名义价值
            "margin": float,          # 保证金
            "risk_pct": float,        # 风险占本金%
            "liquidation_approx": float,  # 预估强平价
            "atr_clamped": bool,      # ATR是否修正了止损
            "original_stop": float,   # 原始结构止损
        }
    """
    if entry <= 0 or stop <= 0 or risk_usd <= 0:
        return {"error": "无效参数"}
    
    distance = abs(entry - stop)
    original_stop = stop
    atr_clamped = False
    
    # ATR夹层修正：止损必须在 0.5×ATR ~ 2.5×ATR 之间
    if atr_value and atr_value > 0:
        min_dist = 0.5 * atr_value
        max_dist = 2.5 * atr_value
        if distance < min_dist:
            # 噪音止损 → 推远到0.5×ATR
            if stop < entry:  # long stop below entry
                stop = entry - min_dist
            else:  # short stop above entry
                stop = entry + min_dist
            distance = abs(entry - stop)
            atr_clamped = True
        elif distance > max_dist:
            # 风险过大 → 拉近到2.5×ATR
            if stop < entry:
                stop = entry - max_dist
            else:
                stop = entry + max_dist
            distance = abs(entry - stop)
            atr_clamped = True
    
    if distance <= 0:
        return {"error": "入场=止损，无距离"}
    
    # 每张合约价值
    risk_per_contract = distance
    
    # 张数 = 风险金额 / 每张风险
    quantity = risk_usd / risk_per_contract
    
    # 名义价值
    notional = quantity * entry
    
    # 保证金 = 名义价值 / 杠杆
    margin = notional / leverage
    
    # 风险占本金%
    risk_pct = (risk_usd / account_balance) * 100 if account_balance > 0 else 999
    
    # 预估强平价（简化：单方向100x）
    if entry > stop:  # 做空
        liquidation_approx = entry * (1 + 0.9 / leverage)
    else:  # 做多
        liquidation_approx = entry * (1 - 0.9 / leverage)
    
    # Binance 精度 (BTCUSDT: 3 decimals)
    qty_rounded = round(quantity, 3)
    if qty_rounded < 0.001:
        qty_rounded = 0.001  # 最小0.001 BTC
    
    return {
        "quantity": qty_rounded,
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "risk_pct": round(risk_pct, 2),
        "risk_per_contract": round(risk_per_contract, 1),
        "liquidation_approx": round(liquidation_approx, 1),
        "atr_clamped": atr_clamped,
        "original_stop": original_stop,
        "final_stop": stop,
    }


def execute_stop_loss(symbol: str, direction: str, entry: float,
                       stop: float, risk_usd: float = 3.0,
                       leverage: int = 100, account_balance: float = 67.52,
                       target1: Optional[float] = None,
                       target2: Optional[float] = None,
                       dry_run: bool = True) -> dict:
    """
    执行硬止损挂单
    
    流程:
      1. 计算仓位
      2. 开仓 (MARKET/LIMIT)
      3. 挂止损单 (STOP_MARKET)
      4. 可选止盈单 (LIMIT)
    
    Args:
        symbol: 交易对
        direction: "long" / "short"
        entry: 入场价
        stop: 止损价
        risk_usd: 风险金额
        leverage: 杠杆倍数
        account_balance: 账户余额
        target1/target2: 止盈目标
        dry_run: True=仅模拟不执行
    
    Returns:
        {
            "success": bool,
            "orders": [...],
            "position": {...},
            "log_entry": {...},
        }
    """
    # 1. 仓位计算
    pos = position_size(entry, stop, risk_usd, leverage, account_balance)
    if "error" in pos:
        return {"success": False, "error": pos["error"]}
    
    result = {
        "success": False,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "position": pos,
        "orders": [],
        "dry_run": dry_run,
    }
    
    if dry_run:
        # 模拟模式
        result["success"] = True
        result["orders"] = [
            {"type": "ENTRY", "side": "SELL" if direction == "short" else "BUY",
             "price": entry, "quantity": pos["quantity"], "status": "DRY_RUN"},
            {"type": "STOP_LOSS", "side": "BUY" if direction == "short" else "SELL",
             "stopPrice": stop, "quantity": pos["quantity"], "status": "DRY_RUN",
             "reduceOnly": True},
        ]
        if target1:
            result["orders"].append({
                "type": "TAKE_PROFIT_1", "side": "BUY" if direction == "short" else "SELL",
                "price": target1, "quantity": pos["quantity"] * 0.5, "status": "DRY_RUN",
                "reduceOnly": True,
            })
        if target2:
            result["orders"].append({
                "type": "TAKE_PROFIT_2", "side": "BUY" if direction == "short" else "SELL",
                "price": target2, "quantity": pos["quantity"] * 0.5, "status": "DRY_RUN",
                "reduceOnly": True,
            })
        return result
    
    # 2. 实盘执行（通过 Hermes MCP）
    # 注意：需要 Hermes 已加载 create_order MCP 工具
    print(f"⚠ 实盘模式下单: {symbol} {direction} entry={entry} stop={stop} qty={pos['quantity']}")
    print("  当前为 dry_run=True，如确实需要实盘，设置 dry_run=False")
    
    result["error"] = "实盘模式需通过 MCP create_order 工具执行，当前仅模拟"
    return result


def log_execution(result: dict):
    """记录执行到 trade_reviews.jsonl"""
    if not result.get("success"):
        return
    
    log_entry = {
        "time": __import__("datetime").datetime.now().isoformat(),
        "schema": "hard_stop_v1",
        "symbol": result["symbol"],
        "direction": result["direction"],
        "entry": result["entry"],
        "stop": result["stop"],
        "position": result["position"],
        "orders": result["orders"],
        "dry_run": result.get("dry_run", True),
        # P2-5: custom_data 持久化字段（借鉴Freqtrade trade.set_custom_data）
        # 用于存储 entry_type / adjustment_count / meta_label / session 等
        "custom_data": result.get("custom_data", {}),
    }
    
    path = DATA / "hard_stop_log.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    return log_entry


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo: VWAP反抽做空计划
    result = execute_stop_loss(
        symbol="BTCUSDT",
        direction="short",
        entry=64283,
        stop=64510,
        risk_usd=2.03,
        leverage=100,
        account_balance=67.52,
        target1=63637,
        target2=63100,
        dry_run=True,
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result["success"]:
        log = log_execution(result)
        print(f"\n✅ 已记录到 hard_stop_log.jsonl")
