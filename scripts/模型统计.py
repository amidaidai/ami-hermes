#!/usr/bin/env python3
"""模型统计 v1.1 — 按模型统计 R、MAE、MFE、出场质量和治理建议。"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts

OUT = ts.DATA_DIR / "strategy_model_stats.json"


def fnum(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def review_model_key(row: dict) -> str:
    """模型名兼容取值：自动标注 review 用 model_id，旧手动 review 用 model/setup_model。"""
    return str(row.get("model_id") or row.get("model") or row.get("setup_model") or "未标注模型")


def review_r(row: dict) -> float:
    """R 倍数兼容取值：自动标注用 result_r，旧手动用 r_multiple。"""
    val = row.get("result_r")
    if val in (None, ""):
        val = row.get("r_multiple")
    return fnum(val)


def group_reviews(reviews: list[dict]) -> dict:
    """按模型分组（兼容 model_id 与 model 两种字段）。"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in reviews:
        grouped[review_model_key(row)].append(row)
    return grouped


def max_drawdown(rs: list[float]) -> float:
    equity = peak = 0.0
    worst = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return round(worst, 4)


def main() -> None:
    ts.ensure_files()
    reviews = ts.load_jsonl(ts.REVIEW_LOG)
    grouped = group_reviews(reviews)
    gov = ts.read_json(ts.GOVERNANCE_FILE, ts.default_governance())
    policy = gov.get("policy", {})
    out = {"schema": "strategy_model_stats_v1", "time": ts.now_iso(), "models": {}, "portfolio": {}}
    all_r = []
    for model, rows in grouped.items():
        rs = [review_r(r) for r in rows]
        all_r.extend(rs)
        wins = sum(1 for r in rs if r > 0)
        losses = sum(1 for r in rs if r < 0)
        maes = [fnum(r.get("mae_r"), None) for r in rows if r.get("mae_r") not in (None, "")]
        mfes = [fnum(r.get("mfe_r"), None) for r in rows if r.get("mfe_r") not in (None, "")]
        qualities = Counter(str(r.get("exit_quality") or "未标注") for r in rows)
        loss_streak = max_loss_streak = cur = 0
        for r in rs:
            if r < 0:
                cur += 1
                max_loss_streak = max(max_loss_streak, cur)
            else:
                cur = 0
        loss_streak = cur
        sample = len(rows)
        total_r = round(sum(rs), 4)
        avg_r = round(total_r / max(sample, 1), 4)
        if sample < int(policy.get("min_sample_to_activate", 20)):
            decision = "样本不足，不升权"
        elif avg_r < float(policy.get("min_expectancy_r", 0.15)) or max_drawdown(rs) <= float(policy.get("max_drawdown_r", -6.0)):
            decision = "期望值或回撤不达标，降权/停用"
        else:
            decision = "统计达标，等待棠溪手动批准"
        out["models"][model] = {
            "trades": sample,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / max(sample, 1), 4),
            "total_r": total_r,
            "avg_r": avg_r,
            "max_drawdown_r": max_drawdown(rs),
            "current_loss_streak": loss_streak,
            "max_loss_streak": max_loss_streak,
            "avg_mae_r": round(sum(maes) / len(maes), 4) if maes else None,
            "avg_mfe_r": round(sum(mfes) / len(mfes), 4) if mfes else None,
            "exit_quality": dict(qualities),
            "decision": decision,
        }
    out["portfolio"] = {
        "trades": len(all_r),
        "total_r": round(sum(all_r), 4),
        "avg_r": round(sum(all_r) / max(len(all_r), 1), 4),
        "max_drawdown_r": max_drawdown(all_r),
        "sample_target": int(policy.get("min_sample_to_activate", 20)),
    }
    ts.write_json(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
