# LLM Cron 分析模式 v1.0

> 2026-06-29 · 如何为数据采集脚本配LLM分析cron · 详见完整文件

## 模式

采集脚本(no_agent) → 落盘JSON → LLM cron(错开5分钟) → 读JSON → 模型分析 → 推TG人话

## 三步

1. 脚本双落盘(hermes data + 项目data)
2. 创建LLM cron: no_agent=false, model=deepseek-v4-flash, schedule错开5分钟
3. prompt读文件+中文分析+推送TG

## 当前5个LLM Cron

| ID | 名称 | 读文件 | 频率 |
|------|------|------|------|
| 4846c6e383f7 | Orion雷达分析 | orion_radar.json | :05/:35, 9-23 |
| 515e6cf10d43 | QLib因子解读 | qlib_factors.json | :05/:35 |
| 2616ba6a5ccb | 清算压力推演 | liquidation_pressure.json | :05/:35 |
| ada5d94913fd | BTC关键位同步 | TV MCP | :00/每4h |
| f71dcf102007 | 每日复盘提醒 | trade_events.jsonl | 22:00 |

## 适用判断

- 异动筛选+多维解读 → ✅ LLM（人需要知道"为什么"不只是"什么"）
- 30因子评分→故事化 → ✅ LLM（一个数字不够）
- OI+价格→连锁推演 → ✅ LLM（需要推理因果关系）
- 纯数据采集(Dune/Deribit/COT) → ❌ 保持no_agent
- 健康检查(看门狗) → ❌ 二元判断不需要模型
- 维护(备份/同步) → ❌ 零推理需求

## 成本

deepseek-v4-flash: ~$0.14/1M in, ~$0.28/1M out
每30min一次: ~28次/天 × 2K tokens ≈ $0.01/天
三个LLM cron合计: ~$8-10/月