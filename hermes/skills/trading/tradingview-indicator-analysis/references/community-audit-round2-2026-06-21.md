# 第二轮社区联网审计 · 2026-06-21

◷ 六大社区源 · VWAP+EMA+CVD三合一共识

## 社区发现

### X/Twitter ICT/SMC
- **VWAP+EMA+CVD三合一 = 2026黄金标准**：价格在VWAP上下(机构方向) + EMA排列(趋势强度) + CVD确认(假突破过滤)
- 3/4对齐才是高置信·pullback entry优于breakout chase
- CVD趋势线突破是LEADING信号（早于价格2-5根K线）
- SMT divergence (correlated assets) 作为 post-sweep 确认

### Reddit r/algotrading
- 回撤控制 > 胜率优化
- 固定分数1% + 动态降级 = 机构标准
- 动态回撤降级：DD>5%→0.75x, DD>8%→0.5x, DD>12%→0.25x, DD>15%→暂停
- VWAP SD bands 回测价值区，周末过滤

### Freqtrade
- Protections 三层 (StoplossGuard/Cooldown/MaxDrawdown) ✅ 已对齐
- ATR trailing stop
- Dry-run 渐进上线

### NautilusTrader
- Pre-trade 风险闸门 ✅ 宪法覆盖
- Crash-Only 模式：corrupt data > no data

### Bookmap
- Iceberg 吸收检测 → Stop Run 预警
- CVD divergences 在 key level 处精度最高
- MBO数据不可得时用大单频率+价格停滞近似

### TradingView Pine v6
- `request.footprint()` 原生 VAH/VAL/POC/delta (需Premium/Ultimate)
- `syminfo.isin` 跨交易所标识
- `timeframe_bars_back` 多TF时间戳

## 系统融合状态

| 社区共识 | 棠溪状态 | 轮次 |
|---------|---------|------|
| VWAP+EMA+CVD三合一 | ✅ vwap_ema_cvd_engine.py | 本会话新增 |
| CVD趋势线突破LEADING信号 | ✅ orderflow_absorption.py | 本会话新增 |
| 动态回撤降级(5级) | ✅ risk_constitution.py | 本会话新增 |
| DMI决策表=真理源 | ✅ TV读取+auto_card消费 | v6.9.14 |
| Protections系统 | ✅ v2.0 | 第一轮 |
| Walk-Forward验证 | 框架存在·未产出 | P1待补 |
| 蒙特卡洛模拟 | 缺失 | P2 |
| TV Pine v6 Footprint | 需Premium | P2 |
