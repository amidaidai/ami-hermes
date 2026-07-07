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
    """刷新 TV 缓存，瞬时失败自动重试 2 次（审计 P1：避免偶发 CDP 断连直接退出）。"""
    last_msg = ""
    for attempt in range(3):
        try:
            cp = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "tv_live_dump.py")],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=90,
            )
            msg = (cp.stdout or cp.stderr or "").strip()
            if cp.returncode == 0:
                return msg
            last_msg = (msg or "tv_live_dump failed")[:300]
        except Exception as exc:
            last_msg = f"{type(exc).__name__}: {exc}"[:300]
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(last_msg or "tv_live_dump failed after 3 attempts")


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


def _pick_cache_relaxed() -> dict[str, Any]:
    """P0修复：放宽年龄限制读最新 TV cache（用于TV刷新失败兜底，不卡30min）。"""
    candidates = []
    for path in (TV_LIVE, TV_DMI):
        if not path.exists():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        if str(data.get("symbol")) != "BINANCE:BTCUSDT.P":
            continue
        candidates.append((path.stat().st_mtime, data, path.name))
    if not candidates:
        raise RuntimeError("no BINANCE:BTCUSDT.P TV cache (relaxed)")
    candidates.sort(reverse=True, key=lambda x: x[0])
    data = candidates[0][1]
    data["_picked_cache"] = candidates[0][2]
    return data


def recent_hilo() -> tuple[float | None, float | None]:
    """Fetch recent BTC 15m high/low with regional fallback.

    binance.com futures endpoint can return 403 from this host. For reference
    levels, spot BTCUSDT high/low is good enough as a fallback; TV SVP remains
    the authoritative source for executable futures levels.
    """
    urls = [
        "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=15m&limit=100",
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=100",
        "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=100",
    ]
    last_exc: Exception | None = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TangXi/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                bars = json.loads(resp.read().decode("utf-8"))
            if isinstance(bars, list) and bars:
                highs = [float(k[2]) for k in bars]
                lows = [float(k[3]) for k in bars]
                return max(highs), min(lows)
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"Binance recent hilo unavailable: {last_exc}")


def main() -> int:
    try:
        # P0修复：TV缓存刷新失败不再直接退出，转warning继续（Binance直取兜底）
        try:
            refresh_note = refresh_tv_cache()
        except Exception as tv_exc:
            refresh_note = f"TV刷新失败(降级Binance直取): {tv_exc}"[:200]
            print(f"⚠ {refresh_note}", file=sys.stderr)
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
                # P0修复：TV刷新已失败时不直接raise，放宽cache年龄到120min兜底一次
                relaxed_age = None
                if all(path.exists() for path in (TV_LIVE, TV_DMI)):
                    relaxed_age = min(age_minutes(TV_LIVE), age_minutes(TV_DMI))
                if relaxed_age is not None and relaxed_age <= 120:
                    stale_note = f"; TV刷新失败,复用{relaxed_age:.1f}min前cache兜底"
                else:
                    raise RuntimeError("missing TV fields: " + ",".join(missing))
            # Cron 子进程偶发读到刷新前缓存时，复读磁盘最新文件兜底一次。
            # P0修复：兜底分支放宽年龄限制（pick_cache 卡30min会再次raise），直接读最新文件
            cache = _pick_cache_relaxed()
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
        now = datetime.now(TZ)
        # P1: 失败落盘诊断文件，供看门狗/审计读取
        try:
            (DATA / "btc_ref_levels_error.json").write_text(
                json.dumps({"ts": now_iso(), "error": str(exc)[:300]},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"×同步失败 · BTC关键位 · {now.year}年{now.month}月{now.day}日{now.hour:02d}：{now.minute:02d}")
        print("")
        print("| 项目 | 数据 | 状态 |")
        print("|:----|:----|:----|")
        print("| 任务 | BTC关键位同步 | 失败 |")
        print("| 来源 | TradingView MCP | 异常 |")
        print("| 输出 | btc_ref_levels.json | 未更新 |")
        print("")
        print("| 模块 | 数据 | 状态 |")
        print("|:----|:----|:----|")
        print(f"| 异常 | `{str(exc)[:160]}` | 需处理 |")
        print("| 缓存 | tv_live/tv_dmi | 检查新鲜度 |")
        print("| Binance | recent hilo | 重测接口 |")
        print("")
        print("| 方向 | 触发 | 动作 |")
        print("|:---:|:----|:----|")
        print("| ×修复 | TV字段缺失/过期 | 先修复TV MCP |")
        print("| ○降级 | Binance可用 | 只保留高低点不下结论 |")
        print("| ↑恢复 | 缓存30分钟内更新 | 重跑同步脚本 |")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
