# 驾驶舱 Cron 架构 v9.0

## 12-Job 分层设计

```
┌─ 运维层 (daily maintenance) ────────────────┐
│ 06:45  每日系统备份          ▸ TG:846       │
│ 07:00  每日SkillMCP更新      ▸ TG:846       │
│ 07:00  OpenRouter模型同步     ▸ local        │
│ 07:20  每日系统审计          ▸ TG:846       │
└─────────────────────────────────────────────┘

┌─ 高频监控层 (realtime monitoring) ──────────┐
│ 每15m  BTC高频分析(8-23)     ▸ TG:386       │ LLM cron
│ 每4h   BTC关键位同步          ▸ local        │ LLM cron
│ 每5m   XAUUSD监控(8-23)      ▸ origin       │ no_agent
│ 每30m  Orion全市场雷达(9-23)  ▸ origin       │ no_agent
└─────────────────────────────────────────────┘

┌─ 数据刷新层 (data refresh) ─────────────────┐
│ 每4h   ETF Flow刷新          ▸ local        │ no_agent
│ 每2h   Dune链上刷新          ▸ local        │ no_agent
│ 每15m  Deribit期权刷新       ▸ local        │ no_agent
│ 周六   COT报告刷新           ▸ local        │ no_agent
└─────────────────────────────────────────────┘
```

## 核心原则

### LLM cron ≤2min ≡ 必须转 no_agent
RE 监控 cron（每2min deepseek-v4-flash）本 session 已删。高频监控用 LLM cron 烧 token 且不可靠。
- LLM cron 仅用于需推理的任务（BTC高频分析15min、BTC关键位同步4h）
- 所有数据采集走 no_agent script + local deliver（不进 TG 刷屏）
- origin deliver 仅用于 Orion 雷达和 XAU 监控（有触发时才输出）

### 硬超时约束
cron 有 180s 硬超时。Orion 雷达从 10候选/8输出 优化到 5候选/5输出 + CG 首败即停 + Binance 超时 10→15s，预估 60-90s。

### 数据采集器清单
创建监控 cron 时必须对照此清单确认无遗漏：
| 采集器脚本 | 最小刷新频率 | 资产覆盖 | 状态 |
|-----------|-------------|---------|------|
| etf_flow_collector.py | 每小时 | BTC ETF | ✅ cron:78fdecc04c7f |
| dune_collector.py | 每30分钟 | BTC链上 | ✅ cron:3a8bee120dd4 |
| cot_collector.py | 每周六 | 全资产 | ✅ cron:b664f56f904c |
| deribit_options.py | 每30分钟 | BTC/ETH期权 | ✅ cron:0764c6922694 |
| gold_monitor.py | 每5分钟 | XAU/USD | ✅ cron:e55cc21726b9 |
| orion_screener_radar.py | 每30分钟 | 加密全市场 | ✅ cron:ef4cf5f7cd24 |

## 智能路由参考

`scripts/pipeline_router.py` — 按资产类别自动选择管线步骤：

```
BTCUSDT [crypto] → 14步: TV+Binance+CG Pro+宏观+金十+Poly+ETF+Dune+Deribit+X情绪+FG+CVD+深度+卡
XAUUSD  [gold]   →  8步: TV+宏观+金十+COT+X情绪+CVD+黄金宏观+卡
EURUSD  [forex]  →  7步: TV+宏观+金十+COT+X情绪+外汇利率+卡
AAPL    [stock]  →  8步: TV+宏观+金十+COT+X情绪+FMP+期权链+卡
```

加密专属步骤（Binance/CG Pro/Dune/Deribit/FG/CVD/depth）自动跳过非加密资产。

## Orion 雷达超时修复模式

```python
# 问题: 10候选 × 6 Binance API调用 + 10 CoinGecko调用 = ~180s (超时)
# 修复:
MAX_CANDIDATES = 5    # 10 → 5
MAX_OUTPUT = 5         # 8 → 5
BINANCE_TIMEOUT = 15   # 10s → 15s (但候选少了，总时间还是降)

# CG 早停: 首次失败即跳出
if not cg_data:
    print("CG failed, skipping remaining")
    break

# 限制 CG 验证数
if verified >= 3:
    break
```

## 监控健康检查流程

1. `cronjob(action='list')` 拿全量
2. 逐项判: error/timeout/silent/disabled/deliver缺失
3. 检查输出文件密度（error job 输出为 0 或只有 error 标头）
4. 对照采集器清单确认无缺失 cron
5. LLM cron 每 ≤2min → 建议转 no_agent
6. 检查 deliver: origin 的 job 是否真的收到（origin 可能静默丢包）
