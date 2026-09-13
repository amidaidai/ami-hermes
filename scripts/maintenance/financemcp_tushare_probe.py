"""FinanceMCP 选型探针：实测本机 Tushare token 对 FinanceMCP 各接口的权限等级。

FinanceMCP 19 个 tool 里 16 个依赖 Tushare，积分不足会返回"权限不足"而不是数据。
本脚本逐个打接口，把 可用/积分不足/参数错 分类，用于判断这个项目对棠溪是否有真实增量。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

SECRETS = Path("D:/Hermes agent/hermes/secrets")
TOKEN = (SECRETS / "tushare_token.txt").read_text(encoding="utf-8").strip()

# (tool 名, api_name, params) —— 覆盖 FinanceMCP 依赖 Tushare 的每个 tool
CASES = [
    ("stock_data(A股日线)",        "daily",            {"ts_code": "600519.SH", "limit": 2}),
    ("stock_data_minutes(分钟)",   "stk_mins",         {"ts_code": "600519.SH", "freq": "15min", "limit": 2}),
    ("index_data(指数)",           "index_daily",      {"ts_code": "000300.SH", "limit": 2}),
    ("index_data(估值)",           "index_dailybasic", {"ts_code": "000300.SH", "limit": 2}),
    ("macro_econ(GDP)",            "cn_gdp",           {"limit": 2}),
    ("macro_econ(CPI)",            "cn_cpi",           {"limit": 2}),
    ("macro_econ(PPI)",            "cn_ppi",           {"limit": 2}),
    ("macro_econ(PMI)",            "cn_pmi",           {"limit": 2}),
    ("macro_econ(Shibor)",         "shibor",           {"limit": 2}),
    ("macro_econ(LPR)",            "shibor_lpr",       {"limit": 2}),
    ("company_performance(A股)",   "fina_indicator",   {"ts_code": "600519.SH", "limit": 2}),
    ("company_performance_hk",     "hk_income",        {"ts_code": "00700.HK", "limit": 2}),
    ("company_performance_us",     "us_income",        {"ts_code": "AAPL", "limit": 2}),
    ("fund_data(净值)",            "fund_nav",         {"ts_code": "510300.SH", "limit": 2}),
    ("convertible_bond(可转债)",   "cb_daily",         {"ts_code": "113050.SH", "limit": 2}),
    ("block_trade(大宗交易)",      "block_trade",      {"ts_code": "600519.SH", "limit": 2}),
    ("money_flow(个股资金流)",     "moneyflow",        {"ts_code": "600519.SH", "limit": 2}),
    ("money_flow(北向/互联互通)",  "moneyflow_hsgt",   {"limit": 2}),
    ("margin_trade(融资融券)",     "margin_detail",    {"ts_code": "600519.SH", "limit": 2}),
    ("dragon_tiger(龙虎榜)",       "top_list",         {"trade_date": "20260911", "limit": 2}),
    ("csi_index_constituents",     "index_weight",     {"index_code": "000300.SH", "limit": 2}),
    ("futures_data(会员持仓)",     "fut_member_rank",  {"trade_date": "20260911", "limit": 2}),
    ("hot_news_7x24(新闻快讯)",    "news",             {"limit": 2}),
]


def call(api_name: str, params: dict) -> dict:
    body = json.dumps({"api_name": api_name, "token": TOKEN,
                       "params": params, "fields": ""}).encode()
    req = urllib.request.Request(
        "https://api.tushare.pro", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def classify(r: dict) -> tuple[str, str]:
    if r.get("code") != 0:
        msg = str(r.get("msg", ""))
        if "积分" in msg or "权限" in msg:
            return "积分/权限不足", msg[:70]
        return "接口错误", msg[:70]
    data = r.get("data") or {}
    items = data.get("items") or []
    if not items:
        return "无数据", f"fields={len(data.get('fields') or [])}"
    return "可用", f"{len(items)} 行 / {len(data.get('fields') or [])} 字段"


ok = []
print(f"token: {TOKEN[:6]}...{TOKEN[-4:]} (len={len(TOKEN)})\n")
for label, api, params in CASES:
    try:
        status, detail = classify(call(api, params))
    except Exception as exc:
        status, detail = "网络/异常", f"{type(exc).__name__}: {exc}"[:70]
    flag = {"可用": "OK ", "无数据": "0  "}.get(status, "XX ")
    print(f"{flag}{label:<30} {api:<20} {status:<10} {detail}")
    if status == "可用":
        ok.append(label)

print(f"\n可用 {len(ok)}/{len(CASES)}")
print("可用项:", "; ".join(ok))
