# 本地引擎与数据源直调配方

> 场景：绕过编排器手动跑一遍完整管线。下面每一条都是实测跑通过的调用形态，含签名陷阱。
>
> 通用纪律：多步诊断脚本写进 `outputs/*.py` 再跑。长内联 shell（`for ...; do grep ...; done`）会被命令解析器整条拦掉 → 改写成 `outputs/*.sh` 再 `bash outputs/x.sh`。

## 0. 起手

```bash
python scripts/tv_analysis_lease.py start --minutes 12 --symbol <SYMBOL>
# ... 采完 ...
python scripts/tv_analysis_lease.py end
```

租约必须先起：后台刷新任务会在读图中途把图切走，读出来是空表。收工即 `end`。

## 1. 行情衍生品（直连优先，一次抓齐）

```
fapi/v1/ticker/price?symbol=            现价
fapi/v1/ticker/24hr?symbol=             24h 高/低/涨跌/成交额
fapi/v1/openInterest?symbol=            OI 现量
futures/data/openInterestHist?period=1h&limit=25
fapi/v1/premiumIndex?symbol=            当期资金费率 + 标记价
fapi/v1/fundingRate?limit=8             费率历史
futures/data/topLongShortPositionRatio  大户持仓多空比（反指）
futures/data/topLongShortAccountRatio   大户账户多空比
futures/data/globalLongShortAccountRatio
futures/data/takerlongshortRatio?period=15m&limit=8
```

判据：OI 涨 + 价跌 = 新空进场；OI 跌 + 价涨 = 空头回补；多空比 >2 属极偏多，当反指读；Taker <1 是卖压票。取最新的那一根 Taker 比取均值更能反映当下力度，但要在报告里写明取的是哪一根。

## 2. 宏观指数（主源不可用时的实测替代）

走本地代理，符号需 URL 编码：

```
https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=10d&interval=1d
```

`%5EGSPC` 标普 · `%5EVIX` · `%5EIXIC` 纳指 · `DX-Y.NYB` DXY · `%5ETNX` 美10Y · `GC=F` 黄金。

**日变动自己从日线 close 序列算**（最后两个非空收盘），不要用 `meta.chartPreviousClose`——时间基准不同，实测 VIX 会算出 −6.2% 而真值 −2.67%。

## 3. 引擎四连

```python
import sys; sys.path.insert(0, "scripts")
kl = [{"open":..., "high":..., "low":..., "close":..., "volume":...} for r in raw_klines]

# engine —— klines 必传
import vwap_ema_cvd_engine as v
v.vwap_ema_cvd_summary("BTCUSDT", kl)
# 不传 klines 只回 {"available": False, "reason": "无K线数据"}（不报错，容易误读成模块坏了）
# → {vwap{VWAP±1/2σ, price_vs_vwap, in_band}, ema, ema_cloud{fast/slow_cloud, ema_ranking, trend_strength}, atr, summary}

# regime —— 全 keyword-only，特征自己从 15m K 线算
import decision_regime as dr
dr.classify_decision_regime(adx=.0, atr_ratio=.0, ema_spread_atr=.0, vwap_crosses_20=0,
                            va_stay_ratio_20=.0, displacement_atr=.0, rvol=.0,
                            adr_remaining_ratio=..., vwap_distance_atr=...)
# 多传 symbol / tf_dirs 会 TypeError —— 它不接受编排器之外的调用方式
# → DecisionRegime(code, name, allowed_models, blocked_models, position_multiplier, exhausted, reason)

# scoring
import scoring_engine as se
se.score_setup(symbol="BTCUSDT", tv_levels={...}, manual_structure={...},
               cvd_value=..., taker_ratio=..., volume_ratio=..., cvd_quality="B",
               tf_consensus=2, tf_total=5, tf_details={...},
               has_fomc=True, x_direction=..., fear_greed=51)
# → total / max_score(14) / grade / breakdown / recommendation / constitution_violations

# risk
import risk_constitution_v2 as rc
rc.evaluate_risk({"symbol": "BTCUSDT", "price": ..., "entry": None, "stop": None})
```

### 15m 特征怎么算（regime 入参）

| 特征 | 定义 |
|---|---|
| `adx` | 标准 ADX(14) |
| `atr_ratio` | `ATR14 / close * 100` |
| `ema_spread_atr` | `|EMA9 − EMA55| / ATR14` |
| `vwap_crosses_20` | 近 20 根收盘价穿越 EMA20 的次数 |
| `va_stay_ratio_20` | 近 20 根落在 VWAP ± 1.5·ATR 内的占比 |
| `displacement_atr` | `|close[-1] − close[-4]| / ATR14` |
| `rvol` | 当根量 / 近 20 根均量 |

`regime=balance` 时 `blocked_models` 常含 `direct_chase / breakout_acceptance`（禁追价），`exhausted=True` 表示 ADR 已耗尽——报告里要把这两点写出来，否则会给出“顺势追入”的建议。

### 风控模块的两个坑

- 无 entry/stop 时 `violations` 会吐**假违规**（如「单笔风险 100.0% > 1% 上限」）——那是缺输入算的，不得当真实违规写进报告。
- `risk_state_status.status="stale"` 时 `allowed=False / risk_tier="blocked"`。按**可见降级**处理：写明「风险状态陈旧（日期）→ 本轮不给仓位建议」，方向结论照给，不要把整轮分析判死。

## 4. 深度 / 相关性 / 清算

```bash
python scripts/depth_wall.py <SYMBOL>     # 位置参数，没有 argparse
python scripts/correlation_matrix.py      # 首行必须显示黄金腿来源 + 偏差%
```

- `depth_wall.py` 不接 `--help`：它会把 `"--help"` 当符号去查盘口，回 `{"ok": false, "summary": "盘口不可用"}`。看起来像接口坏，其实是没 argparse。
- 逐笔清算 JSON：`coins.<COIN>.events = [[ms, "long"|"short", price, qty], ...]`，`qty` 要乘 `coins.<COIN>.ct_val` 才是币量。报告「多单强平 X vs 空单强平 Y」比报事件条数有用得多。
- 堆积带源（免 key，仅 BTC 匿名可用）：强度是**相对刻度不是 USD**，只报占比与距现价%，不得换算成金额。

## 5. 收尾自检

出报告前把这一轮实际调过的模块逐项列一遍，与路由返回的步骤列表对齐；缺的一步要写清是「本轮无有效字段」还是「源设计性停用」——两类不得混写。
