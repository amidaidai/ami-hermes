#!/usr/bin/env python3
"""vNext影子回测：与实盘共用decision_loop，不再调用旧写死置信模型。"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from decision_loop import resolve_final_verdict
from decision_regime import DecisionRegime
from shadow_calibration import label_outcome


def _regime(raw: Any) -> DecisionRegime | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return DecisionRegime(
        code=str(raw.get("code") or "balance"),
        name=str(raw.get("name") or raw.get("code") or "未知"),
        allowed_models=tuple(raw.get("allowed_models") or ()),
        blocked_models=tuple(raw.get("blocked_models") or ()),
        position_multiplier=float(raw.get("position_multiplier", 1.5)),
        exhausted=bool(raw.get("exhausted")),
        reason=str(raw.get("reason") or ""),
    )


def _snapshot_parts(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Any, dict[str, Any]]:
    """读取新嵌套契约；兼容早期影子JSONL的扁平记录。"""
    main = record.get("main")
    if not isinstance(main, dict):
        main = {
            "grade": record.get("grade") or "C等待",
            "direction": record.get("side") or "neutral",
            "model_id": record.get("model_id") or "unknown",
            "entry": record.get("entry"), "stop": record.get("stop"),
            "target": record.get("target"), "rr": record.get("rr"),
            "mcp_fvg_quality_score": record.get("fvg_quality"),
            "mcp_ob_quality_score": record.get("ob_quality"),
        }
    dual = record.get("dual")
    if not isinstance(dual, dict):
        symbol = str(record.get("symbol") or "").upper()
        dual = {
            "asset_is_crypto": symbol.endswith("USDT"),
            "valid_code": record.get("haldro_valid_code", 0),
            "risk_code": record.get("haldro_risk_code", 0),
            "conflict": bool(record.get("haldro_conflict", False)),
        }
    regime = record.get("regime") if isinstance(record.get("regime"), dict) else None
    risk = record.get("risk")
    if not isinstance(risk, dict):
        risk = {
            "allowed": str(record.get("final_state") or "WAIT") != "NO-GO",
            "risk_usd": record.get("risk_usd", 0.0), "violations": [],
        }
    return dict(main), dict(dual), regime, dict(risk)


def replay_shadow_records(
    records: Iterable[dict[str, Any]],
    future_bars_by_signal: dict[str, list[dict[str, Any]]],
    *,
    horizons: tuple[int, ...] = (4, 8, 16),
) -> dict[str, Any]:
    """逐条复跑唯一裁决并标注后续结果；输入必须是当时快照，禁止未来字段。"""
    trades: list[dict[str, Any]] = []
    blocked = 0
    gate_stats: Counter[str] = Counter()
    states: Counter[str] = Counter()
    for record in records:
        main, dual, regime_raw, risk = _snapshot_parts(record)
        final = resolve_final_verdict(
            str(record.get("symbol") or ""),
            main,
            dual,
            regime=_regime(regime_raw),
            risk=risk,
        )
        states[final.state] += 1
        if not final.executable:
            blocked += 1
            for reason in final.blockers:
                gate_stats[reason] += 1
            continue
        signal_id = str(record.get("signal_id") or "")
        signal = {
            **main,
            "signal_id": signal_id,
            "symbol": record.get("symbol"),
            "side": final.side,
            "entry": final.entry,
            "stop": final.stop,
            "target": final.target,
            "model_id": final.model_id,
            "grade": final.grade,
            "regime": (regime_raw or {}).get("code", record.get("regime_code", "unknown")),
        }
        outcome = label_outcome(signal, future_bars_by_signal.get(signal_id, []), horizons=horizons)
        trades.append({**signal, "outcome": outcome, "risk_usd": final.risk_usd})
    return {
        "executed": len(trades),
        "blocked": blocked,
        "total": len(trades) + blocked,
        "trades": trades,
        "gate_stats": dict(gate_stats),
        "state_stats": dict(states),
    }
