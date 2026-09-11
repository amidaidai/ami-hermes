# XAUUSD 数据源约束

## Yahoo Finance 现货不可用

Yahoo Finance **不支持 XAUUSD 现货黄金**。经实测验证：

| 符号 | 结果 | 含义 |
|------|------|------|
| `XAUUSD=X` | HTTP 404 | 不存在 |
| `XAU=X` | None/404 | 不存在 |
| `XAU=F` | 913.1 | PHLX金银指数，不是金价 |
| `^XAU` | 365.5 | 也是指数 |
| **`GC=F`** | ✓ 真实价格 | COMEX黄金期货（主力合约） |
| **`MGC=F`** | ✓ 真实价格 | COMEX微型黄金期货 |

Yahoo Finance v8 chart API (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`)
和 quote API (`query2.finance.yahoo.com/v7/finance/quote`) 均不支持现货黄金符号。

## 当前数据源架构

| 层级 | 源 | 用途 |
|------|-----|------|
| **主价** | 金十Quote | XAUUSD 实时现货价（最稳定实时源） |
| **现货校验** | gold-api.com | 免费现货API·无认证·提升至A级 |
| **跨市场验证** | Yahoo `GC=F` + `MGC=F` | COMEX期货，最流动的黄金衍生品 |
| **宏观背景** | DXY, US10Y, TIP, TLT | 利率/美元/实际利率代理 |
| **贵金属同步** | GLD, GDX, SI=F | ETF、金矿股、白银确认 |

### XAUUSD 数据质量分级（2026-06-18 更新）

| 源组合 | 等级 | 置信度 | 标签 |
|--------|------|--------|------|
| 金十 + gold-api + Yahoo ≥1 | **A** | 92% | 金十+gold-api+Yahoo三源验证 |
| 金十 + gold-api | B | 82% | 金十+gold-api双源验证 |
| 金十 + Yahoo ≥1 | B | 78% | 金十+Yahoo跨市场验证 |
| gold-api + Yahoo ≥1 | B | 80% | gold-api+Yahoo跨市场验证 |
| 金十 单源 | C | 60% | 金十单源 |
| gold-api 单源 | C | 62% | gold-api.com单源 |

> **关键升级（2026-06-18）**：接入 gold-api.com（`https://api.gold-api.com/price/XAU`，免费·无认证·实时现货）后，XAUUSD 无需 OANDA 凭据即可达到 A级 92%。金十+gold-api 双现货源价差通常 < $3（0.07%），Yahoo 期货做跨市校验。代码实现见 `trading_system.py::gold_api_price()` 和 `price_consensus()` 的 gold_api_valid 分支。

## 设计原则

- **金十Quote 是 XAU 的唯一实时现货源** — 单源时标注"金十单源 · C级"
- **Yahoo GC=F 期货用于跨市场确认** — 现货-期货价差通常在 $1-15 范围
- **不要把现货/期货差异当成数据不一致** — 它们本身就是不同产品
- **宏层脚本 `黄金宏观.py`** 使用 GC=F 作 cross-check，rule 中已说明

## 不要做的事

- 不要尝试用 `XAUUSD=X` 作为 Yahoo 符号（404）
- 不要用 `yfinance` 替代（websockets.proxy 依赖冲突）
- 不要在监控卡中声称 "Yahoo 现货"（Yahoo 只有期货）
- 金十+Yahoo 双源可标 B级，但不要伪称 A 级（期货≠现货）