#!/usr/bin/env python
"""持仓与信号监控 — 每5分钟。no_agent模式，零token消耗。
检查: 价格告警 / 关键位穿越 / Protections状态 / 新信号
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
TIMEDELTA_OFFSET = 8  # CST = UTC+8

DATA = Path(__file__).resolve().parent.parent.parent / "data"
SECRETS = Path(__file__).resolve().parent.parent / "secrets"

def load_json(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except:
        pass
    return {}

def check_alerts():
    """检查价格是否接近关键位"""
    alerts = []
    # BTC
    btc_card = DATA / "auto_card_BTCUSDT.md"
    if btc_card.exists():
        content = btc_card.read_text()
        # 解析极简卡的关键位置
        for line in content.split('\n'):
            if '← 价踩在这' in line or '← 距' in line:
                alerts.append(f"BTC{line.strip()}")
    # XAU
    xau_card = DATA / "auto_card_XAUUSD.md"
    if xau_card.exists():
        content = xau_card.read_text()
        for line in content.split('\n'):
            if '← 价踩在这' in line or '← 距' in line:
                alerts.append(f"XAU{line.strip()}")
    return alerts

def check_protections():
    """检查Protections状态"""
    prot_file = DATA / "protections_state.json"
    if prot_file.exists():
        try:
            prot = json.loads(prot_file.read_text())
            violations = prot.get("active_violations", [])
            if violations:
                return f"Protections拦截: {', '.join(violations)}"
        except:
            pass
    return "Protections: OK"

def check_new_signals():
    """检查是否有新的交易信号"""
    plans_file = DATA / "trade_plans.jsonl"
    if plans_file.exists():
        lines = plans_file.read_text().strip().split('\n')
        if lines:
            last = json.loads(lines[-1])
            ts = last.get("timestamp", "")
            status = last.get("status", "?")
            if status.startswith("A"):
                return f"信号: {status} @ {ts}"
    return "无新信号"

if __name__ == "__main__":
    silent = "--silent" in sys.argv
    now = datetime.now(timezone.utc)
    cst_now = now.replace(tzinfo=None) if now.tzinfo else now
    
    status = {
        "time": cst_now.isoformat(),
        "alerts": check_alerts(),
        "protections": check_protections(),
        "signals": check_new_signals(),
    }
    
    if not silent:
        print(f"[{cst_now.strftime('%m-%d %H:%M')}] 监控心跳")
        for a in status["alerts"]:
            print(f"  ⚡ {a}")
        print(f"  🛡 {status['protections']}")
        print(f"  📡 {status['signals']}")
    
    # Write status
    (DATA / "monitor_state.json").write_text(json.dumps(status, indent=2, ensure_ascii=False))
