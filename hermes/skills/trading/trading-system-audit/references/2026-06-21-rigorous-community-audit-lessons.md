# 2026-06-21 严苛多渠道社区审计教训

## 触发场景

用户要求“全方位、多渠道、联网社区、每一个社区都联网、不怕消耗、严苛审计系统并给优化方向”。

## 必须保留的审计模式

1. 先加载 `trading-system-audit`，不要只凭记忆。
2. 并行覆盖至少六源：Freqtrade、NautilusTrader、Bookmap、TradingView Pine v6、Reddit r/algotrading、X/ICT-SMC。
3. 同时采本地证据：cron、watchdog、monitor.log、source snapshots、pytest、auto_card 输出、Binance account、TradingView CDP、git 状态。
4. 报告必须以“能影响真实交易/监控可信度”为 P0/P1 判定标准，避免文档洁癖。

## 本轮新增 P0/P1 判定模式

### 1. 文本风控不等于硬闸（P0）

症状：分析卡操作段输出 `A做多/A做空`，止盈显示 `R:R 1:0.8` 或 `1:1.2`，但风控段同时写“R:R ≥1:2 — 低于直接 X禁做”。

判定：P0。因为系统口头说禁做，但实际给出 A 预案，会误导用户执行。

审计命令：

```bash
grep -n "④ 状态\|R:R\|③ R:R\|预案A" data/auto_card_BTCUSDT.md data/auto_card_BTCUSDT_full.md
```

修法方向：

- `render_card_locked()` 生成操作段前后都要执行硬闸校验。
- 若优先预案 `rr < 2.0`，状态必须降级为 `X禁做` 或 `B等待`。
- 降级后必须同步重算头部状态、决策、仓位、操作段、风控段，不能只追加 “⚠R:R不足”。
- `validate_card_rules()` 不能只检查 meta 的 `rr1/rr2`，还要检查实际渲染出来的 `R:R 1:x`。

### 2. 源码直测通过但运行日志相反（P1）

症状：源码直测 `has_min_liquidity('BTCUSDT', snapshot)=True`，但运行日志持续每 10 秒写 `流动性不足 BTCUSDT — 静默`。

判定：P1。说明运行态代码、状态缓存、参数传递或热进程与源码不一致，可能错误静默真实信号。

审计命令：

```bash
python - <<'PY'
import json, sys
sys.path.insert(0,'scripts')
from session_filter import has_min_liquidity, should_trade, get_active_sessions
for s in ['BTCUSDT','XAUUSD']:
    snap=json.load(open(f'data/source_snapshot_{s}.json'))
    print(s, snap.get('quality'), snap.get('confidence'), get_active_sessions(s), should_trade(s), has_min_liquidity(s, snap))
PY

grep -n "流动性不足 BTCUSDT" data/monitor.log | tail -40
```

修法方向：

- 在 `行情守望.py` 流动性拦截处输出结构化 reason：`symbol/q/confidence/session/has_min_liquidity_result/snapshot_keys`。
- 重启进程后验证日志与源码直测一致。
- 若日志仍相反，优先查调用处是否传入了旧 snapshot、空 snapshot 或不同 symbol。

### 3. Binance 价格链路正常不代表账户链路健康（P1）

症状：价格和持仓查询可能可用，但 `mcp_binance_get_account_summary()` 返回 futures `-1021 recvWindow`。

判定：P1。账户余额、实盘持仓、风险同步不可信。

修法方向：

- Windows NTP 同步。
- Binance 客户端增加 server time offset 校准。
- health score 中单独标注 account endpoint 状态，不能因 price endpoint 正常而判 Binance 健康。

### 4. Watchdog 冷却本身必须可见（P0/P1）

症状：`watchdog.log` 多次出现 `重启速率限制[卡死/环境未就绪]` 和 `重启速率限制[真崩溃]`。

判定：如果当前仍在冷却且无推送提醒，P0；如果已恢复但频繁发生，P1。

修法方向：

- 冷却进入时写结构化 health，并推 Telegram 846。
- 区分真崩溃与心跳阻塞，恢复策略分离。
- 不要只看 `monitor_heartbeat.json` 当前 running，就忽略过去 1–6 小时的冷却风暴。

## 社区共识映射

- Freqtrade / Reddit：Walk-Forward、过拟合控制、Protections、1%风险、回测不要在 callback 做重计算。
- NautilusTrader：pre-trade risk validation、fail-fast、外部化状态、可恢复重启。
- Bookmap：CVD 必须与 stop run、iceberg absorption、关键位流动性结合，不应孤立使用。
- TradingView Pine v6：footprint / volume delta 已成为可用方向，TV 数据应作为主验证源之一。
- X/ICT-SMC：高概率序列仍是 Sweep → MSS/Displacement → CVD/吸收 → 回踩 FVG/OB；R:R 低于 1:2 不应进入 A 计划。

## 报告写法

- 先讲“系统是否能跑”，再讲“哪里不可信”。
- P0/P1 每条都必须写：问题 → 证据 → 影响 → 修法。
- 不要把历史文档残留、旧日志、排版洁癖标 P0/P1。
- 当用户要求“严苛”，严苛对象是交易可信度，不是无差别挑刺。
