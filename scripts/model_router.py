#!/usr/bin/env python3
"""体制→模型路由器：只选一个主模型，旧confidence不作为概率。"""
from __future__ import annotations

import math
from typing import Any, Iterable, cast

from decision_regime import DecisionRegime


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _validated_calibration_rate(cal: Any) -> float | None:
    """Do not trust a legacy reliable flag without its decisive denominator."""
    if not isinstance(cal, dict) or cal.get("reliable") is not True:
        return None
    n, wins, losses = (cal.get(key) for key in ("decisive_samples", "wins", "losses"))
    minimum = cal.get("min_samples", 30)
    if any(type(value) is not int or value < 0 for value in (n, wins, losses, minimum)):
        return None
    n, wins, losses, minimum = cast(tuple[int, int, int, int], (n, wins, losses, minimum))
    if n < max(30, minimum) or wins + losses != n:
        return None
    rate = cal.get("calibrated_win_rate")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate):
        return None
    if not 0 <= rate <= 1 or not math.isclose(rate, wins / n, rel_tol=1e-6, abs_tol=1e-8):
        return None
    return float(rate)


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
        calibrated_rate = _validated_calibration_rate(cal)
        if calibrated_rate is not None:
            score_components["calibration"] = calibrated_rate * 10.0
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
