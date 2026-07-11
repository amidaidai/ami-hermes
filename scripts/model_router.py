#!/usr/bin/env python3
"""体制→模型路由器：只选一个主模型，旧confidence不作为概率。"""
from __future__ import annotations

from typing import Any, Iterable

from decision_regime import DecisionRegime


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def select_primary_model(
    candidates: Iterable[dict[str, Any]],
    regime: DecisionRegime,
    *,
    calibration: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """过滤体制白名单后按区域/触发质量和R:R选择唯一主模型。"""
    calibration = calibration or {}
    evaluated: list[dict[str, Any]] = []
    for raw in candidates:
        item = dict(raw)
        model_id = str(item.get("model_id") or "unknown")
        if model_id not in regime.allowed_models:
            continue
        quality = max(0.0, min(100.0, _f(item.get("quality"))))
        rr = max(0.0, _f(item.get("rr")))
        score_components = {
            "quality": quality * 0.70,
            "rr": min(rr, 4.0) / 4.0 * 30.0,
        }
        cal = calibration.get(f"{regime.code}|{model_id}") or {}
        # 只有达到最小样本后才可用校准概率做轻微排序；绝不使用旧写死confidence。
        if cal.get("reliable") and cal.get("calibrated_win_rate") is not None:
            score_components["calibration"] = float(cal["calibrated_win_rate"]) * 10.0
        route_score = sum(score_components.values())
        evaluated.append({
            **item,
            "model_id": model_id,
            "route_score": round(route_score, 4),
            "score_components": score_components,
            "selected": False,
        })
    if not evaluated:
        return None
    evaluated.sort(key=lambda item: (-item["route_score"], -_f(item.get("rr")), item["model_id"]))
    evaluated[0]["selected"] = True
    selected = dict(evaluated[0])
    selected["route_rank"] = 1
    selected["evaluated"] = evaluated
    return selected
