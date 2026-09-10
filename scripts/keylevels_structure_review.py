#!/usr/bin/env python3
"""棠溪 · BTC 批准关键位「结构复核」（2026-09-10）

## 为什么需要它

`keylevels_config.json` 里有一道安全闸：

    auto_approval_policy.max_structure_age_hours = 24
    → 超过 24 小时没有「结构复核」，全部批准位一律失效
    → active_approved_levels = 0 → 看门狗 DEGRADED → 到价监控停摆

设计意图是对的（防止无限自动续期而不复核市场），但**此前没有任何脚本或 cron
会写 `structure_reviewed_at`** —— 只有手工能写。结果：任何一次人工复核之后
最多 24 小时，BTC 到价监控必然停摆（本次实测：2026-09-05 16:14 起停摆）。

## 本脚本做什么

做一次**真的**复核，而不是盲目盖章：

  1. 读当前 SVP 的价值区读数（data/tv_dmi_cache.json，由既有 cron 每 ~20 分钟刷新，
     **不新占 TradingView 图表** —— 这点很重要，避免与用户看盘抢图）
  2. 把每个既有批准位与「同名的当前 SVP 读数」比对：
     - 能对上的（价值区·VAH ↔ VAH Price 等）：漂移必须 ≤ MAX_DRIFT_PCT
     - 对不上的（结构·/磁吸 HTF·）：只做价格带检查（±MAX_BAND_PCT）
  3. 通过数 ≥ MIN_VALID 才盖章；不通过就**不盖**，并写明谁失效了

这样安全属性保留：结构真漂了就复核不过，闸照常落下。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
TZ = timezone(timedelta(hours=8))

CONFIG = ROOT / "data" / "keylevels_config.json"
CACHE = ROOT / "data" / "tv_dmi_cache.json"
REVIEW_OUT = ROOT / "data" / "keylevels_structure_review.json"

# 批准位名称 → TV Data Window 字段（两边都是同一套 SVP 口径）
NAME_TO_SVP = {
    "价值区·VAH": "vah_price",
    "价值区·VAL": "val_price",
    "价值区·POC": "poc_price",
    "价值区·nPOC": "npoc_price",
    "价值区·M-VWAP": "m_vwap_price",
    "价值区·W-VWAP": "w_vwap_price",
    "价值区·S-VWAP": "s_vwap",
    "价值区·DO": "do_price",
}

MAX_DRIFT_PCT = 2.5    # 同名价值区漂移上限（超过说明该位已被市场重构）
MAX_BAND_PCT = 10.0    # 无同名读数的位，只要求落在现价 ±N% 内
MIN_VALID = 6          # 至少要复核到这么多个位，否则视为样本不足
MIN_STAMP_INTERVAL_MIN = 30   # 盖章最小间隔，避免每 2 分钟无意义写盘


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def _num(value):
    try:
        f = float(value)
        return f if f == f else None       # 过滤 nan
    except (TypeError, ValueError):
        return None


def _parse_ts(raw):
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=TZ)
    except (TypeError, ValueError):
        return None


def review(config: dict | None = None, snapshot: dict | None = None,
           now: datetime | None = None) -> dict:
    """对既有批准位做一次结构复核。

    返回 {ok, checked, valid, invalid:[...], price, reasons:[...], method}
    ok=True 才允许写 structure_reviewed_at。
    """
    now = now or datetime.now(TZ)
    config = config if isinstance(config, dict) else _load_json(CONFIG)
    snapshot = snapshot if isinstance(snapshot, dict) else _load_json(CACHE)

    price = _num(snapshot.get("last_price"))
    indicators = snapshot.get("indicators") if isinstance(snapshot.get("indicators"), dict) else {}
    # 品种校验：tv_dmi_cache.json 是共享文件，可能被别的品种（XAU 等）最后写入。
    # 拿黄金数据去核 BTC 关键位会得出「漂移 1600%」的假结论，必须先确认品种。
    snap_symbol = str(snapshot.get("symbol") or "").strip().upper()
    want = {f"{s}".upper() for s in (config.get("symbols", {}) or {}).keys()}
    if snap_symbol and want and not any(w in snap_symbol for w in want):
        return {"ok": False, "checked": 0, "valid": 0, "invalid": [], "price": price,
                "reasons": [f"快照品种不匹配：缓存是 {snap_symbol}，配置要的是 {sorted(want)}"],
                "method": "cache", "symbol_mismatch": True,
                "cache_timestamp": snapshot.get("timestamp")}
    if price is None or price <= 0:
        return {"ok": False, "checked": 0, "valid": 0, "invalid": [], "price": price,
                "reasons": ["无有效现价快照（tv_dmi_cache 缺失或 last_price 无效）"],
                "method": "cache"}

    checked, valid, invalid = 0, 0, []
    for symbol, block in (config.get("symbols", {}) or {}).items():
        if not isinstance(block, dict):
            continue
        for level in block.get("levels", []) or []:
            if not isinstance(level, dict) or level.get("enabled", True) is False:
                continue
            checked += 1
            name = str(level.get("name") or "")
            approved = _num(level.get("price"))
            if approved is None or approved <= 0:
                invalid.append({"name": name, "why": "批准价无效"})
                continue

            svp_key = NAME_TO_SVP.get(name)
            current = _num(indicators.get(svp_key)) if svp_key else None
            if current is not None and current > 0:
                drift = abs(approved - current) / current * 100.0
                if drift > MAX_DRIFT_PCT:
                    invalid.append({
                        "name": name, "why": f"同名价值区漂移 {drift:.1f}% > {MAX_DRIFT_PCT}%",
                        "approved": approved, "current": current, "drift_pct": round(drift, 2),
                    })
                    continue
            else:
                band = abs(approved - price) / price * 100.0
                if band > MAX_BAND_PCT:
                    invalid.append({
                        "name": name, "why": f"距现价 {band:.1f}% > {MAX_BAND_PCT}%（已不在有效交易带内）",
                        "approved": approved, "current": price, "band_pct": round(band, 2),
                    })
                    continue
            valid += 1

    # 价格带作为兜底：现价必须落在批准位的整体区间附近
    reasons = []
    # 严格口径：**任一**批准位失效就不盖章。
    # 理由：盖章会让看门狗把这批位整体续期（含已失效那个）→ 监控一个假价 → 发假警报。
    # 宁可让闸落下、要求人工重新批准，也不放行一个已知失效的位。
    ok = checked >= MIN_VALID and valid == checked
    if checked == 0:
        reasons.append("配置里没有启用的批准位")
    elif checked < MIN_VALID:
        reasons.append(f"只复核到 {checked} 个位，少于 {MIN_VALID} 个，样本不足")
    elif valid != checked:
        reasons.append(f"{checked - valid}/{checked} 个位已失效 —— 需要人工重新批准后再续期")
    if not ok:
        reasons.extend(f"{i['name']}：{i['why']}" for i in invalid[:6])

    return {
        "timestamp": now.isoformat(),      # source_health 用这个键判新鲜度
        "ok": bool(ok), "checked": checked, "valid": valid, "invalid": invalid,
        "price": price, "reasons": reasons, "method": "svp-drift+band",
        "reviewed_at": now.isoformat(),
        "cache_timestamp": snapshot.get("timestamp"),
    }


def apply_review(config_path: Path = CONFIG, result: dict | None = None,
                 now: datetime | None = None, force: bool = False) -> dict:
    """复核通过才把 structure_reviewed_at 写进配置。"""
    now = now or datetime.now(TZ)
    result = result or review()
    config = _load_json(config_path)
    policy = config.get("auto_approval_policy") or {}
    last_stamp = _parse_ts(policy.get("structure_reviewed_at"))
    if not result.get("ok"):
        result["stamped"] = False
        result["stamp_reason"] = "复核未通过，不盖章（安全闸保留）"
        return result
    if (not force and last_stamp is not None
            and (now - last_stamp).total_seconds() < MIN_STAMP_INTERVAL_MIN * 60):
        result["stamped"] = False
        result["stamp_reason"] = f"距上次盖章不足 {MIN_STAMP_INTERVAL_MIN} 分钟，跳过写盘"
        return result

    policy["structure_reviewed_at"] = now.isoformat()
    policy["structure_review_method"] = result["method"]
    policy["structure_review_valid"] = result["valid"]
    policy["structure_review_checked"] = result["checked"]
    config["auto_approval_policy"] = policy
    try:
        from atomic_json import atomic_write_json
        atomic_write_json(config_path, config)
    except Exception:
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    result["stamped"] = True
    result["stamp_reason"] = f"复核通过 {result['valid']}/{result['checked']}，已更新 structure_reviewed_at"
    return result


def main() -> int:
    result = review()
    result = apply_review(result=result)
    try:
        from atomic_json import atomic_write_json
        atomic_write_json(REVIEW_OUT, result)
    except Exception:
        REVIEW_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result.get("stamped"):
        print(f"✅ 结构复核通过 {result['valid']}/{result['checked']} → 已续授权 "
              f"(现价 {result['price']})")
    elif result.get("ok"):
        print(f"ℹ️ 结构复核通过但跳过写盘：{result.get('stamp_reason')}")
    else:
        print(f"⚠️ 结构复核未通过：{result.get('stamp_reason')}")
        for r in result.get("reasons", [])[:6]:
            print(f"   - {r}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
