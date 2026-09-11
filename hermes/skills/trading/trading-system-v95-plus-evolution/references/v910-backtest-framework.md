# v9.10 回测框架（2026-06-18 社区对比升级）

借鉴 Freqtrade(51k⭐)/Jesse(8k⭐) 补齐最后一个工程短板。

## 新增模块

| 文件 | 功能 | 来源 |
|------|------|------|
| `scripts/backtest_runner.py` | 五模型历史K线回测 | Freqtrade backtesting |
| `scripts/model_optimizer.py` | 网格搜索参数优化 | Freqtrade Hyperopt |
| `scripts/equity_tracker.py` | 权益曲线+胜率+回撤 | Jesse trade stats |
| `data/dashboard.html` | 实时监控看板(:8766) | Freqtrade FreqUI |
| `data/btc_klines_30d.json` | BTCUSDT 3000根15m K线(含taker买卖量) | Binance REST |

## 回测引擎核心能力

1. **真实CVD**: 从Binance K线自带taker buy/sell volume计算，非价格方向估算
2. **滑点模拟**: 0.1%双边滑点计入止盈/止损成交价
3. **五模型集成**: 直接调用 `five_model_matcher.generate_all_setups()`
4. **K线来源**: Binance REST `/api/v3/klines` (3000根15m = 31天)
5. **输出**: 逐笔交易+模型分层统计+权益曲线

## 诚实使用原则

⚠ **回测数字不可直接用于实盘仓位计算**：
- VWAP反抽在单边趋势中胜率虚高（96% = 路径依赖）
- 入场价设VWAP（理论最优），实际成交有价差
- VAH/VAL/POC使用简化估算（非TradingView真实Volume Profile）
- 31天窗口恰逢BTC强跌趋势，换个震荡月结果完全不同

**正确用法**：
- 模型对比：VWAP反抽 > POC拒绝 >> 扫流动性回收
- 参数筛选：R:R≥2.0比R:R≥2.5更实际
- 方向确认：验证策略在对应市场环境下的方向正确性
- 需要≥3月数据+真实TradingView指标才有统计意义

## 运行方式

```bash
# 拉数据（一次性）
python -c "
import urllib.request, json, time
all_klines = []
end_time = None
for _ in range(6):
    url = 'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=500'
    if end_time: url += f'&endTime={end_time}'
    req = urllib.request.Request(url, headers={'User-Agent':'TangXi'})
    with urllib.request.urlopen(req, timeout=15) as r:
        batch = json.loads(r.read())
    if not batch: break
    formatted = [{'time':str(k[0]), 'open':float(k[1]), 'high':float(k[2]),
      'low':float(k[3]), 'close':float(k[4]), 'volume':float(k[5]),
      'taker_buy_vol':float(k[9]), 'taker_sell_vol':float(k[5])-float(k[9])}
      for k in batch]
    end_time = int(batch[0][0]) - 1
    all_klines = formatted + all_klines
    time.sleep(0.3)
json.dump(all_klines, open('data/btc_klines_30d.json','w'))
"

# 跑回测
python -c "
from scripts.backtest_runner import backtest_from_klines, format_result
import json
klines = json.load(open('data/btc_klines_30d.json'))
result = backtest_from_klines('BTCUSDT', klines, risk_per_trade=10, min_rr=2.0, warmup=200, slippage_pct=0.10)
print(format_result(result))
"

# 参数优化
python -c "
from scripts.model_optimizer import grid_search, format_grid_results, ParamGrid
import json
klines = json.load(open('data/btc_klines_30d.json'))
# ... (see model_optimizer.py for full example)
"
```

## GitHub 社区对比方法

| 项目 | Stars | 借鉴点 | 棠溪实现 |
|------|-------|--------|---------|
| freqtrade/freqtrade | 51k | 回测·Hyperopt·Dashboard | backtest_runner·optimizer·dashboard.html |
| jesse-ai/jesse | 8k | 策略统计·权益曲线 | equity_tracker.py |
| iterativv/NostalgiaForInfinity | 3.3k | 策略治理·统计驱动调参 | strategy_governance集成 |

棠溪护城河：SMC/ICT独有·中文分析卡·A/B/C数据定级·Grok AI验证·风险宪法。
社区护城河：回测·参数优化·Dashboard·多交易所·3000+测试。
桥接：五模型写成Freqtrade策略跑回测 = 最优路径。
