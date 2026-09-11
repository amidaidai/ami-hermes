# 监控-引擎接线架构 v7.5（2026-06-19 闭环修复）

棠溪交易系统的脚本分两个目录，接线错误会被 bare except 静默吞掉，导致"代码存在但从未运行"。本文件记录正确架构和踩过的坑。

## 双目录架构（关键）

| 目录 | 内容 | 运行时谁在跑 |
|------|------|------------|
| `D:/Hermes agent/scripts/` | 监控守护：`行情守望.py`、`信号巡检.py`、`system_data_bridge.py`、`智能更新结构.py`、`five_model_matcher.py`、`prediction_tracker.py`(副本)、`indicator_feed.py` | 监控进程从这里启动 |
| `D:/Hermes agent/hermes/scripts/` | **引擎权威版**：`multi_model_engine.py`、`data_gatherer.py`、`prediction_tracker.py`(权威·211行) | 引擎逻辑真身 |

陷阱：`scripts/multi_model_engine.py` 和 `scripts/data_gatherer.py` 曾是**指针文件**（只 print 一行提示），真身在 `hermes/scripts/`。skill 目录里的同名文件也是指针。盲目复制指针文件会覆盖真相 —— 改接线前先 `head` 看是不是指针。

**正确跨目录 import**：scripts/ 下的脚本要 import 引擎时，必须把 `hermes/scripts` 加进 sys.path：
```python
eng_dir = str(Path(__file__).resolve().parent.parent / "hermes" / "scripts")
if eng_dir not in sys.path:
    sys.path.insert(0, eng_dir)
```
`行情守望._verify_predictions_if_needed` 已正确这样做；`system_data_bridge.dir_flip` 旧版做错了（见下）。

## 预测闭环（P0·此前完全没跑）

链路：`dir_flip()` 跑引擎 → `log_prediction()` 记录 → 4h后 `行情守望._verify_predictions_if_needed` 回验 → `aggregate_stats()` 出胜率。

此前断在两处：
1. `system_data_bridge.dir_flip` 双重 bug：①模块顶部**没 import sys** → `sys.path.insert` 抛 NameError 被 `except: return False` 吞；②加的是 `Path(__file__).parent`(=scripts/) 而非 hermes/scripts/。两者叠加 → 方向翻转检测+引擎预测从来没运行过。
2. `log_prediction` 从未被任何地方调用 → `prediction_log.jsonl` 停在 6 条（两天没新增）。

修复 v1.1：dir_flip 内 `import sys as _sys`、path 指向 `parent.parent/hermes/scripts`、跑完引擎调 `log_prediction(sym, m, r)`，再用 `_patch_pred_price` 把 price_at_prediction 从 0 补成真实价（log_prediction 默认写 0）。验证：dir_flip 实跑后 prediction_log 从 6→7，新条目带真实价。

## 五模型接入监控位（P1-1·此前永远退化到假位）

`智能更新结构.build_levels_v2` 调 `five_model_matcher.generate_all_setups` 生成真实 R:R 入场位。此前死在：它从 `system_data_bridge._LAST[symbol]['tv']` 取指标，但 `_LAST` 只存方向字符串（`_LAST[sym]=nd`），没有 'tv' 子键 → tv_indicators 恒空 → 五模型从不触发 → 永远退化到 `build_levels` 硬编码假位（type=breakout_accept/retest，无 R:R）。

修复 v2.1：新建 `scripts/indicator_feed.py::build_indicators(symbol)` —— 拉真实 K线（BTC走 Binance `/api/v3/klines`，XAU走 Yahoo `GC=F` 代理，减溢价），复用 `backtest_runner.py` 的 calc_ema/calc_atr/calc_vwap + 成交量分布算 POC/VAH/VAL，返回喂给 generate_all_setups 的 dict。接入后监控位变 `type=five_model`、display_name 含模型名+入场价、action 含 `R:R{n}`。
- `build_indicators` 签名是 `(symbol, interval="15m")`，**不是** `(symbol, price)`。
- 真身函数名 `build_indicators`，不是 `build_indicator_feed`。

陷阱：**XAU 的 R:R 会虚高**（实测 VWAP反抽 R:R=40.2）。因为 XAU ATR≈9 止损距离极小，入场到 VWAP 距离相对很大 → R:R 失真。挂这种位会误导。需给 R:R 加合理上限（>10 视为异常→回退或标记），病根在 `five_model_matcher` 的 rr_ratio 计算。

## 警报推送按品种路由（v7.5）

chat = `-1003733144325`。路由表：
- BTC 警报 → topic `386`
- XAU 警报 → topic `385`
- 其他警报 → topic `416`（默认回落）
- 任务报告（非警报：系统体检/安全审计/每日验证/心跳卡）→ topic `846`

实现：`行情守望.py` 加 `alert_target_for(symbol)` + `report_target()`；推送队列元素从纯字符串改为 `(target, msg)` 元组；`push(msg, target=None)` target 省略回落 416；4 个警报 render_message 调用点传 `target=alert_target_for(symbol)`。worker 向后兼容纯字符串。

## 关键位全景区（v7.5）

警报卡触发单个位时，用户要看全部近端关键位全景。`render_message(..., all_levels=items)` 新增"关键位全景"区：`sort_levels_panorama` 排序（阻力高→低在上，支撑高→低在下），触发位走 `format_hit` 详细展开+标 `◀ 已触发`，未触发位走 `format_level_brief` 单行（简称·价位·距离·位信）。4 个调用点都传 `all_levels=items`。

## 安全隐患（待修）

`system_data_bridge.py` 顶部硬编码了 Binance API Key/Secret 明文（`BK=...`/`BS=...`）。应移到 `hermes/secrets/` 并改 env 读取。
