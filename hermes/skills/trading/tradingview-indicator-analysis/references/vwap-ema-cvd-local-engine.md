# VWAP+EMA+CVD 本地计算引擎

◷ 2026-06-21 · 本会话产出 · 333行新建

## 设计目标

TV MCP不可用时（CDP连接失败/TV未运行），从Binance K线数据本地计算 VWAP/EMA/CVD，
完全对齐棠溪自定义 Pine Script 指标参数。

## 模块结构（`scripts/vwap_ema_cvd_engine.py`）

| 函数 | 输入 | 输出 | 对齐Pine |
|------|------|------|---------|
| `calc_vwap()` | OHLCV数组 | VWAP + 1σ/2σ带 + 价在上下 + 带内/外 | VWAP_SD_MULT_1=1.0, 2=2.0 |
| `calc_ema()` | close数组, period | EMA递归序列 | Pine ta.ema |
| `calc_ema_cloud()` | {period: ema[]} dict | 快云(9/21)·慢云(34/55)·趋势强度 | EMA_12_CLOUD, EMA_34_CLOUD |
| `calc_atr()` | OHLC数组 | ATR(14) | True Range + EMA |
| `analyze_cvd_absorption()` | cvd_data dict | 吸收/派发+置信度 | CVD_ABSORB_LEN=12, ABSORB_PRICE_ATR=0.8 |
| `vwap_ema_cvd_summary()` | K线列表 | 完整摘要dict | 全链路 |

## 注入点位

1. **完整分析卡** — `auto_card.py::render_card_locked()`
   - 环境段⑧: `_vwap_ema_display()` 单行
   - 结构段: `_vwap_structure_line()` VWAP带

2. **极简卡** — `auto_card.py::_compact_card()`
   - VWAP行: 从 `engine_data["_vwap_ema"]` 提取

3. **实时警报** — `行情守望.py::process_block()` 的 `allow_push` 块
   - 从 block/klines 提取数据 → `vwap_ema_cvd_summary()` → 追加到 `macro_text`

## TV vs 本地优先级

当 TV MCP 可用时，优先使用 TV Pine 指标值（tick级精度）：
- `tv_vals["S VWAP"]` → 覆盖本地VWAP
- `tv_vals["EMA 9"]` → 覆盖本地EMA
- TV DMI决策表 → 覆盖本地CVD判断

TV不可用时，本地引擎透明接替（K线级近似·精度损失约100-300点）。

## 测试验证

```bash
python -c "
from vwap_ema_cvd_engine import vwap_ema_cvd_summary
klines = [...]  # Binance K线
result = vwap_ema_cvd_summary('BTCUSDT', klines)
print(result['summary'])
"
```
