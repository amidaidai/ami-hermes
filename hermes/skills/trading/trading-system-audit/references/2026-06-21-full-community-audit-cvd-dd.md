# 2026-06-21 全面社区联网审计 — CVD趋势线 + 动态回撤降级

◷ 2026-06-21 21:30 · d8798ba · 六源联网 + 11域扫描

## 新增社区共识（本轮发现并实装）

### 1. CVD 趋势线突破检测（X/Twitter ICT/SMC 2026 LEADING信号）

**来源**: x_search "ICT SMC trading 2026 liquidity sweep CVD divergence"
**共识**: "CVD trendline breaks as LEADING signals of position unwinding — often BEFORE price fully breaks structure."

**差距**: 系统之前只检测 CVD 背离（价格与量方向不一致），未检测 CVD 自身趋势线突破。

**实现**: `scripts/orderflow_absorption.py` → `detect_cvd_trendline_break(cvd_series, window=20)`
- 线性回归拟合 CVD 趋势线（20根K线窗口）
- CVD 跌破上升趋势 = 多头撤离预警（conf 0-90）
- CVD 突破下降压制 = 空头撤退预警（conf 0-90）
- 两种加强信号：加速上行/下行（conf 0-70）

**代码模式（可复用）**:
```python
# 线性回归 + 斜率判定
x = np.arange(window); y = np.array(cvd_series[-window:])
slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
deviation_pct = (y[-1] - trendline_y[-1]) / np.ptp(y)

if deviation_pct < 0 and slope > 0:    # 下破 = 多头撤离
if deviation_pct > 0 and slope < 0:    # 上破 = 空头撤离
```

### 2. 动态回撤降级 v2.1（X/Twitter/Reddit 2026 机构共识）

**来源**: x_search "position sizing 1% risk per trade drawdown limit 2026"
**共识**: 
```
DD < 5%   → 全仓 1%
DD 5-8%   → 3/4仓 0.75%
DD 8-12%  → 半仓 0.50%
DD 12-15% → 1/4仓 0.25%
DD 15-20% → 微仓 0.10%
DD ≥ 20%  → 暂停
```

**差距**: 系统之前有 MaxDrawdown 硬熔断（10%/15%）但缺渐进式降级。

**实现**: `scripts/risk_constitution.py` → `dynamic_drawdown_scaling()` + `combined_risk_check()`
- 5级渐进降险（full/half/quarter/micro/paused）
- `combined_risk_check()` 三层组合：回撤降级 × 波动率自适应 × 硬上限(10U)
- 每层独立计算，最终取最小值

**代码模式（可复用）**:
```python
def combined_risk_check(account_balance, atr_pct, current_drawdown_pct):
    dd = dynamic_drawdown_scaling(current_drawdown_pct)      # 层1
    vol = adaptive_risk_usd(account_balance, atr_pct)        # 层2
    combined_risk_pct = dd["scaled_risk_pct"] * vol["multiplier"]
    hard_cap = min(account_balance * 0.10, max_risk_usd_abs) # 层3
    return min(account_balance * combined_risk_pct, hard_cap)
```

## Watchdog 重启风暴诊断模式（新发现）

**症状**: watchdog.log 20:57-21:24 连续"重启速率限制[真崩溃]：6次/小时已达上限"

**根因链路**:
1. Discord 推送 100% 超时（`hermes_cli timeout`）— 每笔阻塞 6s×2 重试
2. 推送走队列非阻塞 → 但 subprocess.run 占用 worker 线程
3. 次通道连续超时 + 主通道正常 → worker 串行被拖慢
4. 主循环其他阻塞（多个 requests.get timeout）累加
5. 心跳停滞 → watchdog 误判卡死 → 强杀 → 重启

**诊断四步法**:
1. 看时间分布：`grep "推送超时\|timeout" data/monitor.log | tail -40` — 确认错误在时间窗还是持续到当前
2. 跑实弹 send 测试：`hermes send -t telegram:... -q "test"` — 成功 = 通道活着，只是抖动脆弱性
3. 查 watchdog 重启原因：看"真崩溃" vs "卡死/环境未就绪"比例
4. 修复：缩短次通道超时/重试（10s×3 → 6s×2），最坏阻塞从30s降到12s

**手动救活流程**:
```bash
echo '{"restart_times":[],"restart_times_emergency":[]}' > data/watchdog_guard.json
```

## 测试真相纠正

**之前**: 审计报告声称"零回归测试" — 错误
**实际**: `tests/` 目录 15 个测试文件，103/104 passed
**教训**: `find` 命令优先于 `pytest scripts/tests/`；确认搜索范围不包括 sandbox/

## 系统态快照

| 维度 | 值 | 评级 |
|------|-----|------|
| 心跳 | PID 21836 · running | 🟢 |
| Cron | 4全活 · last_run ok | 🟢 |
| 数据 | BTC A / XAU A- | 🟢 |
| 账户 | $67.52 · 无持仓 | 🟢 |
| 测试 | 103/104 passed | 🟢 |
| 交易 | 296 plans · 0 executed | 🔴 |
| TV | 未安装本地 | 🔴 |

## 已对齐共识更新

15项已对齐:
CVD背离 · Liquidity Sweep · ATR夹层 · 日/周硬限 · 时间止损 · 分批止盈 ·
Protections · CVD+Taker+Funding · Kill Zone · 1%仓位 · 相关性矩阵 · 48h就绪 ·
三层架构 · **CVD趋势线突破** · **动态回撤降级**

## Commit

`d8798ba` feat: P1社区审计修复 — CVD趋势线突破检测 + 动态回撤降级 v2.1
