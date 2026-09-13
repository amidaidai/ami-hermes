---
name: backtesting-suite
description: "棠溪交易系统回测套件 — 覆盖策略回测、Walk-Forward验证、贝叶斯优化、过拟合检测、权益曲线追踪。对接 scripts/backtest_runner.py, walk_forward.py, bayesian_optimizer.py"
version: 1.0.0
author: 安禾
tags: [backtesting, backtest, optimization, walk-forward, bayesian, overfitting]
---

# 回测套件 — Backtesting Suite

棠溪交易系统内置回测引擎。所有脚本在 `D:/Hermes agent/scripts/` 目录下。

## 核心脚本

| 脚本 | 功能 | 运行方式 |
|------|------|---------|
| `backtest_runner.py` | 五模型+真实taker CVD+滑点+aurumcrypto成本模型 | `python backtest_runner.py --symbol BTCUSDT --period 30d` |
| `walk_forward.py` | Walk-Forward三段验证（训练60%/验证20%/测试20%） | `python walk_forward.py` |
| `bayesian_optimizer.py` | TPE贝叶斯参数优化（20迭代≈网格27组合） | `python bayesian_optimizer.py` |
| `equity_tracker.py` | 权益曲线+最大回撤+夏普比 | `python equity_tracker.py` |
| `model_optimizer.py` | 单模型网格搜索+参数灵敏度测试 | `python model_optimizer.py --model vwap_bounce` |

## 回测工作流

### ① 单次回测（最快验证）
```bash
cd D:/Hermes agent/scripts
python backtest_runner.py --symbol BTCUSDT --period 30d
# 输出: data/backtest_results.json  + 逐笔交易回放
```

### ② 参数优化（寻找最优参数）
```bash
python bayesian_optimizer.py
# 输出: data/bayesian_results.json — 参数组合+夏普比+最大化回撤
```

### ③ Walk-Forward 验证（防过拟合）
```bash
python walk_forward.py
# 输出:
#   - overfit_score < 15 = 通过
#   - OOS_gap (out-of-sample vs in-sample gap)
#   - param_stability (参数±10%不应崩坏)
```

### ④ 权益曲线+风控验证
```bash
python equity_tracker.py
# 输出: 权益曲线（dashboard.html:8766）
```

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fee_bps` | 0.04 (4bps) | Binance U本位实际费率 |
| `max_hold` | 96 bars | 24小时超时强平（15m周期） |
| `startup_candles` | 400 | 指标预热 |
| `max_params_per_model` | 3 | 贝叶斯优化上限 |
| `slippage` | 0.0004 (0.04%) | 模拟出入场滑点 |

## 回测已知结论

**BTC唯一回测结论（取自v9.10）**：
- VWAP反抽 → 正期望（最高覆盖率）
- POC拒绝 → 正期望
- VAH/VAL回收 → 正期望
- EMA趋势 → 负期望（不用于日内）
- 扫流动性回收 → 负期望（不用于日内）
- 所有数字有趋势偏差，不可直接用于实盘仓位计算

**品种分裂**：
- BTC专属（需futures数据）：费率反转·多空拥挤·Taker背离·OI背离
- XAU专属（黄金特性）：M_VWAP磁吸·关联套利·突破接受
- 共用（两边可用）：VWAP反抽·VAH回收·VAL回收·POC拒绝·EMA趋势·扫流动性

## vNext 架构集成（2026-07-10 决策闭环架构落地）

在「决策闭环为中心」架构下，回测引擎**不再独立运行策略模型**，而是**逐根 K 线调用同一套 `decision_loop`**，保证回测与实盘位级一致。

### 核心变更：`backtest_runner_v2.py`

```python
# scripts/backtest_runner_v2.py

from decision_loop import run_decision_loop
from contracts import MarketSnapshot, FinalVerdict

class BacktestRunnerV2:
    def __init__(self, config: BTConfig):
        self.config = config
        self.trades: list[TradeRecord] = []
        self.equity_curve: list[EquityPoint] = []
        self.gate_stats: dict[str, GateStats] = defaultdict(GateStats)
        self.regime_stats: dict[RegimeLabel, RegimeStats] = defaultdict(RegimeStats)

    def run(self, klines: list[Kline], snapshots: list[MarketSnapshot]) -> BacktestResult:
        \"\"\"
        逐根 K 线：
        1. 构造 MarketSnapshot（含该时刻的 TV 指标、Binance 数据、宏观、新闻）
        2. 调用 run_decision_loop(snapshot) → FinalVerdict
        3. 若 verdict.go：模拟下单、持仓管理、止损/目标触发、滑点/手续费
        4. 记录：逐笔交易、权益曲线、闸门通过率、体制分栏统计
        \"\"\"
        for i, (kline, snap) in enumerate(zip(klines, snapshots)):
            verdict = run_decision_loop(snap)
            self._process_verdict(verdict, kline, snap)
            self._manage_open_positions(kline)
            self._record_equity(kline.close)
        
        return BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            gate_stats=self.gate_stats,
            regime_stats=self.regime_stats,
            overfit_score=self._compute_overfit(),
        )

    def _process_verdict(self, verdict: FinalVerdict, kline: Kline, snap: MarketSnapshot):
        if not verdict.go:
            # 记录闸门拦截原因
            for gate in verdict.gates:
                if gate.status == "red":
                    self.gate_stats[gate.gate_name].blocked += 1
                elif gate.status == "yellow":
                    self.gate_stats[gate.gate_name].warned += 1
                else:
                    self.gate_stats[gate.gate_name].passed += 1
            return
        
        # 模拟入场
        plan = verdict.plan
        entry_price = plan.entry * (1 + self.config.slippage * (1 if plan.direction == "long" else -1))
        trade = TradeRecord(
            entry_time=snap.ts,
            entry_price=entry_price,
            direction=plan.direction,
            stop=plan.stop,
            targets=plan.targets,
            size=verdict.risk_usd / abs(entry_price - plan.stop),
            model_id=plan.model_id,
            regime=snap.feature_vector.regime,  # 体制标签，用于分栏统计
            rr=plan.rr,
        )
        self.open_trades.append(trade)
        
        # 闸门统计
        for gate in verdict.gates:
            self.gate_stats[gate.gate_name].passed += 1

    def _manage_open_positions(self, kline: Kline):
        \"\"\"检查止损/目标/超时强平，产出平仓记录\"\"\"
        for trade in self.open_trades[:]:
            exit_price, exit_reason = self._check_exit(trade, kline)
            if exit_price:
                pnl_r = (exit_price - trade.entry_price) / (trade.entry_price - trade.stop) * (1 if trade.direction == "long" else -1)
                trade.exit_price = exit_price
                trade.exit_reason = exit_reason
                trade.pnl_r = pnl_r
                trade.exit_time = kline.timestamp
                self.trades.append(trade)
                self.open_trades.remove(trade)
                
                # 体制分栏统计
                self.regime_stats[trade.regime].add_trade(trade)
```

### Walk-Forward 验证接入

> ⚠ **落地状态（2026-09-13 实测核实）**：本节是**设计稿**——`scripts/walk_forward_v2.py`
> 与 `walk_forward_v2()` 从未落地（照本节直接跑会失败）。仓库里真实存在的是：
> - `scripts/backtest_runner_v2.py` —— 现行回放器（`replay_shadow_records` / `_regime` / `_snapshot_parts`）
> - `scripts/regime_backtest.py` —— 体制分栏回测 + 过拟合体检（`split_by_regime` / `overfit_health_check` / `classify_regime` / `format_regime_report`）
> - `scripts/_disabled/walk_forward.py` —— 早期 Walk-Forward v1.0（三段 60/20/20），**已退役**；恢复前必须先验证可跑
>
> 下面保留设计原貌（三段分割口径与闸门通过率分析仍然有效），落地时按上述真实模块接线。

```python
# 目标形态（设计稿）——当前请用 scripts/regime_backtest.py + scripts/backtest_runner_v2.py

def walk_forward_v2(runner: BacktestRunnerV2, klines: list, snapshots: list, 
                    train_pct=0.6, val_pct=0.2, test_pct=0.2) -> WFResult:
    \"\"\"
    训练集：跑 bayesian_optimizer 寻优参数 → 选最优参数组合
    验证集：用最优参数跑 backtest_runner_v2 → 记录指标
    测试集：用相同参数跑 backtest_runner_v2 → 对比验证集指标
    \"\"\"
    n = len(klines)
    train_end = int(n * train_pct)
    val_end = train_end + int(n * val_pct)
    
    # 训练集优化参数
    best_params = bayesian_optimize(klines[:train_end], snapshots[:train_end])
    
    # 验证集/测试集用相同参数跑决策闭环
    val_result = runner.run_with_params(klines[train_end:val_end], snapshots[train_end:val_end], best_params)
    test_result = runner.run_with_params(klines[val_end:], snapshots[val_end:], best_params)
    
    overfit_score = abs(val_result.sharpe - test_result.sharpe) * 100
    return WFResult(
        overfit_score=overfit_score,
        val_sharpe=val_result.sharpe,
        test_sharpe=test_result.sharpe,
        param_stability=check_param_stability(best_params, ±10%),
        gate_pass_rates=test_result.gate_pass_rates,  # 新增：闸门通过率分析
    )
```

### 闸门复跑报告（新增）

回测输出必须包含：
- 各闸门通过率（`gate_stats[gate].passed / total`）
- 各闸门拦截原因分布（Top 3）
- 体制×闸门 交叉表：哪些体制下哪个闸门最常拦截
- 模型×闸门 交叉表：哪些模型最常被哪个闸门拦截

```json
// data/backtest_gate_report.json
{
  "gate_pass_rates": {
    "data_freshness": 0.98,
    "tv_live": 0.95,
    "rr_ratio": 0.87,
    "event_window": 0.92,
    "protections": 0.81,
    "wfo_samples": 0.73,
    "dual_indicator": 0.89,
    "portfolio_exposure": 0.96
  },
  "top_block_reasons": {
    "protections": ["日回撤熔断", "连亏3停", "止损冷却"],
    "rr_ratio": ["目标位被结构位压制", "止损过宽导致R:R<2"]
  },
  "regime_x_gate": {
    "range_vol": {"protections": 0.45, "dual_indicator": 0.38},
    "bull_normal": {"rr_ratio": 0.12}
  }
}
```

### 权益曲线 + 体制分栏 + 闸门分析三位一体

`equity_tracker.py` 输出 dashboard.html 必须包含：
1. 总权益曲线
2. 体制分栏权益曲线（9 体制各自一条线）
3. 闸门通过率随时间变化（滚动 100 笔）
4. 逐笔交易表：含 `regime`、`gates_passed`、`gate_blocked_by` 字段

## 真实TV闭柱影子校准（2026-07-10）

旧回测若用滚动高低中点近似 VAH/VAL/POC，不能验证当前生产 SVP/FVG/OB，也不能用来调整实盘仓位。生产校准应先影子记录真实 TV MCP 闭柱候选：

- `signal_id` 幂等写入 JSONL；
- 保存资产、周期、体制、主模型、方向、入场/止损/目标/R:R、FVG/OB质量、HALDRO Valid/Risk、FinalVerdict及阻断原因；
- 后续4/8/16根记录 MFE/MAE、先止损/先目标、触发耗时；同根双触发按止损优先，避免乐观偏差；
- 按 `资产→周期→体制→主模型` 分组，样本少于30不输出校准概率；
- 写死的 legacy `confidence` 是模型标签，不是胜率，禁止用于仓位或概率文案；
- 回测必须复跑同一 `decision_loop`，并验证 `WAIT/NO-GO` 没有生成交易。

若置信桶出现“分数越高，OOS胜率/平均R越低”，先判定为校准失效，不要简单反转分数；应追查分数是否只是模型类型编码、样本是否失衡、回测是否同构。

详细不变量见 `trading-system-architecture-design/references/final-verdict-shadow-calibration-2026-07-10.md`。

## 陷阱

- 回测覆盖率 BTC 46-69% 是正常的——7个BTC-XAU共用模型，4个需futures数据
- 回测数字有趋势偏差！不可直接用于计算实盘仓位
- 数据桥修复：引擎模型期望嵌套key结构（`data[\"taker_futures\"][\"ratio\"]`），非平键（`data[\"taker_ratio\"]`）
- 时间框架锁定：BTC=15m, XAU=5m（不可混用）
- **新陷阱（vNext）**：旧版 `backtest_runner.py` 直接调用模型函数，绕过闸门/体制/风控。**必须迁移到 `backtest_runner_v2.py` 走 `decision_loop`**，否则回测/实盘不一致。
