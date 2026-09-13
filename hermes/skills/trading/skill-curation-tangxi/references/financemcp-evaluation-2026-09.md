# FinanceMCP 评估记录（2026-09-13 实测）

对象：[guangxiangdebizi/FinanceMCP](https://github.com/guangxiangdebizi/FinanceMCP)（750⭐，npm `finance-mcp` v4.11.2，TypeScript）

结论：**不装**。增量≈0，成本明确 —— 否决理由是「数据权限 + 增量重叠」，不是环境不兼容。

## 环境兼容性（已验，均通过）

| 项 | 结果 |
|---|---|
| Node | v22.22.3 ≥ 要求的 20 ✓ |
| npm registry | 可达，`finance-mcp@4.11.2` 存在 ✓ |
| stdio 握手 | 成功，`serverInfo = FinanceMCP v4.11.2` ✓ |

## 实测一：Tushare 积分门槛（决定性）

脚本：`scripts/maintenance/financemcp_tushare_probe.py`
用本机 `hermes/secrets/tushare_token.txt` 直打 23 个接口，**仅 7 个可用**。

| 分类 | 接口 |
|---|---|
| 可用（7） | `daily` `stk_mins` `index_daily` `cn_gdp` `cn_cpi` `shibor` `shibor_lpr` |
| 积分不足（16） | `moneyflow`(个股资金流) `moneyflow_hsgt`(北向) `margin_detail`(融资融券) `top_list`(龙虎榜) `block_trade`(大宗) `cb_daily`(可转债) `fund_nav` `fina_indicator` `hk_income` `us_income` `index_weight` `index_dailybasic` `fx_daily`(外汇日线) `fut_daily`(期货日线) `us_daily`(美股日线) `cn_m` `cn_ppi` `cn_pmi` |

关键点：**所有「能补系统缺口」的接口全部积分不足**；能打的 7 个里，A 股日线/分钟本系统早已接入
（`scripts/multi_source_collector.py::tushare_daily`）。它宣传的多资产行情（外汇/期货/美股日线）对我们全是空头承诺。

## 实测二：tools/list 的动态裁剪会造出「死工具」

脚本：`scripts/maintenance/financemcp_stdio_probe.py`

```bash
python scripts/maintenance/financemcp_stdio_probe.py              # 无凭证
python scripts/maintenance/financemcp_stdio_probe.py --with-token  # 注入本机 token
```

| 凭证状态 | tools/list 暴露数 |
|---|---|
| 无凭证 | 4（current_timestamp / finance_news / stock_data / stock_data_minutes） |
| 带本机 token | **17** |

裁剪逻辑只看 **凭证在不在**，不看 **积分够不够** → 装进来后 17 个工具里 13 个调用必失败。
这直接违反本系统「数据源失败必须可见、不拿降级冒充可用」的口径：工具目录里的死工具会污染工具选择。

## 与现有覆盖的重叠

| 能力 | 本系统现有 | FinanceMCP 对应 |
|---|---|---|
| 加密行情 | `binance` MCP（19 tools，实测通） | Binance 公开 K 线（仅 NONE 安全类型） |
| 美股/期权/宏观 | `financekit` MCP + FMP/AV/TwelveData/Massive | 需 Tushare 权限 → 积分不足 |
| 中文新闻/日历 | `jin10` MCP（8 tools）+ market-sentiment | 百度/Twingly/Qveris（后两者需付费 key） |
| A股行情 | 自有 `tushare_daily()` | 同样底层，无新增 |

## 唯一真实增量及其处理

**中国宏观序列**（`cn_gdp` / `cn_cpi` / `shibor` / `shibor_lpr`）在本机 token 下可打通，
而 `multi_source_collector.macro_overview()` 是**纯美国口径**（SPX/VIX/10Y/DXY/Gold），
全仓搜不到任何中国宏观字段（已 grep 确认）。

补法：~30 行 Python 挂进 `macro_overview`，走同一套 live/cache/stale_cache 降级契约。
**不值得为此常驻一个 Node MCP**（多养一份 npm 包版本 + 17 个工具目录，其中 13 个死）。

> 2026-09-13 用户决定：暂不做中国宏观接入（「算了」）。**勿主动重提**，除非用户问起或 Tushare 积分升档。

## 何时重评

Tushare 积分升到 2000+ 后必须重评 —— 届时 16 个受限接口会放开一大半（北向资金、融资融券、龙虎榜、财报）。
复跑：`python scripts/maintenance/financemcp_tushare_probe.py`
