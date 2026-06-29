#!/usr/bin/env python3
"""智能更新结构 v1.0 — 根据刷新队列用纯脚本重算近端监控位。"""

from __future__ import annotations

import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts

LEVELS_FILE = DATA / "monitor_levels.json"
REFRESH_FILE = DATA / "structure_refresh_requests.jsonl"
PLAN_LOG = DATA / "trade_plans.jsonl"


def now() -> datetime:
    return datetime.now().astimezone()


def now_iso() -> str:
    return now().isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def plan_id(symbol: str) -> str:
    return f"{symbol}-{now().strftime('%Y%m%d-%H%M')}"


def expires(minutes: int) -> str:
    return (now() + timedelta(minutes=minutes)).isoformat()


def level_conf(grade: str, score: int, label: str, basis: list[str], missing: list[str] | None = None) -> dict[str, Any]:
    return {"grade": grade, "score": score, "label": label, "basis": basis, "missing": missing or ["TradingView成交量复核", "订单流确认"], "method": "智能结构更新v1"}


def round_price(symbol: str, value: float) -> float:
    if symbol.endswith("USDT"):
        return round(value, 2 if value < 10000 else 1)
    if symbol == "XAUUSD":
        return round(value, 1)
    return round(value, 3)


def build_levels(symbol: str, price: float) -> list[dict[str, Any]]:
    if symbol == "XAUUSD":
        return [
            {"name": "R1_reclaim_accept", "display_name": "阻1·近端收复接受位", "level": round_price(symbol, price * 1.0018), "side": "resistance", "type": "breakout_accept", "action": "突破并回踩不破才按延续；高杠杆不追第一根", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.999)}", "status": "active", "level_confidence": level_conf("B", 73, "近端结构", ["金十实时价重算", "近端突破接受", "失效线明确"], ["TradingView复核", "美元/美债事件确认"])},
            {"name": "R2_extension", "display_name": "阻2·上方延伸压力位", "level": round_price(symbol, price * 1.0038), "side": "resistance", "type": "breakout_accept", "action": "只看放量突破后的回踩确认，不追高", "priority": "medium", "condition": "near_or_breach", "expires": "240m", "valid_until": expires(240), "invalid_if": f"15m close below {round_price(symbol, price * 1.001)}", "status": "active", "level_confidence": level_conf("C", 66, "延伸位", ["当前价上方延伸", "用于防追高", "等待复核"], ["TradingView复核", "时段成交确认"])},
            {"name": "S1_vwap_retest", "display_name": "支1·近端回踩确认位", "level": round_price(symbol, price * 0.9982), "side": "support", "type": "vwap_reclaim_filter", "action": "回踩守住才考虑顺势；跌破接受转等待", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.9965)}", "status": "active", "level_confidence": level_conf("B", 72, "近端回踩", ["金十实时价重算", "近端支撑", "失效线明确"], ["TradingView VWAP复核", "美元/美债确认"])},
            {"name": "S2_sweep_reclaim", "display_name": "支2·扫低回收位", "level": round_price(symbol, price * 0.995), "side": "support", "type": "sweep_reclaim", "action": "刺破快速收回才看回收；跌破接受不逆势", "priority": "medium", "condition": "near_or_breach", "expires": "240m", "valid_until": expires(240), "invalid_if": f"15m close below {round_price(symbol, price * 0.992)}", "status": "active", "level_confidence": level_conf("C", 66, "扫损备份", ["下方扫流动性位", "备份支撑", "等待确认"], ["TradingView复核", "时段成交确认"])},
        ]
    # crypto/default
    return [
        {"name": "R1_reclaim_accept", "display_name": "阻1·近端收复接受位", "level": round_price(symbol, price * 1.002), "side": "resistance", "type": "breakout_accept", "action": "突破并回踩不破才考虑顺势；假突破不追", "priority": "high", "condition": "near_or_breach", "expires": "90m", "valid_until": expires(90), "invalid_if": f"5m close below {round_price(symbol, price * 0.998)}", "status": "active", "level_confidence": level_conf("B", 74, "近端结构", ["实时价重算", "突破接受模型", "失效线明确"])},
        {"name": "R2_upper_extension", "display_name": "阻2·上方延伸压力位", "level": round_price(symbol, price * 1.006), "side": "resistance", "type": "breakout_accept", "action": "放量突破后只做回踩确认，不追第一根", "priority": "medium", "condition": "near_or_breach", "expires": "180m", "valid_until": expires(180), "invalid_if": f"15m close below {round_price(symbol, price * 1.001)}", "status": "active", "level_confidence": level_conf("C", 66, "延伸位", ["实时价上方延伸", "用于防追高", "待订单流确认"])},
        {"name": "S1_retest", "display_name": "支1·近端回踩确认位", "level": round_price(symbol, price * 0.998), "side": "support", "type": "retest", "action": "回踩守住才考虑顺势；跌破说明接受失败", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.995)}", "status": "active", "level_confidence": level_conf("B", 73, "近端回踩", ["实时价重算", "近端支撑", "失效线明确"])},
        {"name": "S2_sweep_reclaim", "display_name": "支2·扫流动性回收位", "level": round_price(symbol, price * 0.992), "side": "support", "type": "sweep_reclaim", "action": "刺破后快速收回才看回收；跌破接受不逆势", "priority": "medium", "condition": "near_or_breach", "expires": "1d", "valid_until": expires(24 * 60), "invalid_if": f"15m close below {round_price(symbol, price * 0.988)}", "status": "active", "level_confidence": level_conf("C", 66, "扫损备份", ["实时价下方扫损", "备份支撑", "待CVD确认"])},
    ]


def build_levels_v2(symbol: str, price: float) -> list[dict[str, Any]]:
    """v2: 优先用五模型匹配生成真实结构位，退化到硬编码"""
    try:
        from five_model_matcher import generate_all_setups
        
        # v2.1: 用 indicator_feed 拉真实K线算指标喂五模型。
        # 旧版从 system_data_bridge._LAST 取 'tv' 字段，但 _LAST 只存方向字符串、
        # 没有 tv 子键 → tv_indicators 恒空 → 五模型从不触发 → 永远退化到硬编码假位。
        tv_indicators = {}
        try:
            from indicator_feed import build_indicators
            tv_indicators = build_indicators(symbol) or {}
        except Exception:
            tv_indicators = {}
        
        if tv_indicators:
            setups = generate_all_setups(
                current_price=price,
                vwap=tv_indicators.get('S VWAP', price * 1.01),
                vwap_band1=tv_indicators.get('S VWAP -Band1', price * 0.995),
                vwap_band2=tv_indicators.get('S VWAP -Band2', price * 0.99),
                vah=tv_indicators.get('VAH Price', price * 1.02),
                val=tv_indicators.get('VAL Price', price * 0.98),
                poc=tv_indicators.get('POC Price', price * 1.01),
                ema9=tv_indicators.get('EMA 9', price),
                ema21=tv_indicators.get('EMA 21', price),
                recent_high=tv_indicators.get('recent_high', price * 1.05),
                recent_low=tv_indicators.get('recent_low', price * 0.95),
                atr=tv_indicators.get('atr', price * 0.007),
                cvd_value=tv_indicators.get('CVD Value', 0),
                cvd_slope=tv_indicators.get('CVD Slope', 0),
            )
            
            # v2.3: 五模型入场 → 结构骨架(阻1/阻2/支1/支2)注入真实血肉。
            # 骨架命名保留棠溪熟悉的结构语义；五模型提供真实入场/止损/止盈/R:R/依据。
            # 关键：side 按【方向】定语义——做空=阻力(在上方做空)，做多=支撑(在下方做多)，
            # 不能按 entry 相对现价分（VAL回收/POC拒绝的做多位可能挂在现价上方等回踩，
            # 若按价格归为阻力会出现"阻力位却是做多单"的语义矛盾）。
            # 同方向多个 setup 去重：同方向保留 R:R 合格且置信最高的，再按距现价远近命名。
            res, sup = [], []
            for s in setups.get('all_setups', []):
                (res if s['direction'] == 'short' else sup).append(s)
            # 同侧按距现价由近到远排序（命名 1=最近）
            res.sort(key=lambda x: abs(x['entry'] - price))
            sup.sort(key=lambda x: abs(x['entry'] - price))

            levels = []
            for grp, side, zh in ((res, 'resistance', '阻'), (sup, 'support', '支')):
                for i, s in enumerate(grp[:2], start=1):
                    levels.append(_setup_to_structure_level(symbol, price, s, side, f"{zh}{i}", i))

            if levels:
                return levels
    except Exception:
        pass
    
    # 退化到原硬编码
    return build_levels(symbol, price)


# 结构骨架显示名（保留棠溪熟悉的语义；五模型决定具体价位/方向/R:R）
_STRUCT_LABEL = {
    "阻1": "阻1·近端结构位", "阻2": "阻2·上方延伸位",
    "支1": "支1·近端结构位", "支2": "支2·下方延伸位",
}
RR_SANITY_CAP = 10.0  # R:R > 10 视为入场距止损过近导致的虚高，标记而非缩小


def _setup_to_structure_level(symbol: str, price: float, s: dict, side: str, slot: str, rank: int) -> dict[str, Any]:
    """把单个五模型 setup 包装成结构骨架监控位（阻1/支1…），血肉=真实入场/止损/R:R。"""
    rr = float(s.get('rr_ratio') or 0)
    model = s.get('model', '五模型')
    dir_zh = '做空' if s['direction'] == 'short' else '做多'
    # R:R 异常处理：>10 标记"目标过远·需确认"，不缩小（XAU 因 ATR 小、VWAP 距离大易虚高）
    rr_anomaly = rr > RR_SANITY_CAP
    rr_txt = f"R:R {rr:.1f}" if not rr_anomaly else f"R:R {rr:.0f}⚠目标过远需确认"
    targets = s.get('targets') or []
    tgt_txt = ('→`' + '`/`'.join(f"{t:.0f}" for t in targets[:2]) + '`') if targets else ''
    action = f"{model}·{dir_zh}入场`{s['entry']:.0f}`·止损`{s['stop']:.0f}`{tgt_txt}·{rr_txt}"
    conf = int(s.get('confidence') or 60)
    # R:R 异常或不足底线 1:2 → 降一档置信与优先级
    if rr_anomaly or rr < 2.0:
        conf = min(conf, 66)
    grade = 'A' if conf >= 80 else ('B' if conf >= 70 else 'C')
    expires_min = 120 if rank == 1 else (180 if side == 'resistance' else 240)
    basis = list(s.get('confluence', []))[:3]
    missing = ['TradingView成交量复核']
    if rr_anomaly:
        missing.append('R:R虚高·实盘需复核目标可达性')
    return {
        'name': f"{'R' if side == 'resistance' else 'S'}{rank}_{model}",
        'display_name': _STRUCT_LABEL.get(slot, slot),
        'level': round_price(symbol, s['entry']),
        'side': side,
        'type': 'five_model',
        'model_id': model,
        'direction': s['direction'],
        'rr_ratio': round(rr, 1),
        'rr_anomaly': rr_anomaly,
        'stop': round_price(symbol, s['stop']),
        'targets': [round_price(symbol, t) for t in targets[:2]],
        'action': action,
        'priority': 'high' if (conf >= 73 and not rr_anomaly) else 'medium',
        'condition': 'near_or_breach',
        'expires': f"{expires_min}m",
        'valid_until': expires(expires_min),
        'invalid_if': f"15m close {('above' if s['direction'] == 'short' else 'below')} {s['stop']:.0f}",
        'status': 'active',
        'level_confidence': level_conf(grade, conf, f"五模型·{model}", basis, missing),
    }


def update_symbol(raw: dict[str, Any], symbol: str, reasons: list[str] | None = None) -> dict[str, Any]:
    block = raw.setdefault("symbols", {}).setdefault(symbol, {})
    price_probe = ts.template_price(symbol)
    price = price_probe.get("price") or block.get("price_at_analysis")
    if not isinstance(price, (int, float)) or price <= 0:
        raise RuntimeError(f"{symbol} 无可用实时价格")
    # 交叉验证：从实时快照取质量，避免price_probe缓存过时而与source_snapshot不一致
    snap_quality = price_probe.get("quality")
    try:
        import json as _json
        snap = _json.loads((DATA / "source_snapshot.json").read_text(encoding="utf-8"))
        snap_symbols = snap.get("symbols") if isinstance(snap.get("symbols"), dict) else {}
        if symbol in snap_symbols:
            snap_q = snap_symbols[symbol].get("quality", snap_quality)
            if snap_q and snap_q != snap_quality:
                print(f"[智能更新] {symbol} 快照质量覆写: price_probe={snap_quality} → snapshot={snap_q}")
                snap_quality = snap_q
    except Exception:
        pass
    pid = plan_id(symbol)
    block.update({
        "plan_id": pid,
        "analysis_cycle": "智能更新 · 近端结构重算 · 等5m确认 · 旧位降权",
        "price_at_analysis": float(price),
        "updated": now_iso(),
        "monitor_enabled": True,
        "needs_structure_refresh": False,
        "refresh_reason": "",
        "levels": build_levels_v2(symbol, float(price)),
        "smart_update": {"time": now_iso(), "source": price_probe.get("source"), "quality": snap_quality, "confidence": price_probe.get("confidence"), "reasons": reasons or []},
    })
    append_jsonl(PLAN_LOG, {"time": now_iso(), "schema": "trade_plan_v1", "plan_id": pid, "symbol": symbol, "state": "B等待", "score": 7, "model": "智能结构更新", "direction": "等待", "entry": None, "stop": None, "targets": [], "risk_usd": ts.template_risk_limit(symbol), "tags": ["智能更新", "近端结构", "等待确认"], "source": price_probe})
    return block


def pending_symbols(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in rows:
        if row.get("status") != "pending" or not row.get("symbol"):
            continue
        out.setdefault(row["symbol"], []).extend(row.get("reasons") or [])
    return out


def main(argv: list[str]) -> None:
    raw = read_json(LEVELS_FILE, {"schema": "monitor_levels_multi_v1", "symbols": {}})
    rows = read_jsonl(REFRESH_FILE)
    targets = argv[1:] or list(pending_symbols(rows))
    if not targets:
        print("无待智能更新品种")
        return
    reasons_by_symbol = pending_symbols(rows)
    updated: list[str] = []
    for symbol in targets:
        update_symbol(raw, symbol, reasons_by_symbol.get(symbol, []))
        updated.append(symbol)
    raw["updated"] = now_iso()
    write_json(LEVELS_FILE, raw)
    for row in rows:
        if row.get("symbol") in updated and row.get("status") == "pending":
            row["status"] = "done"
            row["done_time"] = now_iso()
    write_jsonl(REFRESH_FILE, rows)
    print("智能更新完成：" + "、".join(updated))


if __name__ == "__main__":
    main(sys.argv)
