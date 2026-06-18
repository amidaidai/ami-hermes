#!/usr/bin/env python3
"""
棠溪 · 三重障碍自动标注管线 v1.0

目的: 解决 trade_plans/trade_reviews 68:1 复盘失衡。
每个有 setup_id 的触发事件，在到期后用三重障碍法（止盈/止损/超时）
自动判定结果，生成 trade_review_v2 训练样本，再回喂 meta_labeler。

用法:
    python 自动标注.py            # 标注所有未标注的到期事件
    python 自动标注.py --dry-run  # 只看会标注多少，不写盘

数据流:
    trade_events.jsonl (有setup_id+direction)
      → 拉入场后 K 线 (Binance klines, ATR 推导止盈止损)
      → triple_barrier.label_event()
      → trade_reviews.jsonl (auto_labeled=True)
      → meta_labeler 训练
"""

from __future__ import annotations
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
TZ = timezone(timedelta(hours=8))
sys.path.insert(0, str(ROOT / "scripts"))

import triple_barrier as tb

EVENTS = DATA / "trade_events.jsonl"
REVIEWS = DATA / "trade_reviews.jsonl"
LABELED_STATE = DATA / "auto_labeled_setups.json"

# 标注参数（日内交易：5m K 线，竖轨 48 根 = 4 小时持有上限）
# 1m K 线 + ATR×1.5 止损距离过紧（BTC 一分钟即扫到），退化为噪音；
# 改用 5m 周期让止损/止盈距离贴近实际日内持仓节奏。
MAX_BARS = 48          # 竖轨：入场后 48 根 5m K 线（=4 小时）
INTERVAL = "5m"
RR = 2.0               # ATR 推导止盈止损用的 R:R
ATR_MULT = 1.5         # 止损 = entry ± ATR_MULT * ATR

# 周期 → 毫秒（用于竖轨时间闸门换算，不能写死 60_000）
_INTERVAL_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000,
                "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}
BAR_MS = _INTERVAL_MS.get(INTERVAL, 300_000)


def _iso_to_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso)
    return int(dt.timestamp() * 1000)


def fetch_klines_after(symbol: str, start_ms: int, interval: str = INTERVAL,
                       limit: int = MAX_BARS) -> list:
    """拉取 start_ms 之后的 K 线（含入场当根之后）。"""
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": interval,
                    "startTime": start_ms, "limit": limit},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        return [[float(x[0]), float(x[1]), float(x[2]), float(x[3]),
                 float(x[4]), float(x[5])] for x in r.json()]
    except Exception as e:
        print(f"  ⚠ klines {symbol}: {e}")
        return []


def compute_atr(klines: list, period: int = 14) -> float:
    """简易 ATR：真实波幅均值。"""
    if len(klines) < 2:
        return 0.0
    trs = []
    prev_close = klines[0][4]
    for bar in klines[1:]:
        high, low, close = bar[2], bar[3], bar[4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close
    window = trs[:period] if len(trs) >= period else trs
    return sum(window) / len(window) if window else 0.0


def _load_state() -> dict:
    if LABELED_STATE.exists():
        try:
            return json.loads(LABELED_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    LABELED_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _already_reviewed_setups() -> set:
    """已有 review 的 setup_id（避免重复标注）。"""
    done = set()
    if REVIEWS.exists():
        for line in REVIEWS.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("setup_id"):
                    done.add(r["setup_id"])
            except Exception:
                continue
    return done


def label_pending(dry_run: bool = False) -> dict:
    """标注所有到期未标注的事件。"""
    if not EVENTS.exists():
        return {"error": "no events file"}

    now_ms = int(time.time() * 1000)
    state = _load_state()
    done_setups = _already_reviewed_setups()
    state_done = set(state.get("labeled", []))

    events = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue

    candidates = []
    for e in events:
        sid = e.get("setup_id")
        if not sid or sid in done_setups or sid in state_done:
            continue
        if e.get("direction") not in ("long", "short"):
            continue
        t = e.get("time")
        if not t:
            continue
        entry_ms = _iso_to_ms(t)
        # 必须已过竖轨时间（入场 + MAX_BARS 根 × 周期分钟）才能判定
        if now_ms < entry_ms + MAX_BARS * BAR_MS:
            continue
        candidates.append((e, entry_ms))

    print(f"待标注事件: {len(candidates)} 个（已标注 {len(done_setups)}，状态记录 {len(state_done)}）")

    if dry_run:
        return {"candidates": len(candidates), "dry_run": True}

    new_reviews = []
    newly_labeled = []
    for e, entry_ms in candidates:
        symbol = e.get("symbol", "BTCUSDT")
        klines = fetch_klines_after(symbol, entry_ms)
        if not klines:
            continue
        atr = compute_atr(klines)
        review = tb.label_event(e, klines, max_bars=MAX_BARS, atr=atr, rr=RR)
        if review is None:
            continue
        new_reviews.append(review)
        newly_labeled.append(e["setup_id"])
        print(f"  {e['setup_id']}: {review['outcome']} · {review['result_r']:+.2f}R")
        time.sleep(0.2)  # 限速友好

    # 写 reviews
    if new_reviews:
        with REVIEWS.open("a", encoding="utf-8") as f:
            for r in new_reviews:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        state.setdefault("labeled", []).extend(newly_labeled)
        state["last_run"] = datetime.now(TZ).isoformat()
        _save_state(state)

    # 统计
    outcomes = {"take_profit": 0, "stop_loss": 0, "timeout": 0}
    for r in new_reviews:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1

    result = {
        "labeled": len(new_reviews),
        "outcomes": outcomes,
        "total_reviews": len(done_setups) + len(new_reviews),
    }

    # 回喂 meta_labeler 训练
    try:
        from meta_labeler import MetaLabeler
        all_reviews = []
        for line in REVIEWS.read_text(encoding="utf-8").splitlines():
            try:
                all_reviews.append(json.loads(line))
            except Exception:
                continue
        ml = MetaLabeler()
        train_result = ml.train(all_reviews)
        ml.save_stats()
        result["meta_labeler"] = train_result
    except Exception as e:
        result["meta_labeler"] = {"error": str(e)}

    return result


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    out = label_pending(dry_run=dry)
    print("\n" + json.dumps(out, ensure_ascii=False, indent=2))
