#!/usr/bin/env python3
"""CoinGlass 网页端公开接口读取器（清算热力图）—— 无需 API key、无需登录。

为什么存在这个模块
------------------
CoinGlass 官方 API 需要付费档：本仓库 `hermes/secrets/coinglass_api_key.txt` 用
正确的 `CG-API-KEY` 头鉴权仍返回 `401 Upgrade plan`（2026-09-15 实测全部端点），
而网页端 pro 图表所用的公开接口 `capi.coinglass.com` 没有账号门槛，只是加了一层
前端握手 + 双层 AES/gzip 包装。本模块复刻该流程，用于读取清算热力图这类
衍生品聚合数据，作为分析的**交叉验证源**。

协议（全部由前端打包产物实测反推）
--------------------------------------------
1. 请求参数 `data` = AES-ECB(base64, key=ASCII "1f68efd73f8d4921acc0dead41dd39bc",
   明文 "<unix秒>,<TOTP>")，TOTP = base32("I65VU7K5ZQL7WB4E") / step 30 / 6 位 / SHA1。
2. 响应头 `user` = 第二层密钥的密文；body.data = 真 JSON 的密文，都是
   AES-ECB(key) → gzip 包装后的 base64。
3. **key1 按响应头 `v` 分支派生**（2026-09-16 换代；旧实现的 key1 恒为
   base64(路径前 12 字符)，只对应下面的 v=1 支）：
     v="1"      → base64(路径前 12 字符)
     v="0"/"2"  → base64(我方请求头 cache-ts-v2 的值)[:16]
     v="55"/"66"/"77" → 三个**固定常量**各自 base64 后取前 16 字符
   key1 统一截断到 16 字符（前端响应管线第一步 `substring(0,16)`）；
   用 key1 解 `user` 头 → gzip → 得到 key2（16 字符 hex 串）→ 用 key2 解 body.data。
4. 服务器在这几个分支间**随机**分发（实测 20 次：55×8 / 77×7 / 66×5），
   只覆盖其中一支必然时好时坏 —— 因此本模块覆盖全部已知分支，未知 v 显式报错。

还原方法（可复现，2026-09-16）
--------------------------------------------
`https://s3.coinglass.com/v1/cg/_next/static/chunks/pages/_app-*.js` 是混淆产物：
字符串表 `function In(){var t=[...]}` / `function mn(){...}` 会在模块加载时被
自带校验式 `n.push(n.shift())` **轮转**，所以直接照抄数组逐个取值会全部解错 ——
必须把「数组 + 解码器(Mn/gn) + 两段轮转 IIFE」整段原样执行，才能得到正确的
token（步骤序、固定常量、方法名）。步骤序实测：
响应管线 `2|5|1|4|3|0|6`（wn 取路径 → vn 派生 key1 → 截断 16 → 解 user →解 body）。

数据口径
--------
`liq` 行 = `[时间桶索引, 价位桶索引, 清算强度]`；`y[i]` 是价位桶 i 的价格；
`prices` 是 288 根 5m K 线（24h）。按价位桶聚合第 3 列即「该价位附近 24h 的清算堆积强度」。

**强度不是 USD**：实测全量求和 ≈ 866 亿，而 CoinGlass 首页公布的同口径 24h 爆仓额
只有数亿，两者量级不符，说明第 3 列是杠杆加权的相对刻度。因此本模块只输出
强度值与占总强度的百分比，**不得当美元金额引用**。

覆盖范围（2026-09-15 实测）
--------------------------
`Binance_BTCUSDT` 匿名可用（v2/v5 两个接口都通）；**其它品种（ETH、OKX_* 等）
匿名请求返回 `code=40000`** —— 浏览器匿名会话拿到的是同一个 40000，即该数据在
CoinGlass 侧按登录/档位门控，不是本模块的参数问题。此类情况按 `unavailable`
返回并带上服务端 code，不伪造数据。

风险提示
--------
这是网页私有实现，CoinGlass 改前端即失效；失效时返回 `status="unavailable"`，
不做静默降级、不拿旧值冒充实时。仅用于人工分析，不接自动下单。
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.parse
import urllib.request
import zlib
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SOURCE = "coinglass_web"
BASE = "https://capi.coinglass.com"

# 前端常量（来自其 webpack 打包产物）
_PARAM_KEY = b"1f68efd73f8d4921acc0dead41dd39bc"
_OTP_SECRET_B32 = "I65VU7K5ZQL7WB4E"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_REFERER = "https://www.coinglass.com/zh/pro/futures/LiquidationHeatMap"

HEATMAP_PATH = "/api/index/v5/liqHeatMap"


def _opener():
    """沿用仓库约定：Hermes 环境带 HTTPS_PROXY 时走系统代理，否则直连。"""
    if os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"):
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def totp(t: int, step: int = 30, digits: int = 6) -> str:
    """RFC6238 TOTP；密钥是 base32 解码后的字节（与前端 authenticator.generate 一致）。"""
    key = base64.b32decode(_OTP_SECRET_B32)
    digest = hmac.new(key, struct.pack(">Q", int(t // step)), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def param_key_for_path(path: str) -> str:
    """v=1 分支的 key1 = base64(接口路径前 12 字符)，即响应头 `user` 的解密密钥。"""
    return base64.b64encode(path[0:12].encode()).decode()


# v=55/66/77 三个分支的 key1 原料（远端前端固定常量，2026-09-16 从混淆字符串表还原）。
# 服务器在这三个分支间随机分发，所以只覆盖其中一个必然时好时坏 —— 三个都要有。
FIXED_KEY_MATERIAL = {
    "55": "170b070da9654622",
    "66": "d6537d845a964081",
    "77": "863f08689c97435b",
}


def response_key1(headers: dict[str, str], path: str, cache_ts: str) -> str:
    """按响应头 ``v`` 分支派生 key1（长度截断到 16 字符）。

    远端 2026-09-16 起在响应头里带 ``v``（实测取值 55/66/77，随机），
    key1 原料随之改写（自前端 bundle 还原，步骤序 ``4|2|0|5|3|1|7|6``）：
      v="1" → 请求路径；v="0"/"2" → 请求头 cache-ts-v2；v∈{55,66,77} → 固定常量。
    随后响应管线第一步 ``substring(0,16)`` 把 key1 截断（v=1 时等价于旧的
    base64(path[:12])，所以旧实现在 v=1 上依旧成立）。
    """
    v = str(headers.get("v") or "")
    if v in FIXED_KEY_MATERIAL:
        material = FIXED_KEY_MATERIAL[v]
    elif v == "1":
        return param_key_for_path(path)          # 旧口径，16 字符，无需截断
    elif v in ("0", "2"):
        material = cache_ts
    else:
        raise ValueError(f"未覆盖的响应头 v={v!r}：CoinGlass 又改了 key 派生（需重新还原前端）")
    return base64.b64encode(material.encode()).decode()[:16]



def make_param_token(now: int | None = None) -> str:
    """生成请求参数 `data`（AES-ECB / PKCS7；对端协议要求 ECB，非我方新设计）。"""
    ts = int(now if now is not None else time.time())
    plain = f"{ts},{totp(ts)}".encode()
    plain += bytes([16 - len(plain) % 16]) * (16 - len(plain) % 16)
    enc = Cipher(algorithms.AES(_PARAM_KEY), modes.ECB()).encryptor()
    return base64.b64encode(enc.update(plain) + enc.finalize()).decode()


def aes_gzip_decrypt(b64_text: str, key: str | bytes) -> bytes:
    """AES-ECB 解密 + gzip 解压；尾部 PKCS7 填充由 zlib 流式解压自然截断。"""
    key_bytes = key.encode() if isinstance(key, str) else key
    raw = base64.b64decode(b64_text)
    dec = Cipher(algorithms.AES(key_bytes), modes.ECB()).decryptor()
    out = dec.update(raw) + dec.finalize()
    if out[:2] != b"\x1f\x8b":
        raise ValueError("响应不是 gzip 密文：协议可能已变更")
    return zlib.decompressobj(31).decompress(out)


def _unwrap(path: str, body: dict[str, Any], headers: dict[str, str], cache_ts: str = "") -> Any:
    if str(body.get("code")) != "0":
        raise ValueError(f"接口返回异常：code={body.get('code')} msg={body.get('msg')}")
    payload = body.get("data")
    if not isinstance(payload, str):
        # 少数接口（如 /api/v2/support/symbol）直接返回明文，不加密
        return payload
    header_key = headers.get("user") or headers.get("User")
    if not header_key:
        raise ValueError("缺少 `user` 响应头（握手失败）")
    key1 = response_key1(headers, path, cache_ts)
    key2 = aes_gzip_decrypt(header_key, key1).decode("utf-8", "replace")[:16]
    plain = aes_gzip_decrypt(payload, key2)
    try:
        return json.loads(plain.decode())
    except Exception:
        return plain.decode("utf-8", "replace")


def fetch_json(path: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    """按 CoinGlass 网页端协议取一个接口的明文 JSON。"""
    query = dict(params or {})
    query["data"] = make_param_token()
    cache_ts = str(int(time.time() * 1000))
    url = BASE + path + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={
        "accept": "application/json",
        "language": "zh",
        "encryption": "true",
        "cache-ts-v2": cache_ts,
        "origin": "https://www.coinglass.com",
        "referer": _REFERER,
        "User-Agent": _UA,
    })
    with _opener().open(req, timeout=timeout) as resp:
        headers = dict(resp.headers)
        body = json.loads(resp.read().decode("utf-8", "replace"))
    # cache_ts 必须传进去：v∈{0,2} 分支的 key1 原料就是它（我方生成，已知）
    return _unwrap(path, body, headers, cache_ts)


def fetch_heatmap(symbol: str = "Binance_BTCUSDT", interval: int = 5, limit: int = 288,
                  timeout: int = 30) -> dict[str, Any]:
    """读取清算热力图。返回 {status, source, fetched_at, data, error}。

    status: live（拿到完整数据）/ unavailable（协议变更、网络或接口异常）
    """
    out: dict[str, Any] = {"source": SOURCE, "symbol": symbol, "fetched_at": int(time.time())}
    try:
        payload = fetch_json(HEATMAP_PATH,
                             {"merge": "true", "symbol": symbol,
                              "interval": int(interval), "limit": int(limit)},
                             timeout=timeout)
    except Exception as exc:
        out.update(status="unavailable", data=None, error=f"{type(exc).__name__}: {exc}")
        return out
    if not isinstance(payload, dict) or "liq" not in payload:
        out.update(status="unavailable", data=None, error="返回结构不含 liq 字段")
        return out
    out.update(status="live", data=payload, error=None)
    return out


def price_bins(payload: dict[str, Any]) -> list[float]:
    """价位桶中心价（y 是桶下沿，按等间距取中心）。"""
    y = payload.get("y") or []
    if len(y) < 2:
        return [float(v) for v in y]
    step = float(y[1]) - float(y[0])
    return [float(v) + step / 2 for v in y]


def liquidation_by_level(payload: dict[str, Any]) -> list[tuple[float, float]]:
    """按价位桶聚合清算名义金额，返回 [(价位, 累计USD), ...]，按价位升序。"""
    centers = price_bins(payload)
    totals: dict[int, float] = {}
    for row in payload.get("liq") or []:
        if len(row) < 3:
            continue
        try:
            level_idx = int(row[1])
            notional = float(row[2])
        except (TypeError, ValueError):
            continue
        totals[level_idx] = totals.get(level_idx, 0.0) + notional
    return [(centers[i], totals[i]) for i in sorted(totals) if i < len(centers)]


def spot_price(payload: dict[str, Any]) -> float | None:
    """最新 5m 收盘价（prices 行 = [ts, o, h, l, c, vol]）。"""
    rows = payload.get("prices") or []
    if not rows:
        return None
    try:
        return float(rows[-1][4])
    except (TypeError, ValueError, IndexError):
        return None


def top_liquidation_levels(payload: dict[str, Any], top: int = 8,
                           min_gap_pct: float = 0.4) -> list[dict[str, Any]]:
    """清算堆积最强的价位（相邻价位做最小间距去重，避免同一个簇刷屏）。

    `intensity` 是 CoinGlass 的相对刻度，不是 USD；`share_pct` = 该价位强度 / 全价位总强度。
    """
    spot = spot_price(payload)
    levels = liquidation_by_level(payload)
    grand_total = sum(v for _, v in levels) or 1.0
    ranked = sorted(levels, key=lambda kv: -kv[1])
    picked: list[dict[str, Any]] = []
    for price, intensity in ranked:
        if spot and any(abs(price - p["price"]) / spot * 100 < min_gap_pct for p in picked):
            continue
        picked.append({
            "price": round(price, 1),
            "intensity": round(intensity, 2),
            "share_pct": round(intensity / grand_total * 100, 3),
            "side": "上方" if (spot is None or price > spot) else "下方",
            "distance_pct": round((price - spot) / spot * 100, 2) if spot else None,
        })
        if len(picked) >= top:
            break
    return picked


def summarize(payload: dict[str, Any], top: int = 8) -> str:
    inst = payload.get("instrument") or {}
    spot = spot_price(payload)
    lines = [
        f"CoinGlass 清算热力图 · {inst.get('exName','?')} {inst.get('instrumentId','?')}"
        f" · 桶 {inst.get('priceTick','?')} · 现价 {spot:,.1f}" if spot else "现价未知",
        f"价位区间 {payload.get('rangeLow')} ~ {payload.get('rangeHigh')}"
        f" · 更新于 {time.strftime('%Y-%m-%d %H:%M', time.localtime((payload.get('updateTime') or 0)/1000))}",
        "强度为 CoinGlass 相对刻度（非 USD）",
        "",
        "清算堆积最强价位（24h 累计）：",
    ]
    for i, lv in enumerate(top_liquidation_levels(payload, top=top), 1):
        dist = f"{lv['distance_pct']:+.2f}%" if lv["distance_pct"] is not None else "n/a"
        lines.append(f"  {i:>2}. {lv['price']:>9,.1f}  强度 {lv['intensity']:>12,.0f}"
                     f"  占比 {lv['share_pct']:>5.2f}%  {lv['side']}  {dist}")
    return "\n".join(lines)


# ── 缓存（供卡面渲染路径读取，避免渲染时打网络）─────────────────────────────
CACHE_MAX_AGE_S = 600          # 超过 10 分钟即视为陈旧，卡面必须显示「陈旧」而不是照抄
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_REPO_ROOT, "data", "coinglass_liq.json")


def refresh_cache(symbol: str = "Binance_BTCUSDT", interval: int = 5, limit: int = 288,
                  cache_path: str | None = None) -> dict[str, Any]:
    """抓一次热力图并落盘（含失败态），供卡面渲染只读缓存。"""
    res = fetch_heatmap(symbol, interval, limit)
    record = {
        "source": SOURCE,
        "symbol": res["symbol"],
        "status": res["status"],
        "fetched_at": res["fetched_at"],
        # 数据新鲜度看门狗只认 TIMESTAMP_KEYS（updated_epoch/updated_at/ts…），
        # 不认 fetched_at；缺它会把这套缓存判成「无显式时间戳」而误报。
        "updated_epoch": res["fetched_at"],
        "error": res["error"],
        "spot": None,
        "top": [],
        "intensity_note": "强度为 CoinGlass 相对刻度，非 USD",
    }
    if res["status"] == "live":
        record["spot"] = spot_price(res["data"])
        record["top"] = top_liquidation_levels(res["data"], top=8, min_gap_pct=0.4)
        record["updated_at"] = res["data"].get("updateTime")
    path = cache_path or CACHE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return record


def liquidation_band_text(symbol: str = "BTCUSDT", cache_path: str | None = None,
                          max_age_s: int = CACHE_MAX_AGE_S) -> str:
    """卡面用的短句：清算堆积最近的上/下两个价位。

    只认 `Binance_BTCUSDT`（该品种匿名可读）。状态三态可见，不拿旧值冒充实时：
      新鲜 → `清算带 上77,492(+0.77%)/下75,303(-2.08%)`
      陈旧 → `清算带 陈旧(需刷新)`
      不可用 → `清算带 不可用`
      非 BTC → 空串（不占位）
    """
    su = str(symbol or "").upper().replace("/", "").replace("-", "")
    if su not in ("BTCUSDT", "BTCUSD", "BTC") and "BTC" not in su:
        return ""
    path = cache_path or CACHE_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception:
        return "清算带 不可用"
    if not isinstance(rec, dict):
        return "清算带 不可用"
    age = time.time() - float(rec.get("fetched_at") or 0)
    if age > max_age_s:
        return "清算带 陈旧(需刷新)"
    if rec.get("status") != "live" or not rec.get("top"):
        return "清算带 不可用"
    spot = rec.get("spot") or 0
    # 取**距现价最近**的上/下堆积位（缓存池 top8），而不是强度榜前两名：
    # 卡面要回答的是「价格摸到哪儿会撞上清算」，不是「哪一档最厚」。
    above = min((x for x in rec["top"] if spot and x["price"] > spot),
                key=lambda x: x["distance_pct"], default=None)
    below = max((x for x in rec["top"] if spot and x["price"] < spot),
                key=lambda x: x["distance_pct"], default=None)
    bits = []
    if above:
        bits.append(f"上{above['price']:,.0f}({above['distance_pct']:+.2f}%)")
    if below:
        bits.append(f"下{below['price']:,.0f}({below['distance_pct']:+.2f}%)")
    if not bits:
        return "清算带 不可用"
    return "清算带 " + "/".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser(description="读取 CoinGlass 网页端清算热力图（免 key / 免登录）")
    ap.add_argument("--symbol", default="Binance_BTCUSDT", help="例 Binance_BTCUSDT / Binance_ETHUSDT")
    ap.add_argument("--interval", type=int, default=5, help="K 线桶（分钟），默认 5")
    ap.add_argument("--limit", type=int, default=288, help="桶数量，默认 288 = 24h")
    ap.add_argument("--top", type=int, default=8, help="输出清算最密集的价位个数")
    ap.add_argument("--json-out", default=None, help="把原始 JSON 落盘（调试用）")
    ap.add_argument("--refresh-cache", action="store_true",
                    help="刷新卡面缓存 data/coinglass_liq.json 并打印卡面短句")
    args = ap.parse_args()

    if args.refresh_cache:
        rec = refresh_cache(args.symbol)
        print(f"[{rec['status']}] CoinGlass 缓存已刷新 · spot={rec.get('spot')} "
              f"top={len(rec.get('top') or [])} · {CACHE_PATH}")
        print(liquidation_band_text("BTCUSDT"))
        return 0 if rec["status"] == "live" else 1

    res = fetch_heatmap(args.symbol, args.interval, args.limit)
    if res["status"] != "live":
        print(f"[{res['status']}] {res['symbol']}: {res['error']}")
        return 1
    print(summarize(res["data"], top=args.top))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(res["data"], fh, ensure_ascii=False)
        print(f"\n原始 JSON 已写入 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
