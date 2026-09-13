# 卡面数值反查清单

来源：2026-09-13 的 BTC「分析BTC」完整档会话（仓库 `D:/Hermes agent`）。
`auto_card` 产出的卡面里，凡是由缓存/辅助源填充的行都可能带错值且**不报错** ——
它们被标成 `cache·—` / `仅展示/辅助` 就混过去了。出卡前必须对**能独立重算的行**反查，
不一致就以重算值为准，并把卡面值明确标为失效（而不是静默替换）。

## 1. corr 行：卡面 `相关0.0` 是坏的，要重算

实测卡面输出（高级订单流段）：

```
跨市场：BTC×XAU相关0.0·独立/弱相关·BTC+XAU独立运行·可同时持仓·各走各的风险预算
```

同轮 `多源验证` 表里该行标为 `跨资产相关性 | cache·— | 仅展示/辅助`。
yfinance 重算（period=3mo，日收益）结果完全不同：

| 配对 | 3mo corr | 20d corr |
|:---|:---:|:---:|
| BTC-GOLD | **0.65** | **0.85** |
| BTC-SPX | 0.27 | 0.36 |
| BTC-DXY | -0.46 | — |
| BTC-VIX | -0.27 | — |

**结论**：`0.0` 与 `独立运行/可同时持仓` 的派生结论整条作废。写卡时把重算值放进多源表，
并在失效源行里点名「卡面 corr 失效 → 已用 yfinance 重算」。
不要因为卡面给了数就直接引用 —— 一个 0.0 会连带推翻「组合风险乘数」那一整段推理。

重算探针：

```python
import yfinance as yf
d = yf.download(['BTC-USD','GC=F','^GSPC','DX-Y.NYB','^VIX'],
                period='3mo', interval='1d', progress=False)['Close'].dropna()
c = d.pct_change().dropna()
print(c.corr().round(2))
print('20d BTC-XAU', round(c['BTC-USD'].tail(20).corr(c['GC=F'].tail(20)), 2))
```

## 2. `data/x_sentiment_context.json`：mtime 新鲜 ≠ 内容新鲜

实测（2026-09-13 18:1x，文件 mtime 仅 333min）：

| 段落 | 文件内值 | 本轮独立源 | 判定 |
|:---|:---|:---|:---|
| `fear_greed.value` | 61 (Greed) | alternative.me `/fng/` = 61 | ✅ 一致，可采用 |
| `global_market.btc_dominance` | 58.73% | CoinGecko 本轮 56.1% | ⚠️ 冲突，不用 |
| `market_snapshot[BTCUSDT].price` | **64,658** | Binance live **76,802** | ❌ 差约 16%，段落作废 |
| `market_snapshot[BTCUSDT].chg_24h_pct` | +3.49% | CoinGecko 总市值日变 -3.49% | ❌ 方向相反 |

那个 `market_snapshot` 段明显是更早某个时点写入后没再更新的残留 —— 文件被部分刷新，
不是整体过期，所以「按文件龄判断」放行了坏数据。

**规则**：对该文件的每个数值段分别核对量级与方向；任一段不通过就**整段丢弃**并注册 `stale_cache`，
不要因为别段对就把整份文件标 ✅。恐贪这种能独立重算的字段优先现场取 `https://api.alternative.me/fng/?limit=3`。

## 3. 其他可独立重算的探针（廉价、优先用）

- 恐贪：`curl -s "https://api.alternative.me/fng/?limit=3"`
- 盘口买卖比（卡面 Depth 行的复核）：
  ```bash
  curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=20"
  ```
  取前 5 档 `price*qty` 求和算 bid/ask 比；实测 2.21 = 下方买墙偏厚。
- 宏观（FinanceKit `market_overview` 返回 `Data unavailable` 时不要留空）：yfinance
  拉 `BTC-USD / GC=F / ^GSPC / DX-Y.NYB / ^VIX / CL=F` 的日变与相关性。

## 4. 完整档实跑耗时与审计典型形状

- **耗时不是 2-3 分钟**：2026-09-13 实测 `auto_card ... --mode-auto --message "分析 BTCUSDT"`
  在 52s 内跑完 15 步（`status: exited`, `uptime_seconds: 52`）。后台 + wait 即可，不必按 3 分钟预留，
  但也别改成前台阻塞 —— 慢的时候仍会到分钟级。
- **完成度 14/15 是正常形状**：唯一 ⚠️ 是 `Cron缓存` 行，它逐源列出
  `dune_cache(stale_cache)` / `deribit_options(unavailable)` / `x_sentiment(stale_cache)` /
  `qlib_factors(stale_cache)` / `liquidation_pressure(stale_cache)`。
  实测这些文件分别陈旧 60 天 / 11 天 / 60 天 —— 如实写降级，不要写成 15/15，也不要当故障去修。
- 卡面 `风险快照 | stale_cache·<旧日期>·stale` 是**有意保留的可见降级**，不是 bug。
