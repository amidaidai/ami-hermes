# TV MCP Pine Script 数据读取协议（2026-06-30 实测验证）

## 背景

本文件记录了棠溪双指标（`SVP+ICT+VWAP+CVD` + `Volume Aggregated Spot & Futures`）通过 TV MCP 的**实际返回格式**。所有格式均为 2026-06-30 在 GASUSDT 1D/1h 图实测验证。

## 一、TV MCP 工具返回格式

### 1.1 `chart_get_state`

```json
{
  "success": true,
  "symbol": "BINANCE:GASUSDT.P",
  "resolution": "1D",
  "chartType": 1,
  "studies": [
    {"id": "C7f7HV", "name": "SVP+ICT+VWAP+CVD"},
    {"id": "6kORjA", "name": "Volume Aggregated Spot & Futures"}
  ]
}
```

### 1.2 `data_get_study_values`

返回所有研究的 `plot()` 值，**包括 `display=display.price_scale` 和 `display=display.data_window` 的 plot**。

```json
{
  "success": true,
  "study_count": 3,
  "studies": [
    {
      "name": "Volume",
      "values": {"Volume": "3.57 M"}
    },
    {
      "name": "SVP+ICT+VWAP+CVD",
      "values": {
        "S VWAP": "1.128",
        "S VWAP +Band1": "1.213",
        "S VWAP -Band1": "1.044",
        "S VWAP +Band2": "1.297",
        "S VWAP -Band2": "0.960",
        "EMA 9": "1.097",
        "EMA 21": "1.123",
        "EMA 34": "1.186",
        "EMA 55": "1.278",
        "POC Price": "1.592",
        "VAH Price": "1.942",
        "VAL Price": "1.522",
        "nPOC Price": "3.336",
        "W VWAP Price": "1.130",
        "M VWAP Price": "1.130",
        "DO Price": "1.123"
      }
    },
    {
      "name": "Volume Aggregated Spot & Futures",
      "values": {
        "Spot (%)": "21",
        "Perp (%)": "81"
        // 以下为 2026-06-30 新增 Data Window plot：
        // "OI Total": "1234567",
        // "CVD Value": "-3200",
        // "Volume Ratio": "1.5",
        // "Composite": "31"  // 方向编码：负=空，零=无向，正=多，乘确认数编码强度
      }
    }
  ]
}
```

**已验证规则：** `display=display.price_scale` 的 plot（POC/VAH/VAL/VWAP/DO）**正常出现在 study_values 中**。不因设置 price_scale 而隐藏。

### 1.3 `data_get_pine_tables`

重要！返回表格嵌套在 `studies[].tables[]` 内，**不在顶层**。

```json
{
  "success": true,
  "study_count": 1,
  "studies": [
    {
      "name": "SVP+ICT+VWAP+CVD",
      "tables": [
        {
          "rows": [
            "结论 | 观望 ⚠冲突",
            "方向 | 观望 · 走弱 · 折价 扫0/4",
            "进场 | 等触发",
            "止损 | —",
            "目标 | ↓上周 高 1.186",
            "核对 | —",
            "磁吸↑ | --",
            "磁吸↓ | 周一 高 1.183 分90 距.6ATR"
          ]
        }
      ]
    }
  ]
}
```

**已验证规则：**
- 行分隔符是 `" | "`（空格-竖线-空格），不是裸 `|` 或 `"｜"`（全角竖线）
- 主指标行动格 v2 使用固定行标签：`结论`、`方向`、`进场`、`止损`、`目标`、`核对`、`磁吸↑`、`磁吸↓`
- **没有** `等级` 行！等级信息在 `结论` 行前缀（如 `A多 回踩` → 等级=A多）

### 1.4 `data_get_pine_labels`

```json
{
  "success": true,
  "study_count": 1,
  "studies": [
    {
      "name": "SVP+ICT+VWAP+CVD",
      "total_labels": 7,
      "showing": 7,
      "labels": [
        {"text": "POC: 3.336", "price": 3.34},
        {"text": "VAH: 4.079", "price": 4.08},
        {"text": "VAL: 2.167", "price": 2.17},
        {"text": "上周 高: 1.186", "price": 1.19},
        {"text": "上周 低: 0.942", "price": 0.94},
        {"text": "周一 高: 1.183", "price": 1.18},
        {"text": "周一 低: 1.032", "price": 1.03}
      ]
    }
  ]
}
```

### 1.5 `data_get_pine_lines`

```json
{
  "success": true,
  "study_count": 1,
  "studies": [
    {
      "name": "SVP+ICT+VWAP+CVD",
      "total_lines": 16,
      "horizontal_levels": [4.08, 3.34, 3.15, 2.17, ...]
    }
  ]
}
```

**注意：** `polyline` 对象（如 MTF VWAP 线、SVP 分布图）**不包含在 pine_lines 中**。pine_lines 只返回 `line.new()` 创建的水平线。

### 1.6 `data_get_pine_boxes`

```json
{
  "success": true,
  "study_count": 1,
  "studies": [
    {
      "name": "SVP+ICT+VWAP+CVD",
      "total_boxes": 4,
      "zones": [
        {"high": 3.2, "low": 3.09},
        {"high": 1.65, "low": 1.62},
        {"high": 1.42, "low": 1.38},
        {"high": 1.31, "low": 1.24}
      ]
    }
  ]
}
```

**注意：** 这些是 SVP v10 的 FVG 缺口区。TV MCP 的 `data_get_pine_boxes` 可以正确读取 `box.new()` 对象。

## 二、数据读取优先级

```
① pine_tables → 行动格（结论/方向/进场/止损/目标/核对/磁吸↑/磁吸↓）
② study_values → VWAP/EMA/POC/VAH/VAL/nPOC/WVWAP/MVWAP/DO
③ pine_labels → ICT会话标签、关键位定位
④ pine_lines → 支撑/阻力水平价位
⑤ pine_boxes → FVG缺口区上下边界
```

## 三、行动格 v2 字段映射

### 主指标行动格（`SVP+ICT+VWAP+CVD`）

| TV 行标签 | 映射到 engine 键 | 示例值 |
|-----------|-----------------|--------|
| `结论` | `grade`（从前缀提取：A多/A空/B多/B空/C反多/C反空/X/C等待） | `A多 回踩` → grade=`A多` |
| `方向` | `direction_text` | `偏多 · 折价 扫0/4` |
| `进场` | `entry` | `扫低收回 64,200` |
| `止损` | `stop` | `63,800 (1.2ATR)` |
| `目标` | `target` | `VAH 65,800 2.5R` |
| `核对` | `check` | `HTF✓ EMA✓ CVD✓` |
| `磁吸↑` | `magnet_up` | `VAH 65,800 分85 距1.2ATR` |
| `磁吸↓` | `magnet_down` | `VAL 64,300 分72 距0.8ATR` |

**Grade 提取规则：** `结论` 行不以任何已知等级前缀开头时 → 默认 `C等待`

### 副指标行动格（`Volume Aggregated Spot & Futures`）

| TV 行标签 | 映射到 engine 键 | 示例值 |
|-----------|-----------------|--------|
| `信号` | `signal` | `🟢 偏多 · 3/4共振` |
| `结论` | `conclusion` | `实涨可信 · 新钱+买盘 ✅` |
| `高周` | `htf` | `▲偏多` |
| `持仓` | `oi` | `▲新多进场(真)` |
| `流向` | `cvd_flow` | `▲买盘占优` |
| `量能` | `volume` | `▲放量 · 合79%⚠主导` |
| `爆仓` | `liquidation` | `空头爆仓(轧空)` |
| `操作` | `operation` | `配合主指标 A多/扫★HTF = 可做` |

**注意：** 子指标**没有独立的 `占比` 行**。占比信息（`合79%`——现货/永续比率）嵌入在 `量能` 行中。`share` 字段在映射中留空。

## 四、Python 解析注意事项

### 4.1 嵌套表格提取

TV MCP 的 `pine_tables` 返回嵌套在 `studies[].tables[].rows` 中。正确的提取代码：

```python
def _unwrap_tv_tables(raw: dict) -> list:
    tables_flat = []
    # 优先从 studies[] 嵌套提取
    studies = raw.get("studies", [])
    if isinstance(studies, list):
        for s in studies:
            s_name = s.get("name", "")
            inner_tables = s.get("tables", [])
            if isinstance(inner_tables, list):
                for t in inner_tables:
                    rows = t.get("rows", [])
                    if rows:
                        tables_flat.append({"name": s_name, "rows": rows})
    # 回退：顶层 tables
    if not tables_flat:
        top_tables = raw.get("tables", [])
        if isinstance(top_tables, list):
            for t in top_tables:
                rows = t.get("rows", [])
                if rows:
                    tables_flat.append({"name": t.get("name", ""), "rows": rows})
    return tables_flat
```

### 4.2 行解析优先级

```python
def _parse_table_rows(rows: list) -> dict:
    result = {}
    for row_text in rows:
        if " | " in row_text:       # 标准 TV MCP 格式
            parts = row_text.split(" | ", 1)
        elif "｜" in row_text:       # 全角竖线
            parts = row_text.split("｜", 1)
        elif "：" in row_text:         # 中文冒号
            parts = row_text.split("：", 1)
        else:
            continue
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result
```

### 4.3 Grade 从结论行提取

```python
GRADE_PREFIXES = ("A多", "A空", "B多", "B空", "C反多", "C反空", "C等待", "X")
def _extract_grade(dmi_rows: dict) -> str:
    grade = dmi_rows.get("等级", "")
    if grade:
        return grade
    conc = str(dmi_rows.get("结论", ""))
    for prefix in GRADE_PREFIXES:
        if conc.startswith(prefix):
            return prefix
    return "C等待"
```

## 五、已知限制

| 限制 | 说明 | 影响 |
|------|------|------|
| `polyline` 对象不在 `pine_lines` 中 | MTF VWAP（周/月折线）和 SVP 分布图无法通过 pine_lines 读取 | 不影响核心决策数据 |
| 主指标 `结论` 行不包含 `等级` 时默认 `C等待` | 当结论不以 A/B/C/X 开头时，可能错过已改善的等级但未渲染前缀 | 极少发生 |
| 子指标 `量能` 行合并占比 | 占比数据嵌入在量能行中，无独立行 | `share` 字段总是空 |
| 副指标只有加密品种可用 | `isCryptoA` 为 false 时显示「非加密品种」 | 贵金属/外汇分析时自动标注 |

## 更新历史

- 2026-06-30：初始创建，全部格式已验证
