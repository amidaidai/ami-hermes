# TV DMI 决策表覆盖规范 v6.9.14

## 数据流

```
TradingView SVP+ICT+VWAP+EMA+CVD 指标
  │
  ├→ mcp_tradingview_data_get_pine_tables()  → DMI决策表文本行
  ├→ mcp_tradingview_data_get_study_values()  → CVD/POC/VAH/VAL/EMA/VWAP数值
  ├→ mcp_tradingview_data_get_pine_labels()   → ICT会话标签
  ├→ mcp_tradingview_data_get_pine_lines()    → 水平支撑阻力线
  │
  ▼
engine_data["_tv_pine"] = {"tables": [...], "studies": [...]}
  │
  ▼
auto_card.py 内部自动:
  _parse_tv_dmi_table()    → 解析 "等级 | X" → {"等级": "X", ...}
  _parse_tv_study_values() → 解析 CVD Value/Slope 等数值
  _apply_tv_dmi_override() → 覆盖 meta.status/direction/priority
  _tv_cvd_override()       → 用TV真实CVD替代Binance Taker代理
```

## Grade → Status 映射

| TV Pine Table "等级" | meta.status | meta.direction | meta.priority_plan | 卡片表现 |
|---------------------|------------|---------------|-------------------|---------|
| A多 | A做多 | long | A | 🔥TV:A多 — 回踩做多 |
| A空 | A做空 | short | A | 🔥TV:A空 — 反抽做空 |
| B多 | B等待 | long | B | TV:B多 — 轻仓等多 |
| B空 | B等待 | short | B | TV:B空 — 轻仓等空 |
| C反多 | C反转 | long | C | TV:C反多 — 站回再多 |
| C反空 | C反转 | short | C | TV:C反空 — 跌回再空 |
| X | X禁做 | wait | 无 | ⚠TV:X — 结构冲突·不进 |
| C等待 | B等待 | wait | 无 | TV:C等待 — 观望 |

## DMI 决策表字段解析

Pine table rows 格式: `"字段 | 值"`, 用 `" | "` 分割:

| 字段 | 含义 | 示例值 |
|------|------|-------|
| 等级 | A/B/C/X 分级 | X / A多 / B空 |
| 处理 | 交易姿态 | 结构冲突 / 回踩做多 / 轻仓等空 |
| 背景 | 高周期方向 | 空 4h / 多 1D |
| 位置 | 价值区位置+扩展 | VAL下方｜下方延展 |
| 量能 | 成交量状态 | 缩量试探 / 放量上收 |
| CVD | CVD状态机 | 顺多确认 / 顶背离 / 下方吸收 |
| 执行 | 当前计划 | 等:看POC / 多:回踩VWAP 64213 |
| 风控 | 失效条件 | 不进场 / 多失效:破VWAP 63692 |

## CVD 真实值替代逻辑

```python
def _tv_cvd_override(cvd_data, tv_vals):
    cvd_val = tv_vals.get("CVD Value")    # e.g. -3099.9
    cvd_slope = tv_vals.get("CVD Slope")  # e.g. -221.7

    direction = "买" if slope > 50 else "卖" if slope < -50 else \
                "中性" if abs(slope) < 10 else ("买" if slope > 0 else "卖")

    quality = "A" if abs(slope) > 500 else "B" if abs(slope) > 200 else "C"

    return {"direction": direction, "quality": quality,
            "value": cvd_val, "slope": cvd_slope, "source": "TV真实CVD"}
```

## X 级冲突处理

当 TV 判定 X 时，不生成 AB 预案，改用:

```
⚠ TV DMI 决策表: X — 结构冲突
   位置: VAL下方｜下方延展 · 量能: 缩量试探 · CVD: 顺多确认
   等: 等:看POC · 不进场
   方向不定，待结构明朗后再看。
   失效：等 TV 下一根 DMI 表更新。
```

极简卡显示: `⚠TV: X — 结构冲突 · 不进`

## 调用时机

在 auto_card() 主函数中，`build_setup_metadata()` 之后、`render_card_locked()` 之前注入:

```python
engine_data["_tv_pine"] = {
    "tables": tv_tables,    # 从 get_pine_tables 获取
    "studies": tv_studies,  # 从 get_study_values 获取
}
# render_card_locked 内部自动调用 _apply_tv_dmi_override
```

## 两个 CVD 的区别

| CVD | 来源 | 周期 | 含义 |
|-----|------|------|------|
| SVP Session CVD | SVP indicator 内 `CVD Value` | 按锚定周期 (日/周) | 本Session累计买卖压 |
| 独立窗格 1D CVD | 独立 CVD indicator | 1D固定 | 日线级别累计买卖失衡 |

两者交叉解读：Session CVD斜率收窄但1D CVD深跌 = 小周期试探但日线未反转。
