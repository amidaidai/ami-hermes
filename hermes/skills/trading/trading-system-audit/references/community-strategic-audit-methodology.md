# 社区联网战略审计方法论 v1.1

2026-06-21 实战验证 + 更新。基于六大社区的全量审计流程。

**最新共识核对**: 见 `references/community-gap-analysis-2026-06-21.md` (13项共识·10已对齐·3差距·3缺失·13系统缺陷)

## 六源矩阵

| 源 | 搜索方向 | 工具 | 产出 |
|---|---------|------|------|
| Freqtrade + X | 策略优化/WFO/Protections/仓位/止损 | web_search + x_search | Protections/ATR/仓位共识 |
| Reddit r/algotrading | 散户实战教训/过拟合/风险管理 | web_search | 1%黄金标准/经验教训 |
| X/Twitter (ICT/SMC) | 2026最新SMC/ICT实战共识 | x_search | Sweep/Displacement/CVD锚定 |
| NautilusTrader | 架构/pre-trade风险检查 | web_search | 风险闸门/实时监控 |
| Bookmap | CVD/冰山水/吸收/订单流 | web_search + web_extract | 吸收检测/Stop Run预警 |
| TradingView Pine v6 | 新API/footprint/多TF | web_search + web_extract | Footprint API/原生volume profile |

## 审计流程（四步铁律）

### 1. 并行联网（必须全量，不挑拣）
六源同时搜索，每条返回至少3-5个结果。以下必须并行：
- `web_search` x 3-4 覆盖 Freqtrade/Reddit/NautilusTrader/Bookmap
- `x_search` x 2 覆盖 ICT/SMC + 风险共识
- `web_extract` 拉关键文章（Pine Script release notes / Bookmap absorption）

### 2. 提取共识表
从各源提取25+条可操作的共识 → 逐条对照棠溪系统 → 标记：
- 🟢 已对齐（系统已实现）
- 🟡 差距（有方向但未落地）
- 🔴 缺失（完全空白）

### 3. 差距分级
- **P1 战略缺口**：社区强制要求但棠溪缺失的功能（如 Freqtrade Protections、ATR 止损、固定分数仓位）
- **P2 增强方向**：有则更好的功能（Bookmap 冰山水、相关性矩阵、渐进上线）

### 4. 全量执行
用户说"全量执行"时立即批量修复全部 P1→实测→pytest→git commit+push。不分步等待确认。

## 本轮落地模块

| 模块 | 变更 | 社区源 |
|------|------|--------|
| risk_constitution.py v2.0 | MAX_RISK 3%→1%·KELLY 0.20·ATR上限·Protections类 | X/Reddit+Freqtrade+NautilusTrader |
| hard_stop.py v2.0 | position_size ATR夹层(0.5×∼2.5×ATR) | Freqtrade ATR trailing |
| readiness_report.py 新 | 8维48h就绪报告 | Freqtrade 48h readiness |
| 行情守望.py | Protections接入apply_risk_constitution | Freqtrade Protections |
| auto_card.py | Protections状态注入meta | 社区共识 |
| position_sizer.py v2.0 | 删除硬编码·对接宪法自适应 | X/Reddit fixed fractional |
| correlation_matrix.py 新 | BTC vs XAU动态相关+组合风险乘数 | Reddit多资产风险 |
| orderflow_absorption.py 新 | Bookmap式CVD吸收/冰山水/StopRun | Bookmap 2026 |
| dryrun_progressive.py 新 | 3阶段渐进上线(DryRun→Micro→Full) | Freqtrade dry-run |

## 可复用代码模式

- `Protections.check_all(symbol, current_bar)` → StoplossGuard(12根)+Cooldown(3根)+MaxDrawdown(10%/15%)
- `adaptive_risk_usd(balance, atr_pct)` → 波动率自适应风险金额
- `position_size(atr_value=...)` → ATR夹层止损自动修正
- `multi_asset_risk_multiplier(positions)` → 相关性感知组合风险
- `detect_absorption(symbol, price, cvd_direction)` → CVD吸收/背离/StopRun

## 验证铁律

每次全量审计后必须：
1. pytest 全量通过
2. Protections 持久化 save/reload 实测
3. ATR 夹层4场景实测（正常/过紧/过宽/无ATR）
4. readiness_report 产出正确
5. Git clean → commit + push
