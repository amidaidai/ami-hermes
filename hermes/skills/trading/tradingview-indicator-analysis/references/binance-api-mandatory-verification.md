# Binance 实盘 API 强制核验铁律（2026-08-29 用户纠正 · P0）

## 规则
**所有分析档次（quick / inherit / full）均必须拉取 Binance 实盘 REST API 核验** —— 不再仅凭 TV 指标值下结论。

## 必做核验清单（每次分析必跑）

| API 端点 | 核验目标 | 对应 TV 指标 |
|----------|----------|-------------|
| `fapi/v1/premiumIndex` | 标记价、资金费率、下次结算时间 | 资金费率、标记价 |
| `fapi/v1/ticker/24hr` | 24h 高低开收、成交量、换手 | 成交量、价格区间 |
| `futures/data/topLongShortAccountRatio` | 多空账户比（15m） | 大户/全局多空比 |
| `futures/data/takerlongshortRatio` | **Taker 主动买卖比（15m）** —— **CVD 交叉验证关键** | CVD 方向、买卖压力 |
| `fapi/v1/openInterest` / `futures/data/openInterestHist` | OI 绝对值 + 15m 变化率 —— **判定「新仓扩张」核心** | OI 方向票、价仓关系 |

## 共振票重新核算逻辑（含实盘核验）

| 共振要素 | TV 显示 | Binance 实盘核验 | 计票规则 |
|----------|---------|-----------------|----------|
| **同向 CVD** | CVD 数值 | Taker Buy/Sell Ratio 对比 | ✅ 一致才算票 |
| **OI 升(新仓扩张)** | OI Change % | OI 15m 变化 >0.5% 才算 | ✅ 仅 OI 实质增仓算票 |
| **放量** | Volume Ratio | 24h/15m 成交量对比 | ✅ 实盘放量才算 |
| **同向 HTF** | 结构方向 | 1D/4h 趋势确认 | ✅ 多周期一致才算 |

## 执行纪律
- **quick 模式**：至少跑 `premiumIndex` + `ticker/24hr` + `takerlongshortRatio` + `openInterest`（4 个 curl，约 2 秒）
- **inherit 模式**：quick 全部 + `topLongShortAccountRatio` + `openInterestHist`（5 分钟窗口）
- **full 模式**：全部端点 + 历史序列对比

## 输出要求
每次分析卡后必须附 **「Binance 实盘核验」小表**，再给最终裁决。格式见本次会话 2026年8月29日09：44 更新示例。

## 常见失败与降级
| 失败 | 降级路径 | 标注 |
|------|----------|------|
| fapi 全线 Cloudflare 403 | TV 副指标 Volume Aggregated OI/Composite 替代 | 「fapi CF 403·TV副指标替代」 |
| 单端点超时 | 单独重试 1 次，失败标注该项不可用 | 「{endpoint}: timeout·跳过」 |
| 网络完全不通 | 标注全量不可用，仅靠 TV 结构判断，降级为观望 | 「Binance API 全阻断·仅TV结构」 |

---
*来源：2026-08-29 会话用户明确纠正「三个档次都需要验证api，记得」*