# auto_card VWAP/EMA 引擎饿死诊断与修复（2026-07-07）

## 症状
实跑 `python scripts/auto_card.py BTCUSDT` 时打印：
```
⏭ VWAP/EMA引擎：无K线数据，跳过
```
且 BTC 卡 GO/NO-GO 长期 NO-GO（R:R 0.5<2.0），即使 TV 缓存正常注入。

## 根因（非网络问题）
主流程 crypto 分支（约 2718-2784 行）只拉 CMC/Binance ticker 价格，
**从未调用 `_collect_binance_data(engine_data, symbol)` 填充 `engine_data["klines"]`**。
导致两处读不到 K线：
- 第 3014 行 `VWAP/EMA引擎` 读 `engine_data.get("futures_klines", [])` → 永为空 → 跳过
- 第 821 行 `vwap_ema_cvd_summary` 兜底读 `engine_data["_raw_klines_multi"]`（数据在但路径未接通）

## 诊断命令
```bash
cd "D:/Hermes agent"
# 确认主流程是否真的填了 klines
grep -n "_collect_binance_data\|engine_data\[.klines.\]\s*=\|futures_klines" scripts/auto_card.py
# 如果只有 _collect_binance_data 定义、无调用 → 饿死确认
```

## 修复模式
1. crypto 分支 quality=A 后置插入：
   ```python
   try:
       _collect_binance_data(engine_data, symbol)
   except Exception:
       pass
   ```
2. 第 3014 行改为优先读 `_raw_klines_multi["15m"]` 重组 OHLCV：
   ```python
   _raw_15m = engine_data.get("_raw_klines_multi", {}).get("15m") or []
   if isinstance(_raw_15m, list) and _raw_15m:
       _klines_raw_for_ve = [
           {"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
            "close": float(c[4]), "volume": float(c[5])}
           for c in _raw_15m if isinstance(c, (list, tuple)) and len(c) >= 6
       ]
   ```
3. Binance klines 拉取（`_collect_binance_data` 内循环）加多源回退：
   `fapi.binance.com` → `api.binance.com/api/v3` → `data-api.binance.vision/api/v3`，
   timeout 6s，任一成功即 break。

## 修复后验证
```
✅ VWAP/EMA引擎：快线63304.08·慢线63303.21·CVD方向卖
🚦 GO/NO-GO: ✅ GO · 绿灯6/8
```

---

# 行情守望看门狗 cron 创建实战（2026-07-07）

## 错误写法（会失败）
```bash
hermes cron create "3 */1 * * *" --name "行情守望看门狗" \
  --script market_watchdog.py --mode no-agent --workdir "D:/Hermes agent"
# ❌ unrecognized arguments: --mode no-agent
# ❌ cron 运行 failed（script 路径无子目录前缀解析不到）
```

## 正确写法
```bash
hermes cron create "3 */1 * * *" --name "行情守望看门狗" \
  --script monitor/market_watchdog.py --no-agent \
  --workdir "D:/Hermes agent" --deliver telegram:-1003733144325:846
# ✅ --no-agent 是标志（无值）；script 带子目录前缀 monitor/
```

---

# XAU auto_card 超时根因与三段式修复（2026-07-11）

## 症状
`timeout 90 python scripts/auto_card.py XAUUSD` 在 90s 内只输出 9-11 行（卡在数据采集阶段），exit_code=124（超时杀掉）。BTC 正常跑完。

## 根因（三段累积阻塞，非单一问题）

| 段 | 代码位置 | 阻塞原因 | 耗时 |
|---|---|---|---|
| ① XAU前置同步 | L3169 `xau_tv_sync.py` subprocess | timeout=30s，超时抛 `TimeoutExpired` 被外层 except 捕获，但已浪费 30s | 30s |
| ② tv_live_dump | L3176 `tv_live_dump.py` subprocess | XAU 已由 xau_tv_sync 完成 TV 同步，但代码继续跑 tv_live_dump（重复等待） | 45s |
| ③ Binance klines | `_collect_binance_data` L2543 | XAUUSDT 拉 4 周期 klines × 6s timeout = 最坏 24s | 17-24s |
| 合计 | | | 75-99s |

## 修复（三段全部降级）

### ① xau_tv_sync：30s → 20s + 显式捕获 TimeoutExpired
```python
# 修复前
xau_sync = subprocess.run([...timeout=30...])
if xau_sync.returncode != 0:
    print(f"  ⚠ XAU五层前置同步失败...")

# 修复后
try:
    xau_sync = subprocess.run([...timeout=20...])
    if xau_sync.returncode != 0:
        print(f"  ⚠ XAU五层前置同步失败...")
except subprocess.TimeoutExpired:
    print(f"  ⚠ XAU五层前置同步超时20s，降级继续")
```

### ② XAU 跳过 tv_live_dump（XAU 专用路径）
```python
# 修复前：XAU 跑完 xau_tv_sync 后继续跑 tv_live_dump（双等）
# 修复后：XAU 分支独立处理，跳过 tv_live_dump
if _asset_class(symbol) == "gold":
    # xau_tv_sync 完成后直接标记 ready，不再跑 tv_live_dump
    engine_tv_ready = True
    print(f"  ✅ TV分析前置刷新: {symbol} {tf_main} (XAU专用路径)")
else:
    tv_refresh = subprocess.run([...tv_live_dump...timeout=45...])
    engine_tv_ready = tv_refresh.returncode == 0
```

### ③ XAU klines：4周期6s → 2周期3s
```python
# 修复前
for tf, limit in [("5m", 30), ("15m", 100), ("1h", 100), ("4h", 50)]:
    data = fetch_spot(..., timeout=6)

# 修复后
_xau_tf_limit = [("15m", 100), ("1h", 100)] if is_xau else [("5m", 30), ("15m", 100), ("1h", 100), ("4h", 50)]
_xau_timeout = 3 if is_xau else 6
for tf, limit in _xau_tf_limit:
    data = fetch_spot(..., timeout=_xau_timeout)
```

## 修复后验证
```
⚠ XAU五层前置同步超时20s，降级继续
✅ TV分析前置刷新: XAUUSD 5m (XAU专用路径)
✅ VWAP/EMA引擎：快线4114.603·慢线4107.235·CVD方向买·TV MCP
🛡️ Protections通过
📸 主周期截图: ...XAUUSD_5m_20260711_181306.png
🚦 GO/NO-GO: ○ WAIT · 等待：no_direction · 绿灯5/8
管线路由：8步 · 完成 7/8
```

## 通用教训
- XAU 管线超时不是单点而是多段累积。逐段计时定位（`price_consensus` 12s + `_collect_binance_data` 17s + TV前置 30s）才能找到真正的阻塞。
- `subprocess.run` 的 `timeout` 参数超时会抛 `TimeoutExpired`，必须在 `try/except` 中显式捕获，否则被外层泛化 except 捕获后行为不可预期。
- 已有 `xau_tv_sync` 完成的工作不应用 `tv_live_dump` 重复做。XAU 和 BTC 的 TV 数据路径应分离。
