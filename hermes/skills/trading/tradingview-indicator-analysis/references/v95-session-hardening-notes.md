# v9.5 会话硬化笔记

本参考记录本轮把交易分析系统从 v5.1/B+ 推到 v9.5 执行系统时沉淀的规则。未来只要用户要求“全面审计”“做到 9.5”“完善监控/风控/复盘”，必须优先应用这里的检查项。

## 用户纠偏

- 监控卡片里的 `plan_id` 不应原样展示为 `BTCUSDT-YYYYMMDD-HHMM`；它是机器追踪字段，用户侧必须中文化为 `比特币日内计划·6月17日00:15` 这种可读计划名。
- 监控提醒不能只说“接近计划位”；必须明确“现在是什么情况”和“现在该做什么”。
- 每张监控卡必须同时有：品种、价格、计划、现状、CVD、衍生、风控、价位、周期、动作。
- 除固定英文术语外必须中文化。固定英文术语包括：BTCUSDT、CVD、VWAP、POC、VAH、VAL、DO、OI、Funding、Basis、Taker、ATR、R:R、ETF、5m/15m/1h/4h。
- 审计类回复要批判性找缺口，不要先夸；用户说“全面审计/多渠道权威源社区联网全方位审计”时，要覆盖模板、数据源、监控、风控、复盘、工程稳定性。

## v9.5 必备闭环

1. 风控闸门：读取 `data/risk_state.json`，按日亏、连亏、数据质量、R:R、评分决定允许、降仓或禁做。
2. 数据快照：每次分析或监控触发都应写 `data/source_snapshot.json`，至少记录 Binance 现货价、futures mark/index、Funding、OI、多空比、Taker、Basis、数据质量。
3. 计划日志：每次正式分析必须追加 `data/trade_plans.jsonl`。
4. 事件日志：每次监控触发必须追加 `data/trade_events.jsonl`，并与 `monitor_events.json` 同步保留。
5. 复盘日志：用户说“进了/出了/止损/止盈/没做”时，必须追加 `data/trade_reviews.jsonl`。
6. 每日复盘：运行 `scripts/daily_review.py` 生成 `data/daily_review.md`。
7. 监控卡：必须显示衍生品摘要和风控结果，不只显示价格距离。

## 风控硬规则

- 数据 C级：最高轻仓，默认最大风险不超过 `3U`。
- R:R 低于 1:2：禁做。
- 连亏 2 笔：下一笔降至轻仓。
- 连亏 3 笔：锁交易。
- 日亏达到 `max_daily_loss`：锁交易。
- CVD 当前若仍为 K线估算，只能标 C级；不得作为 A单加分。

## 监控卡标准样式

```text
🟡 BTCUSDT 接近计划位
①   品种：BTCUSDT
②   价格：`65916`
③   计划：比特币日内计划·6月17日00:15
④   现状：价格接近计划位，先观察确认
⑤  CVD：卖 · C级
⑥   衍生：Funding接近中性；账户多头偏拥挤；Taker短线卖盘主动
⑦   风控：允许 · 轻仓 · 最大风险 `3.0U` · 数据C级，最高轻仓
⑧   价位：支1_扫低 `65928` ↓0.0%
     现状：接近扫低位
     动作：跌破未收回则二段下探，快速收回则扫低回收模型
     失效：5m 收复上方 66166
     优先：高
     有效：90m
⑨   周期：4h 偏多回撤 · 1h 转弱 · 15m 扫低反抽 · 5m 等确认

  动作：可等待触发
→ 说「分析 BTC」
```

## 工程注意

- Windows/MSYS 下旧监控进程容易形成 bash/python 多层链。重启监控前优先运行 `scripts/stop_smart_monitor.ps1`，不要依赖 `ps | awk | kill`。
- 脚本内发送 Telegram 不要用裸 `hermes send`；用 `sys.executable -m hermes_cli.main send`。
- `check_monitor_events.py` 是 cron 直接投递 stdout 的兜底脚本，任何监控卡格式升级都必须同步改它。
- skill 脚本目录、active cron 脚本目录、本地 `scripts/` 三处要同步。

## 9.5 仍未完成的上限项

- CVD 需要从 K线估算升级为 Binance futures `aggTrades`，才能从 C级升到 B/A级。
- 清算热力图尚未接入，后续可用 Coinalyze 或其他数据源补齐。
- TradingView 指标快照尚未自动写入 `source_snapshot.json`。
