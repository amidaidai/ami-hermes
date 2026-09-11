# BTC 推送/静默决策工作流（2026-06-28 实战验证）

## 场景
5min cron 实时分析 BTC，基于 TV 双指标 + Binance 衍生品做多因子评分，决定推送分析卡还是 [SILENT]。

## 数据采集序列（已验证可并行）

### TV MCP（需 `tool_call` 调用）
```
1. tv_health_check                     # → cdp_connected, chart_symbol, resolution
2. chart_get_state                     # → studies list (SVP+ICT+VWAP+CVD, Volume, Volume Aggregated)
3. chart_set_timeframe("240")          # 4h → wait 8-12s
4. data_get_study_values               # → S VWAP, EMAs, POC/VAH/VAL, Band1/Band2
5. data_get_pine_tables                # → 行动格(结论/方向/进场/止损/目标/磁吸)
6. data_get_pine_labels                # → 会话关键位（周六高/纽高、周日亚低等）
7. data_get_pine_lines                 # → 所有水平位（去重价位列表）
8. data_get_ohlcv(summary=true)        # → 周期变化/幅度/均量
9. chart_set_timeframe("60") → repeat  # 1h → wait 8s
10. chart_set_timeframe("15") → repeat # 15m → wait 5s
11. ui_fullscreen
12. capture_screenshot(region="full")
```

### Binance MCP（可与 TV 并行）
```
get_price("BTCUSDT")                    → 价格
get_klines(interval="15m", limit=10)    → K线底部（量异常检测）
get_open_interest_history(limit=5)      → OI 趋势（增/减/平）
get_long_short_ratio()                  → 大户多空比（⚠ 反指信号：>2x 偏多=拥挤）
get_global_long_short()                 → 全局多空比
get_funding_rate_history(limit=5)       → 费率趋势（下降→降温，上升→过热）
get_taker_volume(limit=5)               → Taker买卖比（最新方向+率）
```

## 多因子评分（10分制）

| 因子 | 满分 | 数据来源 | 评分逻辑 |
|------|------|----------|----------|
| TV DMI 行动格等级 | 2 | SVP pine_tables: 结论行 | A/明确方向=2, B/有倾向=1, C/观望/冲突=0, X=-1 |
| VWAP 位置 | 2 | SVP study_values + 现价 | 多TF同侧≥2/3=2, 混搭=1, 全反=0 |
| EMA 排列 | 1 | SVP study_values | 多TF同向=1, 混合=0.5, 混乱=0 |
| CVD 方向 | 1 | Volume Aggregated: 流向行 | ▲买盘=0.5~1, ▼卖盘=0.5~1, 中性=0.5 |
| OI 趋势 | 1 | Volume Aggregated: 持仓行 + OI history | ▲新多/⚡新空+OI升=0.5~1, 矛盾=0.3, 无信号=0.5 |
| Taker 买卖比 | 1 | Binance taker_volume | 最近2根同向≥1.5=1, 混合=0.5, 逆向=0 |
| 资金费率 | 1 | Binance funding_rate | 0.001%~0.005%=中性0.6, >0.01%=热=0, <0.001%=冷=0.8 |
| 多空比反指 | 1 | Binance L/S ratio | 大户>2x=拥挤→0, 1.2~1.5=正常=0.5, <1=偏空=1 |
| 量能 | 1 | Volume Aggregated: 量能行 | ▲放量=1, ▼缩量=0.2, 正常=0.5 |
| 关键位距离 | 1 | Labels + Lines + 现价 | 距磁吸<1ATR=1, 距POC附近=0.5, 远离=0 |

**决策规则：总分 ≥ 7 且方向清晰（非⚠冲突且非X/C级）→ 推送分析卡到话题386**
**总分 < 7 或方向含⚠/X/C冲突 → [SILENT]**

## 主副指标冲突判定（2026-06-28 实战校验）

### 判据1：同TF 主副打架 → 降级
当同一时间框架下：
- 主指标结论 = `等空` / `观望` / ⚠冲突
- 副指标信号 = 🟡偏多 / 🔴偏空（但只有1/4或2/4共振）
→ 总方向不清晰 → 主副冲突 → 得分自动 ≤ 5

### 判据2：跨TF 副指标自相矛盾 → 不推送
当不同 TF 的 Volume Aggregated 给出相反信号：
- 1h 副指标: 🟡偏多·▲新多进场
- 15m 副指标: 🔴偏空·⚡新空进场
→ 方向矛盾 → 即使主指标某一 TF 有倾向也不推送

### 判据3：三联确认 C 级
SVP 行动格同时满足：
1. 结论 = `观望` 或 `等空⚠冲突` 或 `等多⚠冲突`
2. 进场 = `等触发` 或 `—`
3. 止损 = `—`
→ 自动判定 C 级 → 不推送

## 2026-06-28 实战示例

### 现场数据快照
```
BTCUSDT 现价: $60,255
4h: 价$60,255 < S VWAP $63,467 (-5%) · EMA bear stack · VAL区
1h: 价$60,255 < S VWAP $61,068 · EMA扁平簇
15m: 价$60,255 > S VWAP $60,123 (+0.2%) · EMA mild bullish
```

### 主指标行动格
```
1h: 结论"等空反抽⚠冲突" · 方向"观望·走弱·深溢价"
15m: 结论"观望" · 方向"观望·走弱"
```

### 副指标行动格
```
1h: 🟡偏多2/4 · ▲新多进场 · ▲买盘占优 · ▼缩量
15m: 🔴偏空1/4 · ⚡新空进场 · ▲买盘占优 · ▼缩量
```

### Binance 衍生品
```
OI: 102,718→102,871 BTC (+0.15% 微增)
Funding: 0.0014% (很低, 中性)
大L/S: 2.1x 偏多 → 拥挤⚠ (contrarian bearish)
全L/S: 2.02x 偏多
Taker: 最后2根 buy→buy (2.675强买), 前面3根 sell
```

### 评分结果
| 因子 | 分 | 理由 |
|------|----|------|
| TV DMI | 0 | 1h ⚠冲突, 15m 观望 |
| VWAP | 0.5 | 4h/1h低于, 15m高于 → 混搭 |
| EMA | 0.3 | 4h熊, 1h扁, 15m牛 → 混杂 |
| CVD | 0.5 | ▲买盘占优但价格走跌 = 背离 |
| OI | 0.3 | 1h ▲新多 vs 15m ⚡新空 = 矛盾 |
| Taker | 0.5 | 最新 2.675 买, 但之前 sell |
| Funding | 0.6 | 0.0014% 中性 |
| L/S | 0 | 2.1x → 偏多拥挤⚠ |
| Volume | 0.2 | ▼缩量 · "等放量再做" |
| Key Level | 0.4 | 距周日亚低 3.4ATR |
| **总分** | **3.3** | **<7 → 静默** |

### 方向判定
主副指标 **不同TF自相矛盾**（1h副🟡偏多 vs 15m副🔴偏空）+ 主指标 ⚠冲突标记
→ 方向不清晰 → 无论得分多少都不推送

### 一致性检查
主线程：4h空势内反弹，但1h/15m无共振，多源冲突 → 静默正确

## MCP 工具调用注意事项

### 延迟加载
TV MCP 和 Binance MCP 工具需要通过 `tool_call` 调用：
```python
# ✅ 正确
tool_call(name="mcp_tradingview_tv_health_check", arguments={})
tool_call(name="mcp_binance_get_price", arguments={"symbol": "BTCUSDT"})

# ❌ 错误（直接工具名不存在）
mcp_tradingview_tv_health_check()
```

### 数据等待时间
- 切 4h → wait 8-12s 让指标重算
- 切 1h → wait 8s
- 切 15m → wait 5s
- 切后重复 `study_values` 直到出现 S VWAP/EMA 值

### 品种确认
- `tv_health_check` 返回 `chart_symbol` 确认品种
- `chart_get_state` 确认 `studies` 列表含预期指标（SVP + Volume + Volume Aggregated）
- 若 TV 已连接 BTCUSDT.P 且 study 正确 → 跳过 `chart_set_symbol`，直接切 TF

## 关联参考
- `cron-push-scoring-rubric.md` — 标准化评分标准
- `svp-action-grid-states.md` — SVP 行动格等级定义
- `tradingview-indicator-analysis` skill — 棠溪完整分析卡模板
