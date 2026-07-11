#!/usr/bin/env python3
"""零Token影子结果标注器：成熟后以4/8/16根闭柱计算MFE/MAE。"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from shadow_calibration import label_outcome

ROOT = Path(__file__).resolve().parents[1]
SIGNALS_PATH = ROOT / "data" / "shadow" / "decision_signals.jsonl"
OUTCOMES_PATH = ROOT / "data" / "shadow" / "decision_outcomes.jsonl"


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def _signal_projection(record: dict[str, Any]) -> dict[str, Any]:
    main_raw = record.get("main")
    main: dict[str, Any] = dict(main_raw) if isinstance(main_raw, dict) else {}
    side = str(main.get("direction") or record.get("side") or "neutral").lower()
    return {
        **record,
        "side": side,
        "entry": _num(main.get("entry", record.get("entry"))),
        "stop": _num(main.get("stop", record.get("stop"))),
        "target": _num(main.get("target", record.get("target"))),
        "model_id": str(main.get("model_id") or record.get("model_id") or "unknown"),
    }


def _bar_dict(raw: Any) -> dict[str, float] | None:
    if isinstance(raw, dict):
        high, low = _num(raw.get("high")), _num(raw.get("low"))
        return {"high": high, "low": low} if high > 0 and low > 0 else None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        high, low = _num(raw[2]), _num(raw[3])
        return {"high": high, "low": low} if high > 0 and low > 0 else None
    return None


def label_ready_records(
    records: Iterable[dict[str, Any]],
    fetcher: Callable[[str, str, int, int], list[Any]],
    *,
    now_ms: int | None = None,
    horizons: tuple[int, ...] = (4, 8, 16),
    existing_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """标注已拥有完整最长周期闭柱的加密候选；不支持资产只计数，不误报失败。"""
    del now_ms  # fetcher负责只返回已收柱；保留参数便于测试和未来时钟门禁。
    existing = set(existing_ids or ())
    stats: Counter[str] = Counter()
    labeled: list[dict[str, Any]] = []
    required = max(horizons)

    for record in records:
        signal_id = str(record.get("signal_id") or "")
        if not signal_id:
            stats["invalid"] += 1
            continue
        if signal_id in existing:
            stats["existing"] += 1
            continue
        symbol = str(record.get("symbol") or "").upper()
        if not symbol.endswith("USDT"):
            stats["unsupported"] += 1
            continue
        signal = _signal_projection(record)
        if signal["side"] not in {"long", "short"} or min(signal["entry"], signal["stop"], signal["target"]) <= 0:
            stats["invalid"] += 1
            continue
        raw_bars = fetcher(symbol, str(record.get("timeframe") or "15m"), int(record.get("ts") or 0) + 1, required)
        bars = [bar for raw in raw_bars if (bar := _bar_dict(raw)) is not None]
        if len(bars) < required:
            stats["waiting"] += 1
            continue
        outcome = label_outcome(signal, bars[:required], horizons=horizons)
        labeled.append({**signal, "outcome": outcome, "labeled_at": int(time.time() * 1000)})
        existing.add(signal_id)
        stats["labeled"] += 1
    return labeled, dict(stats)


def _fetch_json(url: str, direct: bool) -> Any:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "TangXi-Shadow/1.0"})
    with opener.open(req, timeout=10) as response:
        return json.loads(response.read())


def fetch_binance_closed_bars(symbol: str, timeframe: str, start_ms: int, limit: int) -> list[Any]:
    interval = timeframe.lower().replace("min", "m")
    params = f"symbol={symbol}&interval={interval}&startTime={int(start_ms)}&limit={max(1, min(int(limit) + 2, 1000))}"
    urls = [
        f"https://fapi.binance.com/fapi/v1/klines?{params}",
        f"https://api.binance.com/api/v3/klines?{params}",
        f"https://data-api.binance.vision/api/v3/klines?{params}",
    ]
    now_ms = int(time.time() * 1000)
    for url in urls:
        for direct in (True, False):
            try:
                payload = _fetch_json(url, direct)
                if isinstance(payload, list):
                    return [bar for bar in payload if isinstance(bar, list) and len(bar) > 6 and int(bar[6]) < now_ms]
            except Exception:
                continue
    return []


def main() -> int:
    records = _read_jsonl(SIGNALS_PATH)
    existing_rows = _read_jsonl(OUTCOMES_PATH)
    existing_ids = {str(row.get("signal_id")) for row in existing_rows if row.get("signal_id")}
    rows, stats = label_ready_records(records, fetch_binance_closed_bars, existing_ids=existing_ids)
    if rows:
        OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTCOMES_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"影子结果标注：新增{len(rows)}条 · 累计{len(existing_ids) + len(rows)}条")
    elif stats.get("invalid"):
        print(f"影子结果标注：无新增 · 无效{stats['invalid']}条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
