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

from shadow_calibration import label_outcome, order_model_for_plan

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
    model_id = str(main.get("model_id") or record.get("model_id") or "unknown")
    projection: dict[str, Any] = {
        **record,
        "side": side,
        "entry": _num(main.get("entry", record.get("entry"))),
        "stop": _num(main.get("stop", record.get("stop"))),
        "target": _num(main.get("target", record.get("target"))),
        "model_id": model_id,
    }
    # 2026-09-13：信号未携带 order_model 时按计划语义回填（PLAN_ORDER_MODEL）；
    # 未知模型保持缺失 → missing_order_model（禁止猜测订单类型）。
    if not projection.get("order_model"):
        backfill = order_model_for_plan(model_id)
        if backfill:
            projection["order_model"] = backfill
    return projection


def _bar_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, (list, tuple)) and len(raw) >= 7:
        return dict(open=_num(raw[1]), high=_num(raw[2]), low=_num(raw[3]),
                    close=_num(raw[4]), open_time=_num(raw[0]), close_time=_num(raw[6]))
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
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
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
        signal_ts = int(record.get("ts") or 0)
        timeframe = str(record.get("timeframe") or "15m")
        # Validate against the requested interval, never infer it from returned
        # bars: missing bars could otherwise masquerade as a longer interval.
        step_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000,
            "15m": 900_000, "30m": 1_800_000,
            "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
            "6h": 21_600_000, "8h": 28_800_000, "12h": 43_200_000,
            "1d": 86_400_000,
        }.get(timeframe.replace("min", "m"))
        if step_ms is None:
            stats["unsupported"] += 1
            continue
        first_open = (signal_ts // step_ms + 1) * step_ms
        raw_bars = fetcher(symbol, timeframe, signal_ts + 1, required)
        bars = [bar for raw in raw_bars if (bar := _bar_dict(raw)) is not None]
        bars = [b for b in bars if b.get("closed") is not False
                and signal_ts < _num(b.get("open_time")) <= _num(b.get("close_time")) < now_ms]
        bars = sorted({b["open_time"]: b for b in bars}.values(), key=lambda b: b["open_time"])
        if len(bars) < required or any(
            _num(bar.get("open_time")) != first_open + index * step_ms
            for index, bar in enumerate(bars[:required])
        ):
            stats["waiting"] += 1
            continue
        try:
            outcome = label_outcome(signal, bars[:required], horizons=horizons)
        except ValueError:
            stats["invalid"] += 1
            continue
        if not all(item["mature"] for item in outcome.values()):
            stats["invalid"] += 1
            continue
        labeled.append({**signal, "outcome": outcome, "labeled_at": now_ms})
        existing.add(signal_id)
        stats["labeled"] += 1
    return labeled, dict(stats)


# 本机实测（2026-09-13）：Binance 直连固定 12s 超时，走代理 0.4s 可用。
# 每条信号都先探直连＝每条白等 12s；111 条 ≈ 22 分钟，*/15 的 cron 会永久跑不完。
# 探明可用模式后缓存并优先复用；直连给短超时作兜底。
_PROXY_MODE: list[bool | None] = [None]


def _fetch_json(url: str, direct: bool) -> Any:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "TangXi-Shadow/1.0"})
    with opener.open(req, timeout=5 if direct else 10) as response:
        payload = json.loads(response.read())
    _PROXY_MODE[0] = direct
    return payload


def fetch_binance_closed_bars(symbol: str, timeframe: str, start_ms: int, limit: int) -> list[Any]:
    interval = timeframe.lower().replace("min", "m")
    params = f"symbol={symbol}&interval={interval}&startTime={int(start_ms)}&limit={max(1, min(int(limit) + 2, 1000))}"
    urls = [
        f"https://fapi.binance.com/fapi/v1/klines?{params}",

    ]
    now_ms = int(time.time() * 1000)
    preferred = _PROXY_MODE[0]
    order = (True, False) if preferred is None else (preferred, not preferred)
    for url in urls:
        for direct in order:
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
