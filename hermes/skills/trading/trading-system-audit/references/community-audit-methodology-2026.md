# 2026-06-21 六大社区联网审计 · 方法论与共识表

## 审计源矩阵

| 源 | 覆盖领域 | 搜索词模式 |
|-----|---------|-----------|
| Freqtrade (GitHub 23k⭐) | 策略优化/WFO/Protections | `Freqtrade 2026 latest features strategy optimization stoploss trailing hyperopt` |
| Freqtrade + X Community | 仓位/止损/上线流程 | `Freqtrade best practices 2025 2026 strategy optimization risk management` |
| Reddit r/algotrading | 散户实战教训 | `reddit algotrading "2025" OR "2026" best strategy lessons learned` |
| X/Twitter (ICT/SMC) | 2026最新实战共识 | `SMC ICT trading 2026 BTC XAUUSD best strategy liquidity sweep CVD` |
| X/Twitter (algo risk) | 仓位/风险管理 | `algo trading risk management position sizing 2025 2026 lessons` |
| NautilusTrader | 架构/pre-trade | `NautilusTrader 2025 2026 features comparison architecture risk controls` |
| Bookmap | CVD/冰山水 | `Bookmap order flow CVD absorption iceberg 2025 2026` |
| TradingView Pine v6 | 新API能力 | `TradingView Pine Script v6 2025 2026 new features footprint` |

## 25条社区共识对照表

| # | 共识 | 源 | 棠溪对齐 | 落地状态 |
|---|------|-----|---------|---------|
| 1 | Walk-Forward是验证黄金标准 | Freqtrade/X | 已对齐 | v9.12 |
| 2 | Freqtrade Protections系统 | Freqtrade | 🔴 差距→已修复 | v2.0 Protections类+持久化 |
| 3 | 0.5-1%固定分数仓位 | X/Reddit | 🟡 差距→已修复 | MAX_RISK 3%→1% |
| 4 | 仓位错了知道也爆仓 | X/Reddit | 🟡 已对齐 | adaptive_risk_usd |
| 5 | ATR动态止损>固定点位 | Freqtrade/X | 🟡 差距→已修复 | ATR夹层0.5×~2.5× |
| 6 | Pre-trade风险闸 | NautilusTrader | 🟡 差距→已修复 | Protections接入管线 |
| 7 | Tail risk>upside | X | 已对齐 | risk_constitution |
| 8 | CVD吸收→Stop Run | Bookmap | 🟡 P2增强 | 未落地 |
| 9 | Heatmap可视化 | Bookmap | 方向 | 未落地 |
| 10 | Footprint API | TV v6 | 🟡 P2可用 | 未使用 |
| 11 | timeframe_bars_back | TV v6 | 知晓 | 未使用 |
| 12 | Hyperopt限制搜索空间 | Freqtrade | 已对齐 | bayesian_optimizer |
| 13 | 48h上线就绪报告 | Freqtrade | 🟡 缺失→已创建 | readiness_report.py |
| 14 | 参数稳定性测试 | X | 🟡 缺失→已在就绪报告 | readiness_report.py |
| 15 | 波动率缩放防爆仓 | X | 🟡 差距→已对齐 | volatility_target_multiplier |
| 16 | 相关性感知 | X/Reddit | 🟡 P2缺失 | 未落地 |
| 17 | 简洁胜过复杂 | Reddit | 已对齐 | 五模型限定 |
| 18 | Liquidity Sweep灵魂 | X(ICT) | 已对齐 | v6.9.2 |
| 19 | XAU Kill Zone双段 | X/ICT | 已对齐 | session_filter |
| 20 | BTC spot/perp CVD | X/ICT | 已对齐 | CVD aggTrades |
| 21 | 自动复盘闭环 | Reddit | 已对齐 | 成交记录+成交复盘 |
| 22 | Dry-run渐进上线 | Freqtrade | 🟡 P2缺失 | 未落地 |
| 23 | 50-65%胜率是健康 | X | 已对齐 | prediction_tracker |
| 24 | 最大回撤硬停 | Reddit | 🟡 差距→已修复 | MAX_DAILY_DRAWDOWN_HARD 10% |
| 25 | 量价背离=即将突破 | Bookmap | 🟡 P2增强 | 未落地 |

统计: 已对齐14·已修复7·P2待做4

## 落地代码清单

### risk_constitution.py v2.0
```
CONSTITUTION:
  MAX_RISK_PER_TRADE_PCT: 0.03 → 0.01    (X/Reddit 1%黄金标准)
  KELLY_FRACTION: 0.25 → 0.20            (更保守)
  MAX_STOP_ATR_RATIO: 新增 2.5           (止损上限)
  STOPLOSS_GUARD_LOOKBACK: 新增 12       (Freqtrade防复仇)
  COOLDOWN_AFTER_LOSS: 新增 3            (亏损冷却)
  MAX_DAILY_DRAWDOWN_HARD: 新增 0.10     (日回撤全停)
  MAX_WEEKLY_DRAWDOWN_HARD: 新增 0.15    (周回撤全停)

Protections 类:
  check_stoploss_guard(symbol, current_bar) → bool
  check_cooldown() → bool
  check_max_drawdown() → bool
  check_all(symbol, current_bar) → (passed, violations)
  on_stoploss(symbol, current_bar)       # 止损触发记录
  on_loss(current_bar)                    # 亏损触发冷却
  advance_bar()                           # 每K线推进
  to_dict() / from_dict()                 # JSON持久化

load_protections() / save_protections()   # 磁盘持久化
apply_protections(symbol, current_bar, protections) → dict
```

### hard_stop.py v2.0
```
position_size(entry, stop, risk_usd, atr_value=None):
  ATR夹层: min(结构位, max(结构位, 0.5×ATR)) for tight side
           max(结构位, min(结构位, 2.5×ATR)) for wide side
  → 返回 atr_clamped / original_stop / final_stop
```

### 管线接入点
- `行情守望.py` L650: apply_risk_constitution 内 Protections.check_all
- `auto_card.py` L1544: meta.protections_status 注入
- `position_sizer.py` v2.0: _get_account_balance/_get_max_risk_usd/_get_leverage

## P2 未落地增强（方向参考）
1. Bookmap冰山水吸收检测 → CVD吸收→Stop Run预警
2. BTC vs XAU 相关性矩阵 → 组合风险
3. TradingView Pine v6 Footprint API → 原生volume profile
4. Dry-run渐进上线模式 → 仿真→小规模→全量
