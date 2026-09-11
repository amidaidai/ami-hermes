# Orion LLM Cron 恢复与验证方法 v9.6

2026年6月29日。用户明确要求保留Orion雷达分析为LLM cron。

## cron配置

| 参数 | 值 |
|------|-----|
| cron ID | `ca1678011963` |
| 名称 | Orion雷达分析 |
| 频率 | 5,35 9-23 * * * (每30min, 仅活跃时段) |
| Skills | orion-screener-radar, crypto-multisource-analysis, binance-trading, crypto-onchain-flow |
| Workdir | D:/Hermes agent |
| 推送 | telegram:-1003733144325:846 |
| 月成本估算 | ~$0.50 (18次/天 × ~$0.03) |

## 数据来源：四层验证链

LLM cron读取`data/orion_radar.json`（由no_agent脚本`orion_screener_radar.py`每30min采集）：

| 层 | 来源 | 验证内容 |
|---:|---|---|
| 1 | Orion Binance | 604品种实时扫描，检测OI异动/价量突变/费率异常 |
| 2 | Orion Hyperliquid | 451品种跨交易所交叉验证（HL确认标记） |
| 3 | Binance REST API | OI趋势·费率历史·Taker量·多空比（Binance直接验证） |
| 4 | CoinGecko Pro | 市值排名·现货成交量验证（防假量/假OI） |

## LLM分析任务

prompt核心指令（已内置到cron）：

1. 验证每候选置信度：HL确认标记、OI变化幅度（>8%=强信号）、费率极端度（>0.01%或负费）、量变化（>200%=强信号）
2. 读source_snapshot_BTCUSDT.json确认BTC方向，判断候选顺BTC还是逆势
3. 排除假信号：OI<50万U、24h涨跌幅<5%、BTC逆势无独立叙事
4. 输出7列表格（#·品种·价格·信号·置信度·HL验证·关键指标）
5. 前3候选给简明决策建议（方向·关键位·风控提示）

## 可靠性验证方法

| 验证维度 | 方法 | 假阳性处理 |
|---------|------|-----------|
| HL交叉确认 | Orion Binance信号 vs Orion HL信号一致 | HL不确认→降置信度 |
| OI真实性 | Orion OI变化 vs Binance API OI趋势 | 分叉>5%→标注假OI |
| 费率验证 | Orion funding vs Binance funding_rate | 差异>0.003%→用Binance为准 |
| 量验证 | Orion 24h vol vs CG现货量 | 比值>3x→标注刷量风险 |
| 时效性 | orion_radar.json mtime <30min | 过期→降级标注 |
| BTC方向过滤 | 候选方向 vs BTC 1h方向 | 逆势无叙事→排除 |

## 信号emoji标记

| emoji | 含义 |
|-------|------|
| 🟢OI涨 | OI 24h增幅>8% |
| 🔴OI跌 | OI 24h跌幅>8% |
| 🔥负费 | Funding rate < -0.005% |
| 💰正费 | Funding rate > 0.01% |
| ✅HL通 | Orion HL确认 |
| 🚀价涨 | 24h涨幅>5% |
| 📉价跌 | 24h跌幅>5% |
| 📊量变 | 24h量变化>200% |

## 之前删除原因与恢复

之前误判为"重复烧钱"而删除。实际情况：
- no_agent脚本做数据采集+四层验证+候选项筛选
- LLM cron做自然语言解读+决策建议+信号分级
- 两者互补，不重复

3个已永久删除的LLM cron（QLib因子解读、清算压力推演）不需要恢复——它们的原始数据已由no_agent脚本落盘，且信号简单不需要LLM解读。
