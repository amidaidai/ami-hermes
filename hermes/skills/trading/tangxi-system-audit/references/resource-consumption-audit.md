# 资源消耗审计参考 (2026-06-29)

## LLM Token 消耗（仅 LLM 驱动 cron）

| Cron | 频率 | 模型 | 每次 token 估算 | 日消耗 | 月消耗 |
|------|------|------|----------------|--------|--------|
| BTC关键位同步 | 每4h | deepseek-v4-flash | 入~80K + 出~5K | ~$0.10 | ~$3 |
| BTC高频分析(已删) | 每15min | deepseek-v4-flash | 入~120K + 出~3K | ~$1.09 | ~$33 |

**关键发现**：BTC高频分析几乎每次都返回 `[SILENT]`（评分<7/10），但每次仍加载2个技能+TradingView MCP调用+Binance MCP调用+评分计算，然后输出2个字符。月消耗 $33 中 98% 是浪费。

**替代方案**：`btc_daemon.py` 是已存在的零 token 守护进程，本地多因子评分（DMI+VWAP+CVD+EMA），评分≥8自动推 TG:386。效果完全等价，token 消耗为 0。

## API 调用消耗（no_agent 脚本）

| 脚本 | 日调用量 | API | 免费/限额 | 风险 |
|------|----------|-----|-----------|------|
| 行情守望 daemon | 86K-172K | Binance REST | 1200/min (1.7M/d) | 高频率但限额内 |
| Orion雷达 | 56+140+420+84 | Orion+Binance+CG | 均<限额 | 低 |
| XAU监控 | 576 | Yahoo+Jin10 | 免费无限 | 无 |
| Deribit期权 | 192 | Deribit | 免费无限 | 无 |
| Dune链上 | 36 | Dune | 40/min | 低 |
| ETF Flow | 6 | SoSoValue | 免费 | 无 |

## 优化原则

1. LLM cron ≤ 每2min → 优先转 no_agent 脚本
2. 守护进程优先于 cron（零 token，本地计算）
3. 守护进程必须配看门狗 cron（防停运）
4. 新采集器 ≥ 每4h 用 `deliver: origin`，更频用 `local`
5. 月 token 预算 ≤ $5（仅保留 BTC关键位同步 $3）

## 2026-06-29 优化结果

| 项目 | 前 | 后 | 节省 |
|------|-----|-----|------|
| BTC监控 | LLM cron $33/月 | btc_daemon $0 | -$33 |
| BTC关键位 | LLM $3/月 | LLM $3/月 | — |
| 总月消耗 | ~$36 | ~$3 | -92% |
