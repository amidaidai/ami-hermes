# BTC分析管线 v7 · 社区审计完善清单 (2026-06-22)

## 已执行

### 1. 守护去冗余
旧：独立6因子评分 → 新：只用指标等级+VWAP/VAL价破位
文件：`scripts/btc_vwap_daemon.py` v7

### 2. 精简分析模板
旧：10段头部+5段正文 → 新：6段精简
文件：`references/btc-analysis-compact-template.md`

### 3. 复盘闭环
新增复盘系统 `scripts/trade_journal.py`
- 每次分析记录：方向、入场区、止损、目标、理由、置信度
- `python trade_journal.py review` 查看最近记录
- 后续市场走完后补填 result/pnl_r 字段

### 4. 核对清单（已集成到模板⑤）
- HTF方向一致？
- 放量确认？
- R:R≥1:2？
- 无重大事件？
- 情绪不极端反向？

### 5. 今日判断已记录
- BTCUSDT 空优先 @63,800 放量确认 (conf=2/5)
- BTCUSDT 多(反弹) @63,947 站回VAL (conf=1/5)
→ 后续验证

## 待办
- 策略历史表现统计（需积累20+条记录）
- 事件日历接入（金十MCP）
- KillZone时间过滤（亚/欧/美盘）
- 情绪快照自动化（恐慌贪婪指数）
