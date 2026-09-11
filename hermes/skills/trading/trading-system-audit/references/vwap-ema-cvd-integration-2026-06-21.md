# VWAP+EMA+CVD 本地引擎 + 全链路接入 v1.0 (2026-06-21)

## 新建模块: scripts/vwap_ema_cvd_engine.py (333行)

本地计算引擎（不依赖 TV CDP 连接），完全对齐棠溪 Pine 指标参数：

### 函数矩阵
| 函数 | 输入 | 输出 | Pine参数对齐 |
|------|------|------|-------------|
| `calc_vwap()` | OHLCV列表 | VWAP + 1σ/2σ带 + 价vs位置 | `VWAP_SD_MULT_1=1.0` `VWAP_SD_MULT_2=2.0` |
| `calc_ema()` | close列表 | EMA数列 | 9/21/34/55 递归 |
| `calc_ema_cloud()` | 各期EMA值 | 快云/慢云/趋势强度 | `EMA_12_CLOUD` / `EMA_34_CLOUD` |
| `calc_atr()` | OHLC列表 | ATR(14) | True Range + EMA平滑 |
| `analyze_cvd_absorption()` | CVD dict | 吸收/派发/模式/置信 | `CVD_ABSORB_LEN=12` `CVD_ABSORB_PRICE_ATR=0.8` |
| `vwap_ema_cvd_summary()` | K线列表 | 一键dict | 全链路 |

### 实测输出 (BTC回测)
```
VWAP: 64942.13 · 价在下 · 1σ-2σ
EMA: 快空头云 · 慢空头云 — 强趋势·空头排列
ATR(14): 139.7
```

## 分析卡接入 (auto_card.py)

### 注入位置
- **完整卡 环境段⑧**: `VWAP {vwap} · 价在{VWAP上/下}·{σ带} · EMA 快{云}·慢{云} — {趋势强度}`
- **完整卡 环境段⑨**: `对抗：Bull {n} vs Bear {n} — {分歧度}·{方向}占优`
- **完整卡 结构段⑤**: VWAP带 +1σ/-1σ/+2σ/-2σ（增强行）
- **极简卡**: 单行VWAP/EMA紧凑注入

### 关键代码注入
```python
# render_card_locked() 入口 → VWAP/EMA计算 (L415-431)
from vwap_ema_cvd_engine import vwap_ema_cvd_summary
vwap_ema = vwap_ema_cvd_summary(symbol, klines)
engine_data["_vwap_ema"] = vwap_ema

# 环境段 → ⑧⑨ 渲染
_vwap_ema_display(vwap_ema)  # → L480
# ⑨ 对抗视角同步注入
```

### 新增辅助函数
```python
_vwap_ema_display(vwap_ema: dict) -> str  # 环境段⑧
_vwap_structure_line(vwap_ema: dict) -> str  # 结构段VWAP带
```

## 警报接入 (行情守望.py)

### 注入机制
`process_block` → 在 `allow_push` 分支中:
```python
from vwap_ema_cvd_engine import vwap_ema_cvd_summary
vwap_ema_alert = f"VWAP {v} {vs}·{fast_cloud}·{trend[:10]}"
macro_text = f"{macro_text or ''} | {vwap_ema_alert}".strip(" |")
```
数据追加到 `macro_text` → 通过 `render_message` 的 `⑤ 宏观` extras 行输出。

## 模板变更 (master-template-v68.md v6.9.16)

- 环境段新增 ⑧ VWAP/EMA ⑨ 对抗视角
- 结构段⑤ 新增 VWAP带子行
- 新铁律⑬: VWAP+EMA+CVD三合一≥2同向才A级
- 新铁律⑭: VWAP σ带动态S/R（1σ均衡·2σ偏轨·3σ禁追）

## 社区审计依据
- X/Twitter 2026共识: VWAP+EMA+CVD三合一是当前黄金标准
- Reddit r/Daytrading: SD bands回测价值区判定
- Bookmap: CVD absorption alignment

## 测试状态
- 103/104 passed (1 watchdog ratelimit infra)
- 引擎本地计算验证通过
- auto_card导入+渲染函数测试通过
