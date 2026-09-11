# DMI 决策引擎集成模式 v1.1 (2026-06-22)

## 问题：Python 告警引擎与 Pine 指标各算各的

棠溪的 SVP+ICT+VWAP+EMA+CVD 指标（2024 行 Pine Script）内建了完整的 DMI Decision Table。
但旧的告警系统用简单的加权求和评分，与 TV 指标完全独立——两套评分体系在跑，结果常矛盾。

## 解决方案：三层对齐

### 第1层：Python 复现 Pine 逻辑
`scripts/dmi_decision.py` (333行)：
- `compute_dmi()` — Wilder's RMA 计算 ADX/DI+/DI-（DI_LEN=10·ADX_SMOOTH=10）
- `compute_atr()` — ATR(14) RMA
- `compute_scores()` — 趋势分 0-10 + 反转分 0-10，完全复现 Pine 的：
  - 价格位置(±2) · EMA排列(±2) · DMI确认(±2) · 量能(±1) · CVD(±1)
  - 扫掠检测 · VAH拒绝/VAL回收 · CVD背离/吸收/派发
  - A/B/C/X 四级 · 关键位门控(0.6ATR) · HTF过滤 · 过热禁追

### 第2层：TV 决策表直读
`fetch_tv_data.cjs` 增强 — Step 6 抓取 Pine tables（`pc.dwglabels.get('tables')`），解析等级/处理行写入 JSON。
Python 引擎收到 `tv_grade` → 覆盖本地计算（TV 为权威源）。

### 第3层：动态数据桥
`load_data()` 扩展：从 TV JSON 提取 OHLCV bars、labels、levels。
无 OHLCV 时自动拉 Binance Klines 兜底。

## 集成要点

### DMI 计算陷阱
- 必须用 Wilder's RMA（非 SMA/EMA），alpha=1/N 递推
- 至少需要 20 根 K 线（DI_LEN+ADX_SMOOTH+余量）
- ADX 默认值 50（数据不足时中性）

### CVD 6态全链路
```
顺多确认 → CVD斜率>0 且 价>5K前
顺空确认 → CVD斜率<0 且 价<5K前
顶背离   → 价新高+CVD更低高
底背离   → 价新低+CVD更高低
下方吸收 → 价压缩(≤0.8ATR)+CVD<-3×avgDelta+价在上半部
上方派发 → 价压缩(≤0.8ATR)+CVD>+3×avgDelta+价在下半部
```

### A级门控（仅A才推）
```python
setup_long_a = (
    trend_long >= 8                   # 趋势强
    and trend_long >= trend_short + 2 # 无矛盾
    and cvd_bull_confirm              # CVD确认
    and price_above_s                 # VWAP上方
    and acceptance_bull_ok            # 接受确认
    and htf_allow_long                # HTF不冲突
    and allow_a_by_location           # 关键位0.6ATR内
    and not dmi["hot"]                # ADX<40
)
```

### KillZone/Session集成
```python
from session_strategy import get_active_killzone
kz = get_active_killzone()
killzone_active = bool(kz)  # +1趋势分
```

### 周/月VWAP入评分
```python
price_above_w = w_vwap > 0 and price > w_vwap
price_above_m = m_vwap > 0 and price > m_vwap
trend_long += 1 if (price_above_w and price_above_m) else 0
```

## 验证方法

```bash
# 1. 静态编译
python -c "compile(open('scripts/dmi_decision.py').read(),'x','exec')"

# 2. 跑引擎看评分
python scripts/btc_alert_watch_v3.py
cat ~/AppData/Local/hermes/data/detector_state.json

# 3. 对比TV决策表
# 用 MCP: data_get_pine_tables → 等级/处理行
# Python 输出 grade/bias/treatment 应对齐
```

## 相关文件
- `scripts/dmi_decision.py` — DMI引擎核心
- `scripts/btc_alert_watch_v3.py` — 告警探测器（v4.0+）
- `tools/tradingview-mcp/fetch_tv_data.cjs` — TV数据桥（含Pine tables抓取）
- `hermes/scripts/session_strategy.py` — KillZone/Session检测
