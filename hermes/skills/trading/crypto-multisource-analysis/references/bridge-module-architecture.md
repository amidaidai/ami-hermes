# 桥接模块架构（Bridge Module Pattern）

> 2026-06-30 R1+R2 两轮修复后定型。用于将孤立引擎/数据源接入 `auto_card.py` 分析管线。

## 模式定义

**桥接模块** = 位于 `scripts/` 下的轻量包装层，满足以下条件：

1. **不修改原有脚本** — 原有引擎/采集器保持原样
2. **单一公开接口** — `{domain}_card_line(symbol) -> str` 或 `{domain}_summary() -> dict`
3. **try/except 包裹全部实现** — 不因桥接失败中断分析管线
4. **数据源标签** — 每个返回字段标注 `_source` 标记出处

## 已有桥接模块

| 桥接模块 | 包裹的引擎 | 管线集成点 | 行数 |
|---------|-----------|-----------|:--:|
| `orphan_integration.py` | meta_labeler/orderflow_absorption/cvd_analyzer/fvg_detector/order_block/correlation_matrix | auto_card ⑦段 | 632 |
| `jin10_gold_bridge.py` | Jin10 MCP (list_calendar/search_flash/get_quote) | auto_card Step 2（gold） | 430 |
| `cot_bridge.py` | cot_collector.py (subprocess解析输出) | auto_card Step 2（gold） | 170 |
| `forex_rate.py` | web_search 央行利率 + 30分钟文件缓存 | auto_card Step 5（forex） | 310 |
| `options_chain.py` | deribit_options.py（BTC/ETH）+ yfinance（美股） | auto_card Step 5（crypto/stock） | 170 |
| `stock_quote.py` | Stock-API MCP（A股）+ yfinance（美股） | 独立CLI脚本 | 170 |

## 集成模式

### 模式A：注入 `auto_card()` 函数流（推荐）

```python
# 在 auto_card() 的 Step 2 (引擎运算) 或 Step 5 (社区情绪) 后添加
# ═══ {领域}桥接（仅{资产类别}）═══
try:
    if '{条件判断}':
        from {桥接模块} import {card_line_func}
        line = {card_line_func}(symbol)
        if line:
            print(f"  ✅ {line}")
            engine_data['{key}'] = line
except Exception as e:
    print(f"  ⚠️ {领域}桥接: {e}")
```

### 模式B：注入 `render_card_locked()` 函数（分析卡正文）

```python
# 在 render_card_locked() 的 {段} 中添加
try:
    from {桥接模块} import {summary_func}
    data = {summary_func}({参数})
    if data:
        out['{key}'] = data
        lines.append(f"- **{标签}：{data.get('verdict','?')}**")
except Exception as e:
    lines.append(f"- {标签}：跳过({str(e)[:40]})")
```

## 验收标准

| 检查项 | 标准 |
|--------|------|
| 语法检查 | `python -m py_compile scripts/{module}.py` 通过 |
| 导入检查 | `python -c "from {module} import {func}; print({func}('BTC'))"` 有输出 |
| 集成检查 | `python -c "from auto_card import auto_card; auto_card('{symbol}')"` 不崩溃 |
| 容错检查 | 取消数据源后桥接模块返回空/标注降级，不阻断分析 |

## 常见陷阱

- **不要用 `len()` 检查 TypedDict/Protections 类型** → 用 `isinstance` 或 `type().__name__`
- **文件缓存时效** → forex_rate 设定 30 分钟（`_CACHE_TTL=1800`），缓存文件写入 `scripts/.cache/`
- **子进程输出解析** → `cot_bridge.py` 通过 `subprocess.run([sys.executable, 'scripts/cot_collector.py', '--line'])` 调用，需 `cwd=str(ROOT)`
- **Jin10 MCP 参数名** → `search_flash` 用 `keyword`（单数），非 `keywords`（复数）
