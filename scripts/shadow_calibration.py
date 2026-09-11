#!/usr/bin/env python3
"""真实TV闭柱候选的影子记录、4/8/16根结果标注与分组校准。"""
from __future__ import annotations

import json
import math
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
    """OHLC模拟，不是实际成交证明。调用者保证仅传信号后的闭柱。

    order_model.type: limit(GTC)或market_next_open；禁止猜测订单类型。
    同柱双触达止损优先；盘中限价成交柱不能假设此前高点可止盈。
    R以计划风险为分母；无完整成本模型仅报gross，绝不补零冒充net。
    cost_model: fee_bps/slippage_bps(每侧)，funding=none或per_bar。
    per_bar为持仓每柱显式funding_rate乘该柱close；正值多付空收。
    未成熟、未成交、未平仓均不输出已实现收益；不强行期末平仓。
    """
    bars = list(future_bars)
    entry = _f(signal.get("entry"))
    stop = _f(signal.get("stop"))
    target = _f(signal.get("target"))
    side = str(signal.get("side") or "long").lower()
    risk = abs(entry - stop)
    if (not all(math.isfinite(v) and v > 0 for v in (entry, stop, target))
            or side not in {"long", "short"} or risk <= 0
            or not (stop < entry < target if side == "long" else target < entry < stop)):
        raise ValueError("signal entry/stop/target must define positive risk")
    model = signal.get("order_model") or {}
    order_type = model.get("type") if isinstance(model, dict) else None
    costs = signal.get("cost_model") or {}
    sign = 1 if side == "long" else -1
    result: dict[str, dict[str, Any]] = {}
    for horizon in horizons:
        sample = bars[: max(0, int(horizon))]
        out: dict[str, Any] = dict(mature=False, observed_bars=len(sample),
            filled=False, fill_price=None, fill_bar=None, exit_price=None,
            first_hit="none", bars_to_hit=None, mfe_r=None, mae_r=None,
            gross_r=None, net_r=None, fee_r=None, slippage_r=None, funding_r=None,
            status="insufficient_bars", cost_status="unavailable", simulation=True)
        result[f"h{horizon}"] = out
        valid = all(isinstance(b, dict) and b.get("closed") is not False
            and all(math.isfinite(_f(b.get(k))) and _f(b.get(k)) > 0 for k in ("open", "high", "low", "close"))
            and _f(b["low"]) <= min(_f(b["open"]), _f(b["close"]))
            <= max(_f(b["open"]), _f(b["close"])) <= _f(b["high"]) for b in sample)
        if not valid:
            out["status"] = "invalid_bars"
            continue
        out["mature"] = len(sample) == horizon and horizon > 0
        if order_type not in {"limit", "market_next_open"}:
            out["status"] = "missing_order_model"
            continue
        fill = None
        held = []
        mfe = mae = 0.0
        for idx, bar in enumerate(sample, 1):
            op, high, low = (_f(bar[k]) for k in ("open", "high", "low"))
            intrabar_fill = False
            if fill is None:
                at_open = order_type == "market_next_open" or (op <= entry if sign == 1 else op >= entry)
                if at_open:
                    fill = op
                elif low <= entry <= high:
                    fill = entry
                    intrabar_fill = True
                else:
                    continue
                out.update(filled=True, fill_price=fill, fill_bar=idx)
            held.append(bar)
            # MFE/MAE are bar-envelope bounds, not reconstructed intrabar paths.
            mfe = max(mfe, ((high - fill) if sign == 1 else (fill - low)) / risk)
            mae = max(mae, ((fill - low) if sign == 1 else (high - fill)) / risk)
            stop_hit = low <= stop if sign == 1 else high >= stop
            target_hit = high >= target if sign == 1 else low <= target
            if stop_hit:
                exit_price = min(op, stop) if sign == 1 else max(op, stop)
                out.update(first_hit="stop", bars_to_hit=idx, exit_price=exit_price)
                break
            if target_hit and not intrabar_fill:
                # Resting take-profit limit: no invented favorable gap improvement.
                out.update(first_hit="target", bars_to_hit=idx, exit_price=target)
                break
        if fill is not None:
            out.update(mfe_r=round(mfe, 4), mae_r=round(mae, 4))
        out["status"] = ("insufficient_bars" if not out["mature"] else
                         "unfilled" if fill is None else
                         "closed" if out["exit_price"] is not None else "open")
        if out["status"] != "closed" or fill is None:
            continue
        exit_price = _f(out["exit_price"])
        out["gross_r"] = sign * (exit_price - fill) / risk
        if not isinstance(costs, dict) or not all(k in costs for k in ("fee_bps", "slippage_bps", "funding")):
            continue
        try:
            fee, slip = float(costs["fee_bps"]), float(costs["slippage_bps"])
            if not all(math.isfinite(v) and v >= 0 for v in (fee, slip)):
                continue
            if costs["funding"] == "none":
                funding = 0.0
            elif costs["funding"] == "per_bar":
                rates = [float(b["funding_rate"]) for b in held]
                if not all(math.isfinite(v) for v in rates):
                    continue
                funding = sign * sum(r * _f(b["close"]) for r, b in zip(rates, held)) / risk
            else:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        out.update(fee_r=(fill + exit_price) * fee / 10000 / risk,
                   slippage_r=(fill + exit_price) * slip / 10000 / risk,
                   funding_r=funding, cost_status="modeled")
        out["net_r"] = out["gross_r"] - out["fee_r"] - out["slippage_r"] - funding
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
        outcome = ((row.get("outcome") or {}).get(hkey) or {})
        hit = str(outcome.get("first_hit") or "none") if outcome.get("mature") is True and outcome.get("filled") is True else "ineligible"
        buckets[f"{regime}|{model}"].append(hit)

    result: dict[str, dict[str, Any]] = {}
    for key, hits in sorted(buckets.items()):
        wins = hits.count("target")
        losses = hits.count("stop")
        decisive = wins + losses
        calibrated = wins / decisive if decisive >= max(1, min_samples) else None
        interval = None
        if calibrated is not None:
            z = 1.959963984540054
            denominator = 1 + z * z / decisive
            center = (calibrated + z * z / (2 * decisive)) / denominator
            half = z * math.sqrt(calibrated * (1 - calibrated) / decisive + z * z / (4 * decisive * decisive)) / denominator
            interval = [max(0.0, center - half), min(1.0, center + half)]
        result[key] = {
            "min_samples": max(1, min_samples),
            "win_rate_interval": interval,
            "interval_method": "wilson_95",
            "samples": len(hits),
            "eligible_samples": len(hits) - hits.count("ineligible"),
            "decisive_samples": decisive,
            "wins": wins,
            "losses": losses,
            "calibrated_win_rate": calibrated,
            "reliable": decisive >= max(1, min_samples),
        }
    return result
