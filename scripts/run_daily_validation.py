#!/usr/bin/env python3
"""Daily validation runner for 棠溪 trading system.

Produces timestamped backtest / walk-forward / model coverage artifacts.
No LLM required; suitable for Hermes no_agent cron.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

from backtest_runner import BTConfig, backtest_from_klines, format_result
from walk_forward import walk_forward_validate, format_wf_result

TZ = timezone(timedelta(hours=8))
OUT_DIR = ROOT / "data" / "validation"
DATA_FILE = ROOT / "data" / "btc_klines_30d_merged.json"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _arrays(rows: list[dict]):
    return {
        "opens": [float(r["open"]) for r in rows],
        "highs": [float(r["high"]) for r in rows],
        "lows": [float(r["low"]) for r in rows],
        "closes": [float(r["close"]) for r in rows],
        "volumes": [float(r.get("volume", 0) or 0) for r in rows],
        "timestamps": [str(r.get("time") or r.get("timestamp") or r.get("open_time") or i) for i, r in enumerate(rows)],
    }


def main() -> int:
    now = datetime.now(TZ)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    if not DATA_FILE.exists():
        # 静默降级：数据文件缺失时不是失败，跳过回测
        summary = {
            "time": now.isoformat(),
            "error": f"数据文件缺失 {DATA_FILE}",
            "backtest": None,
            "walk_forward": None,
            "coverage": None,
            "human_backtest": f"⚠️ 跳过：{DATA_FILE.name} 不存在",
            "human_walk_forward": "",
        }
        print(json.dumps({"ok": False, "skipped": True,
                          "reason": f"数据文件 {DATA_FILE.name} 不存在",
                          "summary": summary}, ensure_ascii=False))
        return 0  # 返回0而非抛异常，让日间维护正常完成
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cfg = BTConfig(fee_bps=4.0, max_hold=96, risk_per_trade=3.0, min_rr=2.0, warmup=200, startup_candle_count=400, asset="BTCUSDT")

    bt = backtest_from_klines("BTCUSDT", rows, cfg=cfg)
    arr = _arrays(rows)
    wf = walk_forward_validate("BTCUSDT", arr["closes"], arr["highs"], arr["lows"], arr["opens"], arr["volumes"], arr["timestamps"], cfg=cfg, risk_per_trade=3.0)

    bt_dict = dataclasses.asdict(bt)
    wf_dict = dataclasses.asdict(wf)
    coverage = {
        "time": now.isoformat(),
        "symbol": "BTCUSDT",
        "candles": len(rows),
        "models_with_trades": len(bt.model_stats),
        "model_stats": bt.model_stats,
        "sanity": {
            "max_rr": max((float(t.rr_ratio) for t in bt.trades), default=0),
            "trade_count": bt.total_trades,
            "win_rate": bt.win_rate,
            "profit_factor": bt.profit_factor,
        },
    }
    summary = {
        "time": now.isoformat(),
        "backtest": {"trades": bt.total_trades, "win_rate": bt.win_rate, "total_r": bt.total_r, "profit_factor": bt.profit_factor, "max_drawdown_r": bt.max_drawdown_r},
        "walk_forward": wf_dict,
        "coverage": coverage,
        "human_backtest": format_result(bt),
        "human_walk_forward": format_wf_result(wf),
    }

    paths = {
        "backtest": OUT_DIR / f"backtest_{stamp}.json",
        "walk_forward": OUT_DIR / f"walk_forward_{stamp}.json",
        "coverage": OUT_DIR / f"model_coverage_{stamp}.json",
        "latest": OUT_DIR / "audit_summary_latest.json",
    }
    _write_json(paths["backtest"], bt_dict)
    _write_json(paths["walk_forward"], wf_dict)
    _write_json(paths["coverage"], coverage)
    _write_json(paths["latest"], summary)
    print(json.dumps({"ok": True, "paths": {k: str(v) for k, v in paths.items()}, "summary": summary["backtest"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
