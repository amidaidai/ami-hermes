# v9.11 GitHub 社区借鉴 · 2026-06-18 集成记录

## 搜索结果

```
GitHub API搜索: 5轮 × 5项目 = 25个候选
最终集成: aurumcrypto + BAKOME Gold Scalper
参考架构: Freqtrade(51k⭐) / Jesse(8k⭐) / stunning-octo-robot
```

## aurumcrypto · 成本模型

**仓库**: arashMarashian/aurumcrypto ⭐1
**定位**: Python toolkit for BTC + XAUUSD signals, backtest with costs, ML, FastAPI, dashboard

**借用模块**:
1. `BTConfig` dataclass: fee_bps(双边手续费bps) + max_hold(最大持仓K线数)
2. `run_backtest()` cost model: 
   - Entry at open of bar t+1 (无look-ahead)
   - Exit: first-touch TP/SL using high/low (无价格调整)
   - Timeout: max_hold后close强平
   - Fee: `net = gross - abs(entry) * fee_rate * 2`
3. Cumulative equity with rolling max drawdown

**集成位置**: `scripts/backtest_runner.py` v1.1

## BAKOME Gold Scalper · 时段过滤

**仓库**: BAKOME-Hub/BAKOME_Python_Gold_Scalper ⭐1
**定位**: XAUUSD ICT scalper with FVG, Order Blocks, session filters, backtesting

**借用模块**:
1. Gold trading sessions: London(07-17 UTC) / NY(12-22 UTC) / Overlap(12-17 UTC)
2. Kill Zones: London Open(08-10) / London Close(15-16) / NY Open(12-14)
3. Session filter functions: `is_in_trading_session()` / `is_in_kill_zone()`

**集成位置**: `scripts/session_filter.py`

## 数据桥格式修复

**问题发现**: 回测覆盖率31%，7个引擎模型0笔交易
**诊断**: 在 `run_engine_models_for_backtest()` 打印每个模型的conf值

**根因**: 引擎模型 `model_taker_divergence(data)` 期望:
```python
data["taker_futures"]["ratio"]     # ← 嵌套dict
data["binance_spot"]["24h_change_pct"]
data["oi"]["btc"]
```
回测传入的是平键:
```python
data["taker_ratio"] = 1.0          # ← 引擎读不到，fallback=1.0
data["oi_change_pct"] = 0          # ← 引擎读不到
```

**修复路径**:
1. 查阅 `multi_model_engine.py` 中每个模型的 `data.get()` 调用
2. 在回测循环中构建完整嵌套结构
3. 计算缺失字段（24h_change_pct, top_long_pct, oi.btc等）

**修复后覆盖率**: 31% → 46% → 69%

## 测试验证

```bash
# 回测数据完整性
python -c "
import json
k=json.load(open('data/btc_klines_30d_merged.json'))
print(f'Candles: {len(k)}')
print(f'LS: {sum(1 for x in k if x.get(\"ls_ratio\"))}/{len(k)}')
print(f'GLS: {sum(1 for x in k if x.get(\"gls_ratio\"))}/{len(k)}')
print(f'Taker: {sum(1 for x in k if x.get(\"taker_ratio\"))}/{len(k)}')
print(f'OI: {sum(1 for x in k if x.get(\"oi_change_pct\"))}/{len(k)}')
"

# 全模型回测
pytest scripts/test_core.py -q  # 31/31 passed
```
