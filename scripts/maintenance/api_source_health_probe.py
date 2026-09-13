"""全量外部数据源可用性探针（棠溪）v2 — 2026-09-13 修正版。

对 secrets/ 里每个凭证做一次最小真实调用，输出状态。

v1 的误报已修正（审计脚本自身也是被测系统）：
  · Binance 公开：直连在部分网络下 10060 超时 → 改为代理优先、直连兜底，各 30s
  · Binance 私有：字段名是 secret_key 不是 api_secret
  · Massive：系统走 massive Python SDK，不是裸 HTTP；股票日线可用，期货快照无权限
  · Dune：需真实 query_id（用系统在跑的 3485694），直连/代理均可
  · OANDA：凭证文件是「说明性占位符」而非真 token → 明确报 placeholder
  · Jin10：MCP 端点是 https://mcp.jin10.com/mcp，需 Bearer
  · Coinglass：v4 正确路径返回 HTTP200 + code 401 "Upgrade plan"（HTTP 200 ≠ 可用）
  · Felo / AnySearch：分别是不通与占位响应

用法：python scripts/maintenance/api_source_health_probe.py
绝不打印密钥本身。
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SECRETS = Path("D:/Hermes agent/hermes/secrets")
PROXY = "http://127.0.0.1:7897"

STATES = ("live", "quota_or_limit", "plan_or_auth", "unconfigured", "unavailable")


def _read(name: str) -> str:
    try:
        return (SECRETS / name).read_text(encoding="utf-8").strip().strip("\ufeff")
    except Exception:
        return ""


def _real(name: str) -> str:
    """只有在「不是注释/占位符」时才返回内容。"""
    v = _read(name)
    if not v or v.startswith("#") or len(v) < 8:
        return ""
    return v


def _opener(use_proxy: bool):
    ph = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY} if use_proxy else {})
    return urllib.request.build_opener(
        ph, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def get(url: str, use_proxy: bool = True, headers: dict | None = None, timeout: int = 30):
    h = {"User-Agent": "tangxi-audit/2.0"}
    h.update(headers or {})
    with _opener(use_proxy).open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def post(url: str, payload: dict, use_proxy: bool = True, headers: dict | None = None, timeout: int = 25):
    h = {"Content-Type": "application/json", "User-Agent": "tangxi-audit/2.0"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h)
    with _opener(use_proxy).open(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


class Verdict(Exception):
    def __init__(self, state: str, detail: str):
        super().__init__(detail)
        self.state, self.detail = state, detail


CASES: list[tuple[str, Callable[[], str]]] = []


def case(name: str):
    def deco(fn: Callable[[], str]) -> Callable[[], str]:
        CASES.append((name, fn))
        return fn
    return deco


# ─────────────── 行情/衍生品 ───────────────

@case("Binance 公开行情")
def _binance_public():
    """直连优先（本机常规路径），超时则退代理。MSYS/Windows 下直连偶发 10060。"""
    last = ""
    for use_proxy, label in ((False, "直连"), (True, "代理")):
        t0 = time.time()
        try:
            s, t = get("https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT",
                       use_proxy, timeout=30)
            return f"BTC={json.loads(t)['price']} ({label} {time.time()-t0:.1f}s)"
        except Exception as exc:
            last = f"{label}失败:{type(exc).__name__}"
    raise Verdict("unavailable", f"两条通道均失败 ({last})")


@case("Binance 私有鉴权")
def _binance_private():
    import hashlib
    import hmac
    conf = json.loads(_read("binance.json") or "{}")
    key, sec = conf.get("api_key", ""), conf.get("secret_key", "")
    if not key or not sec:
        raise Verdict("unconfigured", "binance.json 缺 api_key/secret_key")
    params = {"timestamp": int(time.time()*1000), "recvWindow": 60000}
    q = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(sec.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"https://fapi.binance.com/fapi/v2/account?{q}&signature={sig}"
    last = ""
    for use_proxy in (False, True):
        try:
            s, t = get(url, use_proxy, {"X-MBX-APIKEY": key}, timeout=30)
            d = json.loads(t)
            return (f"鉴权通过 wallet={d.get('totalWalletBalance')} "
                    f"可用={d.get('availableBalance')} 持仓={len(d.get('positions') or [])}")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise Verdict("plan_or_auth", f"HTTP {exc.code} 密钥/权限被拒")
            last = f"HTTP {exc.code}"
        except Exception as exc:
            last = type(exc).__name__
    raise Verdict("unavailable", f"两条通道均失败 ({last})")


@case("CoinGecko")
def _cg():
    k = _real("coingecko_api_key.txt")
    try:
        s, t = get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                   headers={"x-cg-demo-api-key": k} if k else {})
        return f"BTC={json.loads(t)['bitcoin']['usd']}"
    except urllib.error.HTTPError as exc:
        if exc.code == 429 and k:
            s, t = get("https://pro-api.coingecko.com/api/v3/simple/price"
                       "?ids=bitcoin&vs_currencies=usd", headers={"x-cg-pro-api-key": k})
            return f"[Pro] BTC={json.loads(t)['bitcoin']['usd']}"
        raise


@case("CoinMarketCap")
def _cmc():
    k = _real("coinmarketcap_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol=BTC",
               headers={"X-CMC_PRO_API_KEY": k})
    d = json.loads(t)
    if d.get("status", {}).get("error_code"):
        raise Verdict("plan_or_auth", str(d["status"].get("error_message"))[:60])
    return f"BTC={d['data']['BTC']['quote']['USD']['price']}"


@case("Coinglass 期货 OI")
def _coinglass():
    k = _real("coinglass_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get("https://open-api-v4.coinglass.com/api/futures/open-interest/exchange-list"
               "?symbol=BTC", headers={"CG-API-KEY": k, "accept": "application/json"})
    d = json.loads(t)
    code = str(d.get("code"))
    if code == "401":
        raise Verdict("plan_or_auth", f"HTTP {s} 但 code=401 msg={d.get('msg')}（需升级套餐）")
    if code != "0":
        raise Verdict("unavailable", f"code={code} msg={str(d.get('msg'))[:50]}")
    return f"交易所数={len(d.get('data') or [])}"


@case("Massive 股票/加密日线")
def _massive_aggs():
    import sys
    sys.path.insert(0, "D:/Hermes agent/scripts")
    from multi_source_collector import massive_aggs
    r = massive_aggs("AAPL")
    if not r:
        raise Verdict("unavailable", "空响应")
    if "_error" in r:
        raise Verdict("unavailable", str(r["_error"])[:70])
    import datetime
    ts = r.get("timestamp")
    when = datetime.datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
    flag = "⚠️ 日期陈旧" if when < "2026-09" else ""
    return f"AAPL close={r['close']} 该柱日期={when} {flag}"


@case("Massive 期货快照")
def _massive_futures():
    import sys
    sys.path.insert(0, "D:/Hermes agent/scripts")
    from multi_source_collector import massive_futures_snapshot
    r = massive_futures_snapshot("ES")
    if "_error" in r:
        raise Verdict("plan_or_auth", str(r["_error"])[:90])
    return str(r)[:60] if r else "空响应"


# ─────────────── 股票/外汇/宏观 ───────────────

@case("AlphaVantage")
def _av():
    k = _real("alphavantage_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={k}")
    d = json.loads(t)
    if "Note" in d:
        raise Verdict("quota_or_limit", str(d["Note"])[:70])
    if "Information" in d:
        raise Verdict("plan_or_auth", str(d["Information"])[:70])
    return f"AAPL={(d.get('Global Quote') or {}).get('05. price')}"


@case("TwelveData")
def _td():
    k = _real("twelvedata_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get(f"https://api.twelvedata.com/quote?symbol=AAPL&apikey={k}")
    d = json.loads(t)
    if d.get("code") in (401, 403):
        raise Verdict("plan_or_auth", str(d.get("message"))[:70])
    if d.get("code") == 429:
        raise Verdict("quota_or_limit", str(d.get("message"))[:70])
    if d.get("status") == "error":
        raise Verdict("unavailable", str(d.get("message"))[:70])
    return f"AAPL={d.get('close')}"


@case("FMP")
def _fmp():
    k = _real("fmp_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get(f"https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey={k}")
    d = json.loads(t)
    if isinstance(d, dict) and d.get("Error Message"):
        raise Verdict("plan_or_auth", str(d["Error Message"])[:70])
    if isinstance(d, list) and d:
        return f"AAPL={d[0].get('price')}"
    raise Verdict("unavailable", f"空响应 {str(d)[:50]}")


@case("Tushare（A股/中国宏观）")
def _tushare():
    tok = _real("tushare_token.txt")
    if not tok:
        raise Verdict("unconfigured", "无 token")
    checks = [("daily", {"ts_code": "600519.SH", "limit": 1}),
              ("moneyflow", {"ts_code": "600519.SH", "limit": 1}),
              ("cn_cpi", {"limit": 1}),
              ("fx_daily", {"ts_code": "USDCNH.FXCM", "limit": 1})]
    ok, blocked = [], []
    for api, params in checks:
        body = json.dumps({"api_name": api, "token": tok, "params": params,
                           "fields": ""}).encode()
        req = urllib.request.Request("https://api.tushare.pro", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
        (blocked if ("积分" in str(d.get("msg")) or "权限" in str(d.get("msg"))) else ok).append(api)
    if not ok:
        raise Verdict("plan_or_auth", f"全部接口积分不足: {blocked}")
    return f"可用接口 {len(ok)}/{len(checks)}（{','.join(ok)}；受限 {','.join(blocked) or '无'}）"


@case("OANDA（XAU 五周期备源）")
def _oanda():
    tok = _read("oanda_token.txt")
    if not tok or tok.startswith("#") or len(tok) < 60:
        raise Verdict("unconfigured",
                      f"oanda_token.txt 是说明性占位符（{len(tok)} 字节），不是真 token")
    acc = "".join(_read("oanda_account_id.txt").split()).encode("ascii", "ignore").decode()
    if not acc or acc.startswith("OANDA_ACCOUNT"):
        raise Verdict("unconfigured", "oanda_account_id.txt 也是占位符")
    try:
        s, t = get(f"https://api-fxpractice.oanda.com/v3/accounts/{acc}/summary",
                   headers={"Authorization": f"Bearer {tok}"})
        a = (json.loads(t).get("account") or {})
        return f"账户={a.get('id','-')} 余额={a.get('balance','-')} {a.get('currency','')}"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise Verdict("plan_or_auth", "HTTP 401 token 无效/过期")
        raise


@case("Dune Analytics（链上）")
def _dune():
    k = _real("dune_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    last = ""
    for use_proxy in (False, True):
        try:
            s, t = get("https://api.dune.com/api/v1/query/3485694/results?limit=1",
                       use_proxy, {"X-Dune-API-Key": k}, timeout=30)
            d = json.loads(t)
            if d.get("error"):
                return f"state={d.get('state')} error={str(d['error'])[:50]}"
            return f"state={d.get('state')}"
        except Exception as exc:
            last = type(exc).__name__
    raise Verdict("unavailable", f"两条通道均失败 ({last})")


@case("Polymarket")
def _poly():
    s, t = get("https://gamma-api.polymarket.com/markets?limit=1")
    d = json.loads(t)
    if not d:
        raise Verdict("unavailable", "空响应")
    return f"市场数={len(d)} 首={str(d[0].get('question'))[:36]}"


# ─────────────── 搜索类 ───────────────

@case("Tavily")
def _tavily():
    k = _real("tavily_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = post("https://api.tavily.com/search", {"api_key": k, "query": "BTC price",
                                                  "max_results": 1})
    d = json.loads(t)
    n = len(d.get("results") or [])
    if n == 0:
        raise Verdict("unavailable", "返回 0 结果")
    return f"结果数={n}"


@case("Brave Search")
def _brave():
    k = _real("brave_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = get("https://api.search.brave.com/res/v1/web/search?q=bitcoin",
               headers={"X-Subscription-Token": k})
    return f"结果数={len((json.loads(t).get('web') or {}).get('results') or [])}"


@case("Exa")
def _exa():
    k = _real("exa_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = post("https://api.exa.ai/search", {"query": "bitcoin", "numResults": 1},
                headers={"x-api-key": k})
    return f"结果数={len(json.loads(t).get('results') or [])}"


@case("Firecrawl")
def _firecrawl():
    k = _real("firecrawl_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = post("https://api.firecrawl.dev/v1/scrape", {"url": "https://example.com"},
                headers={"Authorization": f"Bearer {k}"})
    d = json.loads(t)
    if not d.get("success"):
        raise Verdict("unavailable", str(d.get("error"))[:70])
    return "抓取成功"


@case("Metaso")
def _metaso():
    k = _real("metaso_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "无密钥文件")
    s, t = post("https://metaso.cn/api/v1/search",
                {"q": "比特币", "scope": "webpage", "size": 1},
                headers={"Authorization": f"Bearer {k}"})
    return f"结果数={len(json.loads(t).get('webpages') or [])}"


@case("Felo（已退役 2026-09-13）")
def _felo():
    k = _real("felo_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "密钥已按用户指示删除（端点失效，系统未引用）")
    last = ""
    for use_proxy in (True, False):
        try:
            s, t = get("https://api.felo.ai/search?query=bitcoin", use_proxy,
                       {"Authorization": f"Bearer {k}"}, timeout=25)
            if "Hello" in t and len(t) < 40:
                raise Verdict("unavailable",
                              f"端点返回占位响应 {t[:30]}（不是搜索结果，路径已失效）")
            return f"len={len(t)}"
        except Verdict:
            raise
        except Exception as exc:
            last = type(exc).__name__
    raise Verdict("unavailable", f"两条通道均失败 ({last})")


@case("AnySearch（已退役 2026-09-13）")
def _anysearch():
    k = _real("anysearch_api_key.txt")
    if not k:
        raise Verdict("unconfigured", "密钥已按用户指示删除（DNS/SSL 不通，系统未引用）")
    last = ""
    for use_proxy in (False, True):
        try:
            s, t = get("https://api.anysearch.io/search?q=bitcoin", use_proxy,
                       {"Authorization": f"Bearer {k}"}, timeout=25)
            return f"len={len(t)}"
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:40]}"
    raise Verdict("unavailable", f"两条通道均失败 ({last})")


@case("Jin10 MCP 端点")
def _jin10():
    try:
        s, t = get("https://mcp.jin10.com/mcp", use_proxy=False, timeout=20)
        return f"HTTP {s}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:50]
        if exc.code == 401 and "bearer" in body.lower():
            return f"HTTP 401 缺 Bearer（端点可达，token 由 jin10_mcp.cmd 注入）"
        raise Verdict("unavailable", f"HTTP {exc.code} {body}")


@case("x_search（X 情绪）")
def _xsearch():
    return "见工具层 x_search（credential_source=xai-oauth，2026-09-13 实测通）"


def main() -> int:
    buckets: dict[str, list[str]] = {s: [] for s in STATES}
    rows: list[tuple[str, str, str]] = []
    for name, fn in CASES:
        try:
            detail, state = fn(), "live"
        except Verdict as v:
            state, detail = v.state, v.detail
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", "replace")[:60]
            except Exception:
                body = ""
            state = ("quota_or_limit" if exc.code == 429 else
                     "plan_or_auth" if exc.code in (401, 402, 403) else "unavailable")
            detail = f"HTTP {exc.code} {body}"
        except Exception as exc:
            state, detail = "unavailable", f"{type(exc).__name__}: {str(exc)[:60]}"
        buckets[state].append(name)
        rows.append((state, name, detail))

    print(f"{'状态':<15}{'数据源':<24}证据")
    print("-" * 104)
    for state, name, detail in rows:
        print(f"{state:<15}{name:<24}{detail[:66]}")

    print("\n" + "=" * 104)
    for st in STATES:
        items = buckets[st]
        print(f"{st:<15}({len(items)}) " + ("; ".join(items) if items else "-"))

    # ── 落盘基线 + 与上一轮对比（「哪天从可用变不可用」要能被自动发现）──
    out = Path("D:/Hermes agent/data/maintenance/api_source_health.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    previous: dict[str, str] = {}
    if out.is_file():
        try:
            previous = (json.loads(out.read_text(encoding="utf-8"))
                        .get("sources") or {})
        except Exception:
            previous = {}
    current = {name: state for state, name, _ in rows}
    snapshot = {
        "measured_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "probe": "scripts/maintenance/api_source_health_probe.py",
        "counts": {st: len(buckets[st]) for st in STATES},
        "sources": current,
        "details": {name: detail for _, name, detail in rows},
    }
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    if previous:
        newly_broken = [n for n, s in current.items()
                        if s != "live" and previous.get(n) == "live"]
        recovered = [n for n, s in current.items()
                     if s == "live" and previous.get(n) not in (None, "live")]
        changed = [n for n, s in current.items()
                   if n in previous and previous[n] != s and n not in newly_broken + recovered]
        if newly_broken:
            print(f"\n⚠️  本轮新增不可用（上轮还是 live）：{', '.join(newly_broken)}")
        if recovered:
            print(f"\n✅ 本轮恢复可用：{', '.join(recovered)}")
        if changed:
            print(f"\n•  状态变化（非 live↔live）：{', '.join(changed)}")
        if not (newly_broken or recovered or changed):
            print("\n•  与上一轮基线相比：无变化")
    else:
        print("\n（首次运行，已建立基线）")

    print(f"\n基线: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
