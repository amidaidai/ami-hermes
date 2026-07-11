#!/usr/bin/env python3
"""真实TV闭柱候选的影子记录、4/8/16根结果标注与分组校准。"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _shadow_quality(signal: dict[str, Any]) -> tuple[int, int, int]:
    dual_raw = signal.get("dual")
    dual: dict[str, Any] = dict(dual_raw) if isinstance(dual_raw, dict) else {}
    valid_code = int(_f(dual.get("valid_code", signal.get("haldro_valid_code", 0))))
    nested = sum(isinstance(signal.get(key), dict) for key in ("main", "dual", "regime", "risk"))
    has_features = int(isinstance(signal.get("features"), dict) and bool(signal.get("features")))
    return valid_code, nested, has_features


def append_shadow_signal(path: str | Path, signal: dict[str, Any]) -> bool:
    """按signal_id幂等写入；同桶权威性提升时原位升级。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        raise ValueError("shadow signal requires signal_id")
    if p.exists():
        lines = p.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(existing.get("signal_id")) != signal_id:
                continue
            if _shadow_quality(signal) <= _shadow_quality(existing):
                return False
            lines[idx] = json.dumps(signal, ensure_ascii=False, separators=(",", ":"))
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            tmp.replace(p)
            return True
    with p.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(signal, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True


def label_outcome(
    signal: dict[str, Any],
    future_bars: Iterable[dict[str, Any]],
    *,
    horizons: tuple[int, ...] = (4, 8, 16),
) -> dict[str, dict[str, Any]]:
    """只消费信号之后的K线，按R记录MFE/MAE及先触发止损/目标。"""
    bars = list(future_bars)
    entry = _f(signal.get("entry"))
    stop = _f(signal.get("stop"))
    target = _f(signal.get("target"))
    side = str(signal.get("side") or "long").lower()
    risk = abs(entry - stop)
    if entry <= 0 or stop <= 0 or target <= 0 or risk <= 0:
        raise ValueError("signal entry/stop/target must define positive risk")

    result: dict[str, dict[str, Any]] = {}
    for horizon in horizons:
        sample = bars[: max(0, int(horizon))]
        if side == "short":
            mfe = max((entry - _f(bar.get("low"))) / risk for bar in sample) if sample else 0.0
            mae = max((_f(bar.get("high")) - entry) / risk for bar in sample) if sample else 0.0
        else:
            mfe = max((_f(bar.get("high")) - entry) / risk for bar in sample) if sample else 0.0
            mae = max((entry - _f(bar.get("low"))) / risk for bar in sample) if sample else 0.0

        first_hit = "none"
        bars_to_hit = None
        for idx, bar in enumerate(sample, 1):
            high, low = _f(bar.get("high")), _f(bar.get("low"))
            if side == "short":
                stop_hit, target_hit = high >= stop, low <= target
            else:
                stop_hit, target_hit = low <= stop, high >= target
            # 同根同时触发时采取保守口径：先记止损，避免回测乐观偏差。
            if stop_hit:
                first_hit, bars_to_hit = "stop", idx
                break
            if target_hit:
                first_hit, bars_to_hit = "target", idx
                break
        result[f"h{horizon}"] = {
            "mfe_r": round(max(0.0, mfe), 4),
            "mae_r": round(max(0.0, mae), 4),
            "first_hit": first_hit,
            "bars_to_hit": bars_to_hit,
        }
    return result


def calibrate_groups(
    rows: Iterable[dict[str, Any]],
    *,
    horizon: int = 16,
    min_samples: int = 30,
) -> dict[str, dict[str, Any]]:
    """按体制×主模型分组；样本不足只报告，不输出概率。"""
    buckets: dict[str, list[str]] = defaultdict(list)
    hkey = f"h{int(horizon)}"
    for row in rows:
        regime_raw = row.get("regime")
        if isinstance(regime_raw, dict):
            regime = str(regime_raw.get("code") or "unknown")
        else:
            regime = str(regime_raw or "unknown")
        model = str(row.get("model_id") or ((row.get("main") or {}).get("model_id") if isinstance(row.get("main"), dict) else "") or "unknown")
        hit = str(((row.get("outcome") or {}).get(hkey) or {}).get("first_hit") or "none")
        buckets[f"{regime}|{model}"].append(hit)

    result: dict[str, dict[str, Any]] = {}
    for key, hits in sorted(buckets.items()):
        wins = hits.count("target")
        losses = hits.count("stop")
        decisive = wins + losses
        calibrated = wins / decisive if len(hits) >= min_samples and decisive else None
        result[key] = {
            "samples": len(hits),
            "decisive_samples": decisive,
            "wins": wins,
            "losses": losses,
            "calibrated_win_rate": calibrated,
            "reliable": len(hits) >= min_samples,
        }
    return result
