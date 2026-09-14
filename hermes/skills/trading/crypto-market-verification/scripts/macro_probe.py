"""加密分析现场探针：恐贪 + 宏观指数 + BTC 市占。

用途：auto_card 卡面的「订单流」恐贪数与「宏观/事件」行会带旧值或缺失
（实测同轮卡面恐贪 68 / 现场 57），本脚本给出一条命令的独立重算口径，
出卡前用它反查卡面值。

用法： python scripts/macro_probe.py
输出： 扁平 JSON，逐项带 _src（live / unavailable(原因)）。

网络： Yahoo 类境外源直连被封 IP，必须走代理 127.0.0.1:7897；
      alternative.me 与 CoinGecko 直连可用，仍保留代理兜底。
      不要改用 FMP 同类符号（^TNX/DXY/GC=F 在 FMP 上是 402）。
"""
import json
import urllib.parse
import urllib.request

PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url, proxy=None, timeout=15):
    """按 指定代理 → 直连 → 系统代理 的顺序取 JSON，全失败返回 {'_error': ...}。"""
    last = "unknown"
    for handler in ([proxy] if proxy else [None, PROXY]):
        try:
            if handler:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler(handler))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers=UA)
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:  # 逐级降级，最后统一报错
            last = f"{type(e).__name__}: {e}"
    return {"_error": last}


def yahoo(symbol):
    """Yahoo v8 chart 取最新价与日变动（必走代理）。"""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol) + "?range=5d&interval=1d")
    j = get(url, proxy=PROXY)
    try:
        meta = j["chart"]["result"][0]["meta"]
        px = round(float(meta["regularMarketPrice"]), 2)
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        return px, (round((px / float(prev) - 1) * 100, 2) if prev else None), "live"
    except Exception:
        return None, None, f"unavailable ({j.get('_error', 'parse')})"


def main():
    out = {}

    fng = get("https://api.alternative.me/fng/?limit=2")
    try:
        data = fng["data"]
        out["fng_now"] = data[0]["value"]
        out["fng_label"] = data[0]["value_classification"]
        out["fng_prev"] = data[1]["value"] if len(data) > 1 else None
        out["fng_src"] = "live"
    except Exception:
        out["fng_src"] = f"unavailable ({fng.get('_error', 'parse')})"

    for name, sym in (("spx", "^GSPC"), ("vix", "^VIX"), ("dxy", "DX-Y.NYB"),
                      ("gold", "GC=F"), ("tnx", "^TNX")):
        px, chg, src = yahoo(sym)
        if px is not None:
            out[name] = px
            if chg is not None:
                out[name + "_chg_pct"] = chg
        out[name + "_src"] = src

    cg = get("https://api.coingecko.com/api/v3/global")
    try:
        g = cg["data"]
        out["btc_dominance"] = round(g["market_cap_percentage"]["btc"], 2)
        out["total_mcap_chg24h"] = round(g["market_cap_change_percentage_24h_usd"], 2)
        out["cg_src"] = "live"
    except Exception:
        out["cg_src"] = f"unavailable ({cg.get('_error', 'parse')})"

    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
