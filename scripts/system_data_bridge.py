#!/usr/bin/env python3
"""
棠溪 · 系统数据桥 v1.0
统一 data_gatherer v2.0 的输出，供监控脚本（行情守望/信号巡检）调用。
替代 CCTV.py 中的 CVD/衍生品 获取逻辑。
"""

import json, hmac, hashlib, time, urllib.request, os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0"

# v1.2: 凭据从 hermes/secrets/binance.json 读取，不再硬编码明文。
# 与 data_gatherer.py 共用同一份凭据源；环境变量优先。
def _load_binance_keys():
    try:
        p = Path(__file__).resolve().parent.parent / "hermes" / "secrets" / "binance.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        d = {}
    bk = os.environ.get("BINANCE_API_KEY") or d.get("api_key", "")
    bs = os.environ.get("BINANCE_SECRET_KEY") or d.get("secret_key", "")
    return bk, bs

BK, BS = _load_binance_keys()

# ═══════════════════ 基础数据 ═══════════════════

def _price(sym: str) -> Optional[float]:
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return float(json.loads(resp.read())["price"])
    except: return None

def _sget(path: str, extra: str = "") -> dict:
    if not BK or not BS: return {"_e": "no keys"}
    ts = int(time.time() * 1000)
    p = f"{extra}{'&' if extra else ''}timestamp={ts}"
    sig = hmac.new(BS.encode(), p.encode(), hashlib.sha256).hexdigest()
    try:
        req = urllib.request.Request(f"https://fapi.binance.com{path}?{p}&signature={sig}", headers={"X-MBX-APIKEY": BK, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e: return {"_e": str(e)[:100]}

# ═══════════════════ 监控快捷函数 ═══════════════════

def cvd_dir(sym: str = "BTCUSDT") -> tuple:
    """CVD方向。v7.3: 优先真实逐笔aggTrades(A级)，失败回退Taker比率(B级)。"""
    # 优先 A级 真实逐笔 CVD
    try:
        from cvd_aggtrades import get_cvd_aggtrades
        r = get_cvd_aggtrades(sym, limit=1000)
        if r.get("quality") == "A级" and r.get("direction") in ("买", "卖", "中性"):
            return r["direction"], "A级"
    except Exception:
        pass
    # 回退：Taker 买卖比率（B级）
    d = _sget("/futures/data/takerlongshortRatio", f"symbol={sym}&period=5m&limit=1")
    if isinstance(d, list) and d:
        r = float(d[-1]["buySellRatio"])
        return ("买","B级") if r>1.1 else (("卖","B级") if r<0.9 else ("中性","B级"))
    return ("?","C级")

def deriv_text(sym: str = "BTCUSDT") -> str:
    fr = _sget("/fapi/v1/fundingRate", f"symbol={sym}&limit=1")
    ls = _sget("/futures/data/topLongShortAccountRatio", f"symbol={sym}&period=5m&limit=1")
    p = []
    if isinstance(fr,list) and fr: p.append(f"费率{float(fr[0]['fundingRate'])*100:+.4f}%")
    if isinstance(ls,list) and ls: p.append(f"大户{round(float(ls[-1]['longAccount'])*100,1)}%多")
    return " · ".join(p) or "不可用"

def price(sym: str) -> Optional[float]: return _price(sym)

def snapshot(sym: str = "BTCUSDT") -> dict:
    p = _price(sym) or 0
    fr = _sget("/fapi/v1/fundingRate", f"symbol={sym}&limit=2")
    cf = float(fr[0]["fundingRate"]) if isinstance(fr,list) and fr else 0
    pf = float(fr[1]["fundingRate"]) if isinstance(fr,list) and len(fr)>1 else 0
    ls = _sget("/futures/data/topLongShortAccountRatio", f"symbol={sym}&period=5m&limit=1")
    lp = round(float(ls[-1]["longAccount"])*100,1) if isinstance(ls,list) and ls else 0
    tk = _sget("/futures/data/takerlongshortRatio", f"symbol={sym}&period=5m&limit=1")
    tr = round(float(tk[-1]["buySellRatio"]),3) if isinstance(tk,list) and tk else 1.0
    td = "buy" if tr>1.1 else ("sell" if tr<0.9 else "neutral")
    oi = _sget("/fapi/v1/openInterest", f"symbol={sym}")
    ob = float(oi.get("openInterest",0)) if isinstance(oi,dict) else 0
    return {"symbol":sym,"price":p,"funding":{"current":cf,"prev":pf,"flipped":(cf>0)!=(pf>0)},"ls":{"long_pct":lp,"dir":"long" if lp>55 else "short" if lp<45 else "balanced"},"taker":{"ratio":tr,"dir":td,"q":"B"},"oi":{"btc":ob,"usd":ob*p}}

# ═══════════════════ 事件禁做 ═══════════════════

_EVENTS = {
    "2026-06-17": ("Fed利率决议(Warsh首秀)", "18:00", 60, 30),  # UTC 18:00 ≈ CST 次日2:00
}

def event_ban() -> tuple:
    now = datetime.now(timezone.utc)
    for d, (name, t, before, after) in _EVENTS.items():
        ed = datetime.strptime(d,"%Y-%m-%d").replace(tzinfo=timezone.utc)
        h,m = map(int,t.split(":"))
        et = ed.replace(hour=h,minute=m)
        if et-timedelta(minutes=before) <= now <= et+timedelta(minutes=after):
            return True, name
    return False, ""

# ═══════════════════ 方向翻转 ═══════════════════

_LAST = {"BTCUSDT": None, "XAUUSD": None}

def dir_flip(sym: str) -> tuple:
    """v1.1: 跑多模型引擎→检测方向翻转，并顺手记录预测供胜率回验。
    旧版 bug：①未 import sys → sys.path.insert 抛 NameError 被 bare except 吞；
    ②引擎在 hermes/scripts 不在 scripts → import 永远失败。两者叠加导致
    方向翻转检测和引擎预测记录从未真正运行。"""
    import sys as _sys
    global _LAST
    try:
        eng_dir = str(Path(__file__).resolve().parent.parent / "hermes" / "scripts")
        if eng_dir not in _sys.path:
            _sys.path.insert(0, eng_dir)
        from multi_model_engine import run_all_models, merge_directions
        s = snapshot(sym)
        r = run_all_models(s)
        m = merge_directions(r)
        nd = m["bias"]
        # 每轮记录预测，4h 后由 行情守望._verify_predictions_if_needed 回验
        try:
            from prediction_tracker import log_prediction
            pred = log_prediction(sym, m, r)
            # 补真实价格（log_prediction 默认写 0）
            px = s.get("price") or _price(sym)
            if px and pred:
                _patch_pred_price(sym, px)
        except Exception:
            pass
    except Exception:
        return False, "", ""
    old = _LAST.get(sym)
    _LAST[sym] = nd
    if old and old!=nd and old!="方向不明/震荡" and nd!="方向不明/震荡":
        return True, old, nd
    return False, old, nd


def _patch_pred_price(sym: str, price: float):
    """把刚写入的最后一条预测的 price_at_prediction 从 0 补成真实价。"""
    try:
        pf = Path(__file__).resolve().parent.parent / "data" / "prediction_log.jsonl"
        if not pf.exists():
            return
        lines = pf.read_text(encoding="utf-8").splitlines()
        for i in range(len(lines) - 1, -1, -1):
            if not lines[i].strip():
                continue
            obj = json.loads(lines[i])
            if obj.get("symbol") == sym and not obj.get("price_at_prediction"):
                obj["price_at_prediction"] = float(price)
                lines[i] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                pf.write_text("\n".join(lines) + "\n", encoding="utf-8")
                break
    except Exception:
        pass

if __name__ == "__main__":
    print(json.dumps(snapshot("BTCUSDT"), indent=2, ensure_ascii=False, default=str))
