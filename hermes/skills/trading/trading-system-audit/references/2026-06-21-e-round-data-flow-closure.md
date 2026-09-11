# E轮 数据流闭环优化（2026-06-21）

## 背景
前 D 轮已完成 session_filter 全资产化、multi_model 权重 adapter、模板规则。

E 轮目标：把 asset_macro_enrich 真正闭环到渲染和评分，让 DXY/US10Y/财报出现在卡片环境段和宏观加分中。

## 核心变更模式（可复用）

### 1. Bridge 层
- 新增 get_us10y_proxy()（Yahoo ^TNX）
- asset_macro_enrich 返回结构化：
  ```python
  {
    "dxy": 100.849,
    "us10y": 4.45,
    "macro_note": "DXY 100.85 · US10Y 4.45 · 美债/实际收益率",
    "event_flag": "...",
    "asset_class": "gold"
  }
  ```
- 新增 enrich_engine_data(symbol, ed) → 合并 dxy/us10y/_macro 到 engine_data

### 2. Render 入口强制富集（最关键）
在 render_card_locked 最前面：
```python
try:
    from system_data_bridge import enrich_engine_data
    engine_data = enrich_engine_data(symbol, engine_data or {})
except:
    pass
```
（必须带 sys.path 兜底到 scripts/）

### 3. 资产行函数全面替换占位
- _asset_data_line / _asset_flow_line / _asset_catalyst_line 全部改为：
  ```python
  macro = engine_data.get("_macro") or {}
  dxy = engine_data.get("dxy") or macro.get("dxy")
  ...
  return f"CVD ... · DXY `{dxy:.2f}` US10Y `{us10y:.2f}`"
  ```

### 4. 评分宏观加分
_score13 中：
```python
if ac in ("gold", "forex") and macro.get("dxy"):
    total = min(total + 1, 13)
if ac == "stock" and "财报" in ...:
    total = max(total - 1, 0)
```

### 5. 监控集成
行情守望 快照路径调用 enrich_engine_data，写入 raw["_macro"]

## 验证 Bundle（E轮必须执行）
1. python -c 测试 asset_macro_enrich + enrich_engine_data（XAU/EUR/AAPL）
2. python scripts/auto_card.py XAUUSD && BTCUSDT
3. grep 卡片：
   - "DXY `100.85`"
   - "US10Y"
   - "Spot/美元(DXY"
   - 评分中 "宏观+1" 或总分提升
4. grep -E "setup_id|model_id|..." == 0 leaks（仅主卡片）
5. git add + commit + push

## 观察证据（本轮）
- XAU 卡片：
  - ⑩ 数据：Spot/美元(DXY `100.85`) · CVD C
  - 资金：CVD ?C · DXY `100.85` US10Y `4.45`
  - 评分：7/13（宏观贡献）
- 0 machine leaks on main auto_card_*.md

## 坑点
- render 里 import 必须 sys.path 兜底，否则 hermes/scripts 环境下失败
- 必须同时 patch 所有使用 _nna 的资产函数
- 历史文件（_full.md）可能有泄漏，忽略，只看主卡片
- 连续轮次时，上轮 commit 后本轮从干净状态开始

## 下一步可扩展
- 把 _macro 注入到监控短卡正文（品种后追加 DXY 状态）
- 股票真实 earnings calendar 接入（finance MCP）
- 外汇其他宏观（利差）补充

此模式是“数据桥 → 渲染自动富集 → 卡片真实输出” 的标准闭环。
