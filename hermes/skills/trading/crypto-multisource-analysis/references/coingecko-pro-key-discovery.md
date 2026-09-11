# CoinGecko Pro API Key — 发现与灌注（已完成）

> 2026-06-28 驾驶舱审计发现 → 同日完成灌注

## Key 信息

- **Key**: `CG-tkuaqHxNbpTQ92HgpvEc4QXY`
- **Header**: `x-cg-pro-api-key`
- **状态**: ✅ 已灌注 5 个脚本（含 orion）

## 灌注结果（2026-06-28 完成）

| 脚本 | 状态 | 改动 |
|------|------|------|
| `coingecko_collector.py` | ✅ Pro | `_fetch()` 加 CG header + `import os` |
| `data_gatherer.py` | ✅ Pro | `CG_KEY` 常量 + CoinGecko 调用传 headers |
| `multi_source_collector.py` | ✅ Pro | `CG_KEY` 常量 + `cg_top_coins/cg_trending` 传 headers |
| `trading_system.py` | ✅ Pro | `CG_KEY` 常量 + `http_get` 加 headers 参数 |
| `orion_screener_radar.py` | ✅ Pro | 原本已有 |

## 新增 Pro 端点（multi_source_collector.py）

- `cg_categories()` — 板块/分类 24h 涨幅排名，轮动检测 ✅ 已测可用
- `cg_coin_detail("bitcoin")` — 流动性评分/社区/开发者/CG 评分
- `cg_exchange_volumes("bitcoin")` — 交易所成交量明细（信任评分假量检测）

## 已知限制

- CoinGecko `tickers` 端点返回 400，可能是当前 Pro Key 计划等级不支持。`cg_exchange_volumes` 已编码，升级计划后即生效。
- `cg_categories` 实测可用（返回 Base Native 领涨 +0.2%）。
- Orion screener cron 与手动分析共用同一 Key，高峰期可能 429。所有 CG 函数使用 `_cached()` 缓存层（TTL 300-600s）缓解。
