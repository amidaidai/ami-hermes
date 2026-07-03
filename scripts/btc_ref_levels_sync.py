#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC关键位同步 no_agent 版。

替代旧 LLM cron，避免 Grok/模型额度导致 403。流程：
1) 调用 tv_live_dump.py 通过真实 TradingView CDP 刷新 tv_live.json/tv_dmi_cache.json；
2) 从新鲜 TV 缓存读取 SVP Data Window 关键位；
3) 从 Binance 15m K线计算 recent_high/recent_low；
4) 写 data/btc_ref_levels.json，供 btc_daemon 热读。

成功静默；失败输出 ASCII/中文诊断并非零退出。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
TV_LIVE = DATA / "tv_live.json"
TV_DMI = DATA / "tv_dmi_cache.json"
OUT = DATA / "btc_ref_levels.json"


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def num(v: Any) -> float | None:
    if v is None:
        return None
    text = str(v).strip().replace(",", "").replace("\u202f", "").replace(" ", "")
    text = text.replace("−", "-")
    mult = 1.0
    if text and text[-1].upper() in {"K", "M", "B"}:
        suffix = text[-1].upper()
        text = text[:-1]
        mult = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}[suffix]
    try:
        return float(text) * mult
    except Exception:
        return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def age_minutes(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 60


def refresh_tv_cache() -> str:
    cp = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "tv_live_dump.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    )
    msg = (cp.stdout or cp.stderr or "").strip()
    if cp.returncode != 0:
        raise RuntimeError((msg or "tv_live_dump failed")[:300])
    return msg


def pick_cache() -> dict[str, Any]:
    candidates = []
    for path in (TV_LIVE, TV_DMI):
        if not path.exists():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        if str(data.get("symbol")) != "BINANCE:BTCUSDT.P":
            continue
        if age_minutes(path) > 30:
            continue
        candidates.append((path.stat().st_mtime, data, path.name))
    if not candidates:
        raise RuntimeError("no fresh BINANCE:BTCUSDT.P TV cache")
    candidates.sort(reverse=True, key=lambda x: x[0])
    data = candidates[0][1]
    data["_picked_cache"] = candidates[0][2]
    return data


def recent_hilo() -> tuple[float | None, float | None]:
    url = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=15m&limit=100"
    req = urllib.request.Request(url, headers={"User-Agent": "TangXi/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        bars = json.loads(resp.read().decode("utf-8"))
    highs = [float(k[2]) for k in bars]
    lows = [float(k[3]) for k in bars]
    return max(highs), min(lows)


def main() -> int:
    try:
        refresh_note = refresh_tv_cache()
        cache = pick_cache()
        ind = cache.get("indicators") or {}
        vwap = num(ind.get("s_vwap") or ind.get("S VWAP"))
        val = num(ind.get("val_price") or cache.get("val"))
        vah = num(ind.get("vah_price") or cache.get("vah"))
        poc = num(ind.get("poc_price") or cache.get("poc"))
        do = num(ind.get("do_price"))
        w_vwap = num(ind.get("w_vwap_price"))
        recent_high, recent_low = recent_hilo()
        required = {"vwap": vwap, "val": val, "vah": vah, "poc": poc, "w_vwap": w_vwap}
        missing = [k for k, v in required.items() if v is None]
        if missing:
            stale_ok = False
            stale_note = ""
            if all(path.exists() for path in (TV_LIVE, TV_DMI)):
                age = min(age_minutes(TV_LIVE), age_minutes(TV_DMI))
                stale_ok = age <= 30 and bool(refresh_note)
                stale_note = f"; reused cache age {age:.1f}min after refresh stdout: {refresh_note[:160]}" if stale_ok else ""
            if not stale_ok:
                raise RuntimeError("missing TV fields: " + ",".join(missing))
            # Cron 子进程偶发读到刷新前缓存时，复读磁盘最新文件兜底一次。
            cache = pick_cache()
            ind = cache.get("indicators") or {}
            vwap = num(ind.get("s_vwap") or ind.get("S VWAP"))
            val = num(ind.get("val_price") or cache.get("val"))
            vah = num(ind.get("vah_price") or cache.get("vah"))
            poc = num(ind.get("poc_price") or cache.get("poc"))
            do = num(ind.get("do_price"))
            w_vwap = num(ind.get("w_vwap_price"))
            required = {"vwap": vwap, "val": val, "vah": vah, "poc": poc, "w_vwap": w_vwap}
            missing = [k for k, v in required.items() if v is None]
            if missing:
                raise RuntimeError("missing TV fields: " + ",".join(missing) + stale_note)
        payload = {
            "vwap": vwap,
            "val": val,
            "vah": vah,
            "poc": poc,
            "do": do,
            "w_vwap": w_vwap,
            "recent_low": recent_low,
            "recent_high": recent_high,
            "updated_at": now_iso(),
            "source": "btc_ref_levels_sync.py",
            "tv_cache": cache.get("_picked_cache"),
            "tv_symbol": cache.get("symbol"),
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"BTC ref levels sync failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
