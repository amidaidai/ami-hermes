# 数据采集管道 v3.0 架构

> 2026-06-17 · data_gatherer.py v3.0 + cron 调度 · 修复全系统 P0 审计问题

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│              data_gatherer.py v3.0                   │
│              (每5分钟 cron)                           │
├─────────────────────────────────────────────────────┤
│  价格层     │ BTC: Binance+CoinGecko (2源)            │
│            │ XAU: 金十+Yahoo GC+F + MGC=F (3源)      │
├────────────┼────────────────────────────────────────┤
│  衍生品    │ Funding/OI/Basis/BTC多空比(A)/Taker(B)  │
├────────────┼────────────────────────────────────────┤
│  情绪层    │ 恐慌贪婪(日)/Polymarket(REST)/           │
│            │ X情绪占位(status:pending·需agent补跑)     │
│            │ CoinDesk RSS钩子                         │
├────────────┼────────────────────────────────────────┤
│  宏观      │ DXY/VIX/SPX/US10Y (Yahoo)               │
│            │ XAU专属: DXY/EUR/USDJPY/美债/TIP/TLT/    │
│            │  GC=MGC/SI/GLD/GDX/MOVE                 │
├────────────┼────────────────────────────────────────┤
│  API安全   │ Binance Key: env→hermes/secrets/binance. │
│            │ json·不再硬编码                           │
├────────────┼────────────────────────────────────────┤
│  评级      │ A(全源一致)/B(2源)/C(1源)               │
│            │ CVD C级→auto半仓降权                     │
└─────────────────────────────────────────────────────┘
```

## 输出结构

```json
{
  "snapshot_time": "ISO8601",
  "snapshot_ts": unix,
  "binance_spot": {price, 24h_high/low/vol/change},
  "coingecko": {price},
  "price_consensus": {sources, max_deviation_pct},
  "funding": {current, previous, history[]},
  "oi": {btc, usd_nominal},
  "basis": {mark, index, premium_pct},
  "long_short_top": {long, short, ratio, side, quality:"A"},
  "long_short_global": {long, short, ratio, side},
  "taker_futures": {buy_vol, sell_vol, ratio, direction, quality:"B"},
  "fear_greed": {current, classification, trend_5d, signal},
  "xau": {prices[], consensus_price, sources, quality},
  "xau_macro": {dxy, eurusd, usdjpy, us10y, us02y, tip, tlt, ...},
  "sentiment": {
    "x": {status:"pending", note:"run agent x_search"},
    "coindesk": {status},
    "polymarket": {events[], count}
  },
  "dxy": {value}, "vix": {value}, "spx": {value}, "us10y": {value},
  "available": {price, funding, oi, basis, long_short_top, ..., xau, ...},
  "grades": {overall: "A"/"B"/"C"}
}
```

## Cron 调度体系

```bash
# 每5分钟 — 数据采集
*/5 * * * *  python hermes/scripts/data_gatherer.py

# 每4小时+2分 — K线收线提醒
2 */4 * * *  bash hermes/scripts/cron_4h_analysis_reminder.sh

# 每30分钟 — 方向翻转守护
*/30 * * * * python hermes/scripts/cron_direction_flip_guardian.py

# 每天23:00 — 每日复盘
0 23 * * *   python hermes/scripts/cron_daily_review.py

# 每天4:00 — 清理守护(独立·不依赖信号巡检)
0 4 * * *    python hermes/scripts/cleanup_daemon.py

# 每天23:00 — 工作区备份
0 23 * * *   bash hermes/scripts/git_daily_backup.sh
```

## 安全升级

- ❌ 旧版：Binance API Key 硬编码在 `data_gatherer.py` L15-16
- ✅ v3.0：优先读环境变量 `BINANCE_API_KEY`/`BINANCE_SECRET_KEY`，fallback 读 `hermes/secrets/binance.json`
- `hermes/secrets/` 目录在 `.gitignore` 中，不备份到 GitHub

## 情绪填充流程

由于 x_search 是 agent tool（需要 Hermes context），cron 脚本无法直接调用：

1. `data_gatherer.py` → 写 `sentiment.x.status = "pending"`
2. Agent 分析时检测 `pending` → 执行 `x_search("BTC sentiment crypto today", limit=5)`
3. 提取方向（bullish/bearish/neutral）+ 强度（high/med/low）
4. 写入博弈段 `X情绪：偏X·强度{high/med/low}·{跟结构一致/冲突⚠}`

Polymarket 已通过 Gamma REST API 自动拉取（无需浏览器）。

## 已知限制

- CoinDesk RSS 返回 XML 格式，`safe_fetch()` 的 JSON 解析返回 `_error`。需通过 agent `web_extract` 补取
- XAU 金十 Quote 有时无响应 → 自动降级到 Yahoo GC=F + MGC=F 双源（B 级）
- x_search 代理依赖：`api.x.ai` 必须不在 `NO_PROXY` 中
