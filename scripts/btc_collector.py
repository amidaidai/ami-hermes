#!/usr/bin/env python3
"""BTC 全数据源采集器 v1.1 — no_agent, 每1m聚合。
   输出: ~/AppData/Local/hermes/data/btc_latest.json
"""
import json, time, urllib.request, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
os.makedirs(DIR, exist_ok=True)
OUT = os.path.join(DIR, "btc_latest.json")
HIST = os.path.join(DIR, "btc_history.jsonl")
BINANCE = "https://api.binance.com"
FAPI = "https://fapi.binance.com"

def http_get(url, t=5):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "D/1.0"}), timeout=t
    ).read())

ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

record = {"ts": ts, "ts_unix": time.time()}

# 逐字段单次请求，用 try/except 隔离
try:
    record["price"] = float(http_get(f"{BINANCE}/api/v3/ticker/price?symbol=BTCUSDT")["price"])
except: pass

try:
    k = http_get(f"{BINANCE}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=30")
    vs = sum(float(x[5]) for x in k)
    ws = sum((float(x[2])+float(x[3]))/2*float(x[5]) for x in k)
    record["vwap"] = round(ws/vs, 2) if vs else None
except: pass

try:
    record["vol24"] = round(float(http_get(f"{BINANCE}/api/v3/ticker/24hr?symbol=BTCUSDT")["volume"]), 0)
except: pass

try:
    record["oi"] = round(float(http_get(f"{FAPI}/fapi/v1/openInterest?symbol=BTCUSDT")["openInterest"]), 0)
except: pass

try:
    record["funding"] = round(float(http_get(f"{FAPI}/fapi/v1/premiumIndex?symbol=BTCUSDT")["lastFundingRate"]), 6)
except: pass

try:
    lsr = http_get(f"{FAPI}/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1")
    if lsr: record["ls_ratio"] = round(float(lsr[0]["longShortRatio"]), 4)
except: pass

try:
    tak = http_get(f"{FAPI}/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=1")
    if tak: record["taker_ratio"] = round(float(tak[0]["buySellRatio"]), 4)
except: pass

# 落盘
with open(OUT, "w") as f:
    json.dump(record, f)
with open(HIST, "a") as f:
    f.write(json.dumps(record) + "\n")
lines = open(HIST).readlines()
if len(lines) > 2000:
    with open(HIST, "w") as f:
        f.writelines(lines[-2000:])

# === 宏观数据桥（独立采集，可选）===
MACRO = os.path.join(DIR, "btc_macro.json")
try:
    fng = json.loads(http_get("https://api.alternative.me/fng/?limit=1"))
    if fng and "data" in fng and len(fng["data"]) > 0:
        macro = {"timestamp": ts, "fng_value": int(fng["data"][0]["value"]), "fng_label": fng["data"][0]["value_classification"]}
        try:
            # DXY from Yahoo
            dxy_resp = http_get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB", t=5)
            if dxy_resp and "chart" in dxy_resp and dxy_resp["chart"].get("result"):
                meta = dxy_resp["chart"]["result"][0]["meta"]
                macro["dxy"] = round(meta["regularMarketPrice"], 2)
        except:
            pass
        with open(MACRO, "w") as f:
            json.dump(macro, f)
except:
    pass
