# 全系统深度审计框架 v2.0 · 2026-06-17

> 本次审计覆盖七个维度：Hermes 核心 · 策略模板 · 监控系统 · MCP/API 数据链 · 市场情绪/新闻 · Skills 生态 · 工程治理。
> 审计方法：先验明运行态（配置→心跳→数据→日志），再逐层对比"配置应然"和"运行实然"，以 P0/P1/P2 分级输出。

---

## 审计维度与检查清单

### 1. Hermes 核心
- [ ] config.yaml providers 是否显式声明？
- [ ] cron jobs 是否覆盖交易分析触发？
- [ ] checkpoints 是否开启（防长会话崩溃）？
- [ ] delegation spawn_depth 是否足够？
- [ ] 搜索后端（web_search/web_extract）是否实际生效？
- [ ] x_search 代理是否配置正确？
- [ ] 多平台（Telegram/Discord）推送是否双通道就绪？

### 2. 策略模板
- [ ] 模板版本是否统一（v5.1/v9.7/锁定 三套归一派生）？
- [ ] 评分器是否统一（等权 13 分 vs 加权 15 分→13 分显示）？
- [ ] 五类固定模型 vs 31 类扩展的关键边界是否明确？
- [ ] R:R 底线 1:2 是否有自动校验（model_checklist.py）？
- [ ] 博弈段是否含三源一致判断（DMI + 引擎 + CVD）？
- [ ] 预案优先级标注（⚠优先）是否落实？

### 3. 监控系统
- [ ] 行情守望 heartbeat 是否正常？
- [ ] watchdog 参数（30s/90s）是否需要收紧？
- [ ] 推送是否有重试 + 双通道？
- [ ] 降噪规则是否过严（位信 70% warning 被吞）？
- [ ] 信号巡检是否误报"无进程"？
- [ ] 清理守护是否独立 cron？

### 4. MCP / API 数据链
- [ ] 六边形检查：价格 → 衍生品 → K线/结构 → 快讯 → 宏观 → 情绪
- [ ] 哪些 MCP 实际在线？（TradingView ✓ / Binance ✓ / 金十 ✓ / FinanceKit ✓）
- [ ] 实时新闻流是否有自动管道？（CoinDesk RSS / 金十 Flash 自动聚合）
- [ ] API Key 是否有硬编码泄露？
- [ ] XAU 价格链是否有 OANDA 现货主源？

### 5. 市场情绪 / 新闻
- [ ] 恐慌贪婪指数是否每日自动刷新？
- [ ] Grok x_search 是否接入 data_gatherer pipeline？
- [ ] Polymarket 概率是否自动拉取（而非手动浏览器）？
- [ ] CoinDesk/Cointelegraph 标题是否自动入库？
- [ ] Adanos 跨源情绪（finance-sentiment skill）是否激活？
- [ ] 情绪→结构冲突是否有自动告警？

### 6. Skills 生态
- [ ] 交易核心 skills 是否最新且无冲突？
- [ ] 冗余 skills 是否标记？（232 中 ~180 一年不用）
- [ ] feishu-analysis 和 hermes-feishu-card 是否双系统冲突？
- [ ] 未激活但有价值的 skills 有哪些？

### 7. 工程治理
- [ ] strategy_governance.json 是否有真实模型记录？
- [ ] 复盘闭环是否完整（成交记录→成交复盘→治理更新）？
- [ ] 系统健康分是架构分还是实战分？
- [ ] 是否有真实样本（≥20 笔）可供参数校准？
- [ ] 清理守护是否会遗漏？

---

## 当前状态快照（2026-06-17 实测）

| 维度 | 评级 | 关键数据 |
|------|------|---------|
| 价格数据 | **A** | Binance 3源 + CoinGecko + Yahoo，偏差 <0.15% |
| 衍生品 | **A** | Funding/OI/Taker/LS/Basis 全量，Binance 签名API |
| K线/结构 | **A** | TradingView MCP/SVP+ICT+VWAP+EMA+CVD+DMI 决策表 |
| 中文快讯 | **A** | 金十 MCP Flash + 新闻 + 日历 |
| 宏观层 | **B+** | 黄金宏观.py（13资产），FinanceKit 技术分析 |
| 市场情绪 | **B** | 恐慌贪婪（日更）+ Grok x_search（手动）+ Polymarket（手动浏览器） |
| 实时新闻 | **D** | 无自动管道，CoinDesk/Cointelegraph 未接入 |
| 跨品种关联 | **C** | v9.7 §F 规则存在但无自动执行 |
| 预测市场 | **C** | 手动浏览器查 Polymarket |
| 系统健康 | **93/100** | 架构完整但仅 1 笔真实复盘（1/20 样本） |

---

## Grok x_search 集成路线图

```
当前：x_search 工具可用（grok-4.20-non-reasoning）→ 代理 OK → 但只手动触发

Step 1（2h）：data_gatherer.py v2.1 新增字段
  snap["sentiment"] = {
    "fear_greed": ...,
    "x_sentiment": {"direction": "bullish/bearish/neutral", "strength": "high/med/low"},
    "news_headlines": [...],  # 金十 Flash + CoinDesk 标题
    "polymarket": {...}       # 预测市场概率
  }

Step 2（1h）：分析卡博弈段融合
  新增 ③ X情绪 ④ 快讯 ⑤ 恐慌贪婪 → 扩展博弈段 7 行

Step 3（30m）：情绪-结构冲突告警
  行情守望.py 10s 巡检时读 sentiment 缓存 → 冲突则 push warning
```

---

## P0/P1/P2 分类标准

- **P0**：致命——导致推送丢失、方向误判、交易依据缺失、凭据泄露
- **P1**：重要——影响效率、准确性、容错率，一周内应修
- **P2**：清理——代码冗余、配置不透明、过期文档、未启用功能

---

## 改造优先级

```
Week 1（P0）：data_gatherer 升级 + 模板合并 + cron ×3 + Discord 双通道 + R:R 自动校验
Week 2（P1）：情绪融合 + 评分器统一 + 五类/31类边界 + 信号巡检误报 + 飞书双通道确认
Week 3（P2）：清理守护独立 + Skills 冗余清理 + 品种模板标记 + 10笔小仓实盘
```

---

## 关联引用
- `p0-audit-findings-20260617.md` — 第一次审计的 P0/P1/P2 发现和修复记录
- `skeleton-card-audit-pitfalls.md` — 骨架卡片审计陷阱速查
- `template-locked-final.md` — 锁定模板的铁律和格式
- `template-v97-enhancements.md` — v9.7 量化增强层
- `tiered-analysis-strategy.md` — 分层分析 + 缓存继承
- `multi-model-confidence-engine.md` — 12 模型拼接引擎
