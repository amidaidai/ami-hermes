# 驾驶舱 v9.1 全社区审计报告（2026-06-29）

## 对标源

- **学术**：VLDB 2024 "From On-chain to Macro: Assessing the Importance of Data Source Diversity in Cryptocurrency Market Forecasting" — 5类数据源框架
- **专业架构**：Quant 2.0 (AltStreet) — 模块化AI-Native交易栈
- **社区标杆**：Freqtrade、SuperAlgos、awesome-systematic-trading
- **实操**：Reddit r/algotrading pipeline讨论

## 学术5类框架对标

| 类别 | VLDB 2024 | 驾驶舱覆盖 | 状态 |
|------|-----------|-----------|------|
| On-chain Metrics | 交易量、活跃地址、哈希率、矿工收入、供应分布 | Dune(BTC流/CEX净流) | 部分覆盖 — 缺ETH/SOL专用链上 |
| Technical Indicators | SMA/EMA/RSI/Bollinger | TV SVP v10 + Volume | 完整覆盖 |
| Sentiment & Interest | Google Trends、社媒量/情绪、恐惧贪婪 | X情绪(声明)、FG、Poly | X情绪虚挂 — 声明但无采集脚本 |
| Traditional Markets | SPX/DXY/黄金/欧元/债券 | 宏观(SPX/VIX/DXY/US10Y) | 完整覆盖 |
| Macroeconomic | 利率、通胀、政策不确定性 | 金十日历、COT | 完整覆盖 |

## Quant 2.0 架构对标

| 组件 | 专业标准 | 驾驶舱 | 评级 |
|------|---------|--------|:--:|
| Data Lakehouse | 统一存储+ACID+时间旅行 | 无 — 文件系统散落 | ❌ |
| Feature Store | 训练/生产一致特征计算 | 无 | ❌ |
| MLOps Pipeline | 自动验证/影子/金丝雀部署 | 无 | ❌ |
| Backtesting | 历史回测+过拟合检测 | backtest_runner.py存在但孤立 | 🟡 |
| Execution/OMS | 订单管理+滑点+成交率 | 无 — 仅风控skill | ❌ |
| Monitoring | 数据新鲜度+模型漂移 | 进程心跳有，数据过期无 | 🟡 |
| Alert Governance | 去重+限流+升级 | 无 | ❌ |

## 声明 vs 实现差距

| 能力 | 声明位置 | 实际状态 |
|------|---------|---------|
| X情绪 | pipeline_router x_sent, SKILL Step 6 | 无采集脚本，分析时手动调x_search |
| CG Pro验证 | Orion Step 4 | HTTP 400失败，全部CG验证空 |
| position_sizer | 2行wrapper | 无逻辑 |
| event_ban_live | 2行wrapper | 无逻辑 |
| session_strategy | 2行wrapper | 无逻辑 |
| triple_confirm | 2行wrapper | 无逻辑 |

## 免费数据源缺口

| 数据 | 来源 | 费用 | 状态 |
|------|------|------|:--:|
| 爆仓/强平 | Binance /fapi/v1/allForceOrders | 免费 | 未接入 |
| 稳定币供应 | Dune query 4159727 | 免费 | 待验证 |
| 清算热力图 | CoinGlass | $29/mo | 已拒绝 |
| 鲸鱼追踪 | Glassnode/Nansen | 付费 | 已拒绝 |

## P0-P2 优先级

### P0 — 立即补（影响分析完整性）
1. X情绪虚挂 → 写 x_sent_collector.py + cron
2. 爆仓数据缺失 → 写 liquidation_collector.py + 接入分析卡

### P1 — 本周补（已有代码未接入）
3. 回测引擎孤立 → 接入 pipeline_router + 为信号提供历史胜率
4. 数据过期告警 → 写 data_freshness_watchdog.py
5. 4个空wrapper → 写实际逻辑或删除

### P2 — 本月补
6. CG Pro验证修复 → 排查400错误根因
7. 稳定币供应验证 → 确认Dune query有效性
8. 跨资产相关性矩阵 → 计算滚动相关性
9. 告警去重 → cron输出比对上一轮，不变则静默

## Orion代理双策略修复（2026-06-29）

根因：cron环境与直接环境的网络代理配置不同。Orion API在cron中无代理导致返回空。

修复：`fetch_orion()` 双策略 — 系统代理优先 → 直连回退。
```python
strategies = [(None, "proxy"), (ProxyHandler({}), "direct")]
```
两个策略任一成功即返回，覆盖cron/直接两种环境。
