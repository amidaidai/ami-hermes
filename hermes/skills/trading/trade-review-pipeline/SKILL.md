---
name: trade-review-pipeline
description: "棠溪交易复盘管线 — 成交记录、成交复盘、策略治理、预测验证、系统体检。零token自动执行，每次平仓后自动触发。对接 scripts/成交记录.py, 成交复盘.py, 策略治理.py, prediction_tracker.py"
version: 1.0.0
author: 安禾
tags: [trade-log, trade-journal, review, governance, pnl, backtest, prediction]
---

# 交易复盘管线 — Trade Review Pipeline

棠溪交易系统的复盘闭环。每次平仓后执行，自动更新风险状态和治理库。

## 核心脚本

| 脚本 | 功能 | 触发时机 |
|------|------|---------|
| `成交记录.py` | 记录开仓信息（品种/方向/入场/止损/止盈/仓位） | 开仓后立即执行 |
| `成交复盘.py` | 完整复盘：平仓价→R:R→预期vs实际→风险评估 | 平仓后立即执行 |
| `策略治理.py` | 录入/更新模型绩效到 governance.json | 复盘后执行 |
| `prediction_tracker.py` | 预测追踪 + 验证 + 聚合统计 | 每次出卡时自动记录 |
| `系统体检.py` | 健康分（监控/快照/宏观/治理/复盘/代码） | 每日维护 |
| `模型统计.py` | 按模型统计胜率/平均R/最大亏损串 | 每日维护 |

## 执行流程

```bash
# Step 1: 开仓后 — 记录成交
cd D:/Hermes agent/scripts
python 成交记录.py --symbol BTCUSDT --direction long --entry 65000 \
  --stop 64200 --target 66600 --size 0.001 --model vwap_bounce

# Step 2: 平仓后 — 完整复盘
python 成交复盘.py --symbol BTCUSDT --exit_price 66200 \
  --exit_reason "TP触及" --exit_time "2026-06-23T14:30:00Z"

# Step 3: 治理更新
python 策略治理.py

# Step 4: 验证预测
python prediction_tracker.py --verify

# Step 5: 系统健康检查
python 系统体检.py
```

## 数据文件

| 文件 | 格式 | 用途 |
|------|------|------|
| `data/trade_record.jsonl` | JSONL | 逐笔成交记录 |
| `data/trade_reviews.jsonl` | JSONL | 复盘记录（含R:R/预期vs实际） |
| `data/strategy_governance.json` | JSON | 模型绩效 + 启停建议 |
| `data/prediction_log.jsonl` | JSONL | 预测追踪 |
| `data/risk_state.json` | JSON | 风控状态（连亏计数/冷却期） |
| `data/system_health_score.json` | JSON | 系统健康分 |

## 输出现有格式

极简复盘报告（自动生成）：
```
◷ 2026-06-23 · BTCUSDT · VWAP反抽 · ↑做多
入场 65000 → 出场 66200
R:R 1:2.3  ·  实际 +1.8R
预期vs实际：方向✓ · 入场+0.3R · 目标-0.5R
引擎评分：结构8 · 量价7 · 衍生6 → 总体70
风控：仓位0.001 · 风险1.2U · 盈亏+1.8U
```

## 预测验证

```python
# prediction_tracker 核心指标
- win_rate (已平仓预测)
- avg_r_multiple (平均R倍数)
- max_consecutive_losses (最大连亏)
- was_correct vs predicted (预期vs实际偏差)
```

## 陷阱
- `prediction_log` 的验证字段是 `was_correct` 不是 `win`
- `strategy_governance.json` 的 `rules: {}` 初始状态需要手动录入
- **1/3规则**：连续3笔亏损→降档，5笔亏损→全停
- 复盘前必须先执行 `成交记录.py`，否则 `risk_gate()` 把下一笔降到最轻仓
- **经验法则**：10-20 笔真实交易后才可以调核心参数
