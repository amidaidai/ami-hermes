# 全周期BTC完整卡生产模板（2026-07-08实测）

当用户仅说"分析BTC"（无"卡呀/看看"快捷词、无周期特指）时，走全周期完整卡。本文件是 2026-07-08 三次实测跑通的生产版权威模板，配套 `tradingview-execution-card` SKILL.md 的「全周期BTC完整卡」节使用。

## 首屏版式（用户2026-07-06确认"差不多这个排版"）

```text
2026年7月8日07：27 · BTC

一、现在在哪：15m在VWAP下方窄幅震荡，夹在`63,461`与`63,746`之间，偏弱但未破位
二、现在怎么做：不追空也不追多，等`63,300`回踩守住做A，或跌破`62,638`才切B空

① 当前结构
② 多周期定位
③ 关键位矩阵
④ 多源验证
⑤ 执行方案
⑥ 最终裁决
```

## 六段 + 真Markdown表格（每段下接表，禁假表格/宽表>3列）

① 当前结构：侧重点标签 + 结构位 + 动作（如 `【当前】VWAP下沿 | 63,461 | 偏弱，等方向`）
② 多周期定位：周期 | SVP/副指标 | 裁决（D/4h/1h/15m/5m）
③ 关键位矩阵：方向 | 价位 | 用法（上方磁吸/近端阻力/中轴/破位警戒/下方支撑）
④ 多源验证：维度 | 数值 | 方向（Binance价/主动买卖/持仓/多空比/Funding/Depth/Deribit/链上/宏观/X情绪/恐惧贪婪）
⑤ 执行方案：方案 | 条件 | 执行（A主推·回踩多 / B备选·破位空 / X禁做）
⑥ 最终裁决：侧重点 | 结论（主线/转空/失效/评分/当前等级）

## 尾部强制：完整性审计表（15步管线）

| 步骤 | 状态 | 备注 |
|:---|:---:|:---|
| 1 TV健康 | ✅ | tv_launch后恢复 |
| 2 TV·D | ✅ | 日线OHLCV/主副指标 |
| 3 TV·4h | ✅ | 主副指标/关键位 |
| 4 TV·1h | ✅ | 主副指标/关键位 |
| 5 TV·15m | ✅ | 主副指标/截图 |
| 6 TV·5m | ✅ | 副指标/触发层 |
| 7 Binance | ✅ | 价格/K线/持仓/Funding/主动买卖/多空比 |
| 8 CG Pro | ✅ | 全球市值/BTC市占 |
| 9 宏观 | ✅ | SPX/DXY/VIX/XAU相关性 |
| 10 X情绪 | ✅ | x_search实时源 |
| 11 cron_read | ✅ | Deribit/Dune/x_sentiment |
| 12 CVD | ✅ | TV主副CVD |
| 13 Depth | ✅ | 盘口墙 |
| 14 Corr | ✅ | BTC-XAU/BTC-SPX |
| 15 Card | ✅ | RichMarkdown真表格已发 |

## 15步采集顺序（实测一次跑通，约4-5分钟）

1. `date '+%Y年%-m月%-d日%H：%M'` 取北京时间
2. `mcp_tradingview_tv_health_check`；若 `api_available:false` 或 symbol 非 BTC → `tv_launch(kill_existing=true)` 重建
3. `chart_set_symbol BINANCE:BTCUSDT.P` → 等8s → `chart_get_state` 确认 symbol 正确
4. 逐周期切换：`D → 4h → 1h → 15m → 5m`，每切一次 `sleep 5-8s` 等数据加载
5. 每周期读：`data_get_study_values` + `data_get_pine_tables(study_filter="SVP")` + `data_get_pine_tables(study_filter="Volume Aggregated")` + `data_get_pine_labels` + `data_get_pine_lines` + `data_get_ohlcv(count=80-90, summary=true)`
6. 15m/5m 切回后补 `data_get_pine_labels`/`data_get_pine_lines`（切换会丢）
7. `capture_screenshot(region="full")` @ 15m 与 5m 各一张
8. Binance 并行：`get_price` / `get_klines(15m,100)` / `get_open_interest_history(15m,5)` / `get_taker_volume(15m,5)` / `get_funding_rate_history` / `get_long_short_ratio(15m,3)` / `get_global_long_short(15m,3)`
9. `web_extract https://api.alternative.me/fng/` 恐惧贪婪
10. `scripts/coingecko_collector.py` 全球市值/BTC市占
11. `yfinance` 宏观：BTC-USD/GC=F/^GSPC/DX-Y.NYB/^VIX 日变 + 3月相关性
12. `x_search` 实时X情绪（query: `$BTC Bitcoin ... July 2026`）
13. `scripts/depth_wall.py BTCUSDT` 盘口墙
14. `read_file data/deribit_options.json` / `data/dune_cache.json` / `data/x_sentiment.json`
15. `write_file` 落盘 → `send_telegram_reliable('telegram:-1003733144325:386', text, parse_mode='RichMarkdown', timeout=20, retries=3, persist_on_fail=True)` 期望回执 `True rich_sent`

## R:R 计算（出卡前必跑）

```python
price=63632.01
entryA=63300; stopA=62630; t1=63800.07; t2=64234.1; t3=64691.9
for n,t in [('A_t1',t1),('A_t2',t2),('A_t3',t3)]: print(n, round((t-entryA)/(entryA-stopA),2))
entryB=62620; stopB=63150; bt1=61975.98; bt2=61297.0
for n,t in [('B_t1',bt1),('B_t2',bt2)]: print(n, round((entryB-t)/(stopB-entryB),2))
```

## 截图渲染铁律

`capture_screenshot` 存到 `D:\Hermes agent\tools\radingview-mcp\screenshots\` → 必须 `cp` 到 `C:/Users/Administrator/.hermes-web-ui/upload/default/` 再引用（D盘不渲染）。

## 双通道交付（防Telegram降级）

- 正式完整卡：仅 Bot API 10.1 RichMarkdown 发到话题 `-1003733144325:386`
- 普通 assistant 回复：只发 `MEDIA` 截图 + 一句裁决 + `rich_sent` 回执，**禁止**复制完整表格正文（否则降级成项目符号/假表格并重复）
