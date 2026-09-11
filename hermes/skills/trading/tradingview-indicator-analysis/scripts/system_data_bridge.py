#!/usr/bin/env python3
"""
棠溪 · 系统数据桥 v1.0
统一 data_gatherer v2.0 的输出，供监控脚本（行情守望/信号巡检）调用。
替代 行情守望.py 中分散的 get_cvd/get_price/get_close 逻辑。

提供：
- cvd_dir(sym) → (方向, 质量)     Taker B级替代C级K线估算
- deriv_text(sym) → str           衍生品摘要（费率+多空比）
- price(sym) → float              统一价格获取
- snapshot(sym) → dict            完整数据快照
- event_ban() → (bool, reason)    事件禁做检测（Fed等）
- dir_flip(sym) → (bool, old, new) 多模型方向翻转检测
"""

import json, hmac, hashlib, time, urllib.request, os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0"
BK = os.environ.get("BINANCE_API_KEY") or ""
BS = os.environ.get("BINANCE_SECRET_KEY") or ""

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
        req = urllib.request.Request(
            f"https://fapi.binance.com{path}?{p}&signature={sig}",
            headers={"X-MBX-APIKEY": BK, "User-Agent": UA}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e: return {"_e": str(e)[:100]}

def cvd_dir(sym: str = "BTCUSDT") -> tuple:
    """Taker B级方向"""
    d = _sget("/futures/data/takerlongshortRatio", f"symbol={sym}&period=5m&limit=1")
    if isinstance(d, list) and d:
        r = float(d[-1]["buySellRatio"])
        return ("买","B级") if r>1.1 else (("卖","B级") if r<0.9 else ("中性","B级"))
    return ("?","C级")

def deriv_text(sym: str = "BTCUSDT") -> str:
    """衍生品摘要"""
    fr = _sget("/fapi/v1/fundingRate", f"symbol={sym}&limit=1")
    ls = _sget("/futures/data/topLongShortAccountRatio", f"symbol={sym}&period=5m&limit=1")
    p = []
    if isinstance(fr,list) and fr: p.append(f"费率{float(fr[0]['fundingRate'])*100:+.4f}%")
    if isinstance(ls,list) and ls: p.append(f"大户{round(float(ls[-1]['longAccount'])*100,1)}%多")
    return " · ".join(p) or "不可用"

def price(sym: str) -> Optional[float]: return _price(sym)

def snapshot(sym: str = "BTCUSDT") -> dict:
    """完整数据快照"""
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

# Event ban calendar (UTC timezone)
_EVENTS = {}
def event_ban() -> tuple:
    now = datetime.now(timezone.utc)
    for d, (name, t, before, after) in _EVENTS.items():
        ed = datetime.strptime(d,"%Y-%m-%d").replace(tzinfo=timezone.utc)
        h,m = map(int,t.split(":"))
        et = ed.replace(hour=h,minute=m)
        if et-timedelta(minutes=before) <= now <= et+timedelta(minutes=after):
            return True, name
    return False, ""

# Direction flip detection
_LAST = {"BTCUSDT": None, "XAUUSD": None}
def dir_flip(sym: str) -> tuple:
    global _LAST
    try:
        import sys; sys.path.insert(0, str(Path(__file__).parent))
        from multi_model_engine import run_all_models, merge_directions
        s = snapshot(sym)
        r = run_all_models(s)
        m = merge_directions(r)
        nd = m["bias"]
    except: return False, "", ""
    old = _LAST.get(sym)
    _LAST[sym] = nd
    if old and old!=nd and old!="方向不明/震荡" and nd!="方向不明/震荡":
        return True, old, nd
    return False, old, nd
