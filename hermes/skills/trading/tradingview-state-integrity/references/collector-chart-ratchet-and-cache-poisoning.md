# 采集器抢图棘轮 + 共享缓存污染（2026-09-10 实战）

两个都由「后台任务与用户共用一份可变资源」引起，且都表现为**很难归因**的怪象。

## 一、抢图棘轮

### 现象

用户报告：「为什么图表 TV 总是在黄金 5 分钟？应该是我在哪个品种他就要哪个品种啊。」
而采集脚本的日志显示每次恢复都成功。

### 根因

```python
previous = chart_get_state()          # 进入时看到什么
... 切到 XAU 采集 ...
_restore_chart(previous)              # 恢复成“进入时那个”
```

正常路径没错。缺口在异常路径：

```
某次运行被 cron 超时杀掉 / 恢复失败
  → 图表停在 XAU 5m
  → 下一轮 previous = XAU 5m
  → 尽职地“恢复”成 XAU 5m      ← 棘轮锁死
```

关键识别：**“恢复成功”与“恢复到了正确的地方”是两件事**；日志只能证明前者。

### 修法（归属状态文件）

```python
CHART_OWNER = ROOT / "data" / "tv_chart_owner.json"

def _resolve_restore_target(cur_symbol, cur_timeframe):
    state = _load_owner()
    is_our_target = cur_symbol.upper() == SYMBOL.upper()

    if cur_symbol and not is_our_target:
        # 用户的图 → 记下来，并登记待归还
        state["user_symbol"] = cur_symbol
        state["user_timeframe"] = cur_timeframe
        state["pending_restore"] = {"symbol": cur_symbol, "resolution": cur_timeframe}
        _save_owner(state)
        return {"symbol": cur_symbol, "resolution": cur_timeframe}

    pending = state.get("pending_restore") or {}
    ps = str(pending.get("symbol") or "").strip()
    if ps and ps.upper() != SYMBOL.upper():
        # 上次没还回去 → 修回来，不要顺着残留继续“恢复”
        state["ratchet_break_from"] = cur_symbol
        _save_owner(state)
        return {"symbol": ps, "resolution": str(pending.get("resolution") or "")}

    return {"symbol": cur_symbol, "resolution": cur_timeframe}   # 用户真在看它

# finally 里恢复成功之后：
def _mark_restored():
    state = _load_owner()
    if state.pop("pending_restore", None) is not None:
        state["restored_at"] = now_iso()
        _save_owner(state)
```

### 验收（五个场景，都必须过）

1. 进入时是用户图（BTC 15m）→ 归还 BTC 15m，且写下 `pending_restore`
2. 归还成功 → `pending_restore` 被清掉
3. 构造「上次被杀」：`pending_restore` 仍在而图表停在 XAU → **归还到用户图**（打断棘轮）
4. 连续两次残留 → 不漂移，仍指向最早记录的用户图
5. 图表状态读不到（空）→ 安全返回，不误改

第 6 个隐含场景：用户真的在看采集目标品种且无 `pending_restore` → **不得干扰**。

## 二、共享缓存品种污染

### 现象

`data/tv_dmi_cache.json` 里 `symbol=OANDA:XAUUSD`、`last_price=4374`、`fresh=True` ——
但它是 BTC 的主缓存，一堆 BTC 消费者（信号落库、关键位触发、卡片兜底）在读它。

### 根因

品种门禁写成了：

```python
if not expect_symbol:          # ← 只在没传品种时才校验
    real_symbol = read_state_symbol()
    if norm(real_symbol) != norm("BINANCE:BTCUSDT.P"):
        return old_cache  # 拒绝写入
```

带 `expect_symbol` 的调用（XAU 采集）一路直写共享缓存。

### 修法

写入侧品种感知：

```python
def save_cache(data):
    if isinstance(data, dict) and data.get("symbol"):
        if _norm(data["symbol"]) != _norm("BINANCE:BTCUSDT.P"):
            atomic_write_json(_symbol_cache_path(data["symbol"]), data)  # tv_live_{KEY}.json
            return
    atomic_write_json(CACHE, data)
```

读取侧双重保险：**任何**派生计算（结构复核、关键位校验、信号落库）拿到快照后，
先校验 `snapshot["symbol"]` 包含预期品种，不匹配就直接判“无数据”，不得降级使用。

品种不匹配时如果继续计算，会得到看起来很像真结论的假结论 —— 实测出现过
「同名价值区漂移 1644.9%」这种数字，它其实只是 BTC 与黄金的价格量级差。

### 反向教训

假结论差点被当成真问题（“关键位全失效了”）。**先核品种，再核结论**；
数值离谱时优先怀疑数据源身份，而不是市场。
