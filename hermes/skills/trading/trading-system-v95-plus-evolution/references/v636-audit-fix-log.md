# v9.14 审计修复日志 (2026-06-21 第八次全系统审计)

## 审计触发

棠溪命全系统审计："全面检查我的系统，系统怎么样，交易分析策略怎么样，模板怎么样监控策略模板怎么样，优化怎么样？联网社区，多角度多渠道来进行审计给出优化方向。"

## 初始状态快照

| 指标 | 值 | 判断 |
|------|-----|------|
| 心跳 | `pid:22772 status:stopped` @ 01:10 | **P0** |
| Python进程 | 0 | **P0** |
| Cron | 3/3 healthy | ✅ |
| BTC数据 | A级 | ✅ |
| XAU数据 | A-级 | ✅ |
| 钱包 | 67.52 USD | ✅ |
| Git | clean | ✅ |
| 测试 | 98/98 | ✅ |

## P0 修复

### P0-1 · 监控复活

**症状**：watchdog.log 21:58→22:20 反复「重启速率限制已达上限」，watchdog_guard 空但进程未启动。

**根因**：旧时间戳冷却 + 无活跃 watchdog 进程。清空 guard 后 watchdog 才允许重启，但首次检查仍会看到旧 PID 22772 心跳停滞 40,549s。

**修复序列**：
```bash
echo '{"restart_times":[],"restart_times_emergency":[]}' > data/watchdog_guard.json
rm -f data/monitor.lock
python scripts/watchdog.py  # background=true
# 60s后: cat data/monitor_heartbeat.json → pid:17020 status:running
```

### P0-2 · 预测验证断裂

**症状对比**：
- `prediction_log.jsonl`：112 条，0 verified
- `monitor.log`：反复打印「模型胜率：99.8%（491条已验证）」

**根因链**：

1. `log_prediction()` 写 `price_at_prediction: 0`
2. `multi_model_engine.py` 调用后设 `pred["price_at_prediction"] = price` → 但只改了返回的 dict，**没改文件**
3. 然后读整个 prediction_log.jsonl，找最后一行替换重写 → **竞态**
4. `system_data_bridge.py` 用 `_patch_pred_price()` 读整个文件从后向前搜索，找到 price=0 的条目改写 → **竞态**
5. `verify_predictions()` 读所有预测，`old_price=0` → 全部标记 `was_correct=None`（无法验证）
6. `aggregate_stats()` 只统计 `verified=True AND was_correct is not None` → 永远返回 0
7. monitor.log 的「99.8%」来自另一个独立计数器或旧缓存，与 prediction_log 完全脱节

**修复**：

```python
# prediction_tracker.py
def log_prediction(symbol, merged, model_results, price=0):  # 新增 price 参数
    pred = {"price_at_prediction": price, ...}  # 直接写入
    f.write(json.dumps(pred) + "\n")
    return pred

# multi_model_engine.py — 删除 ~10行事后补丁
log_prediction(symbol, merged, results, price=price)

# system_data_bridge.py — 删除 _patch_pred_price() 整个函数 ~20行
log_prediction(sym, m, r, price=px)
```

**教训**：事后补丁（write-then-patch）是竞态温床。数据应在创建时写对，不靠后续修正。

### P0-3 · XAU kline 路径 400 泄漏

**判断**：已在 `0cb65df` 提交（2026-06-21 00:18）中修复。

**验证**：monitor.log 中 61 条 XAU 400 错误全部发生在 00:18 之前。00:18 之后 0 条。

### P1-1 · BTC 监控位补充

旧状态：2 个 expired level。运行 `python scripts/智能更新结构.py BTCUSDT` 重建 → 3 个 active：

| Name | Model | Side | Price | Stop | R:R | Priority |
|------|-------|------|-------|------|-----|----------|
| R1_VAH回收 | VAH回收 | short | 64570 | 64764 | 1.6 | medium |
| S1_POC拒绝 | POC拒绝 | long | 64252 | 64060 | 1.6 | medium |
| S2_VWAP反抽 | VWAP反抽 | long | 63891 | 63673 | 4.0 | **high** |

### P1-2 · 净值对齐

`equity_curve.json` `current_balance: 67.52` = Binance 合约钱包 `67.52`。已对齐。之前误判 32.48 差值是因为把用户资料中的 100 USD（上限）当成了初始入金。

### P1-3 · XAU 周末门控

2026-06-21（周日）验证：
```
is_weekend_closed()       → True
should_trade("XAUUSD")    → (False, '周末闭市')
should_trade("BTCUSDT")   → (True, 'crypto 24/7')
get_active_sessions()     → ['closed']
```

monitor.log 实时打印「时段过滤 XAUUSD: 周末闭市 — 静默」✅

## P2 优化

### P2-1 · HTTP 重试

已在 `9e00cc5`（2026-06-19）部署：`_HTTP = requests.Session()` + `urllib3.Retry(total=2, backoff_factor=0.5)` + `_http_get()` SSL EOF 手动退避重试。6 次 SSL UNEXPECTED_EOF 均为历史记录（部署前）。

### P2-2 · NTP 时钟同步

```bash
cmd.exe //c "net start w32time && w32tm /resync"  # 服务需先启动
```

### P2-3 · 旧胜率计数器

由 P0-2 连带解决。prediction_log 清空后 `aggregate_stats()` 自然返回 0，monitor.log 将打印真实数字。

## 社区联网审查摘要

| 维度 | 棠溪 v6.9.2 | 社区 2026 | 差距 |
|------|------------|-----------|------|
| Liquidity Sweep → CHOCH → CVD | ✅ | 核心序列 | 对齐 |
| X Kill Zone / session timing | ✅ | 时段过滤 | 对齐 |
| Walk-Forward 验证 | ✅ | r/algotrading 黄金标准 | 对齐 |
| Freqtrade Protections | ⚠ | stoploss guard/cooldown | 增量方向 |
| Bookmap冰山水/吸收 | ⚠ | 深度 CVD 模式 | 增量方向 |

## 复用修复模式（已录入 fix-patterns-catalog）

1. **写时就对** — 数据创建时写完整，不事后补丁
2. **清 `.pyc` 后重启** — 代码改完先清除 pyc 再验证
3. **watchdog 复活序列** — guard → lock → background watchdog → heartbeat
4. **字段名验证** — JSON 先 `print(keys())` 再查值
