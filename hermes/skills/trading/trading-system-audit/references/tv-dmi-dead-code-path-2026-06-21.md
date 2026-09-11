# TV DMI 死代码路径 — 2026-06-21 实案

## 症状

v6.9.14 声称 TV DMI 已全量接入，但分析卡从不显示 TV 等级。`grep "TV:" auto_card_*.md` 返回空。

## 根因：三个独立 bug 叠加

### Bug 1：auto_card 从未读取 TV 数据

`engine_data["_tv_pine"]` 始终为 `{}` — 没有任何代码注入它。

```python
# auto_card.py:1987 — 只读不放
tv_raw = engine_data.get("_tv_pine")  # → 始终 None
```

搜索全库 `grep -rn "_tv_pine" --include="*.py" .` — 只有读方，无写方。

### Bug 2：_parse_tv_dmi_table 嵌套级错误

MCP 返回格式: `[{name: "SVP...",  tables: [{rows: [...]}]}]` — 需拆两层。
函数期望: `tables[0].get("rows")` — 只拆一层。永远返回 `{}`。

```python
# 错误: 直接在 studies 第一层找 rows
for row_text in (tv_tables[0].get("rows", []) if tv_tables else []):
# tv_tables[0] = {"name": "...", "tables": [...]}
# 没有 "rows" 键 → 返回 [] → 空字典
```

修正: `tv_tables[0].get("tables")[0].get("rows")`

### Bug 3：局部变量 status 未同步

`render_card_locked()` 在 TV 覆盖前捕获 `status = meta.get("status")`。
`_apply_tv_dmi_override()` 修改 `meta["status"]`，但局部变量不更新 — 卡片仍显示旧值。

```python
# render_card_locked:299 — 捕获 status
status = meta.get("status", "B等待")  # → "B等待"

# render_card_locked:371 — TV 覆盖 meta
tv_override = _apply_tv_dmi_override(meta, ...)
meta["status"] = "C等待"  # ← 改了 meta, 但 status 变量不变

# render_card_locked:406 — 用旧值渲染
f"④ 状态：{status}"  # → "B等待" (错误!)
```

修正: 覆盖后 `status = meta.get("status", status)`。

### 缓存格式漂移（并发写入方破坏性覆盖）

三个进程写同一文件，三种互不兼容格式：

| 写入方 | 格式 | grade 键 | treatment 键 |
|--------|------|---------|-------------|
| tv_signal_monitor.py | `{"grade": "X", "treatment": "结构冲突", ...}` | `grade` | `treatment` |
| cron agent (第1代) | `{"tv_data": {"grade": "C等待", "action": "观望", ...}}` | `tv_data.grade` | `tv_data.action` |
| cron agent (第2代) | `{"grade": "C等待", "action": "观望", "bias": "空 4h", ...}` | `grade` | `action` |
| cron agent (第3代) | `{"grade": "C等待", "table_raw": ["等级 \| C等待", ...], ...}` | `grade` | 无 — 在 `table_raw` 行内 |

修正: 读端统一回退逻辑，键名优先级 `action > treatment`, `cvd > cvd_state`, `background > bias`。`table_raw` 最高优先级（原样 Pine 表行）。

## 诊断命令

```bash
# 检测 Bug 1: _tv_pine 无写入方
grep -rn "_tv_pine" --include="*.py" hermes/scripts/ | grep -v "get\|\.get"

# 检测 Bug 2: 解析函数
python -c "
from hermes.scripts.auto_card import _parse_tv_dmi_table
# 用 MCP 真实格式测试
tables = [{'name': 'SVP', 'tables': [{'rows': ['等级 | C等待', '处理 | 观望']}]}]
print(_parse_tv_dmi_table(tables))  # Bug2 返回 {} → 修复后返回 {'等级': 'C等待', ...}
"

# 检测 Bug 3: status 变量
grep -B5 "f\"④ 状态" hermes/scripts/auto_card.py | grep "status ="
# 若 status 在 TV 覆盖前赋值且覆盖后未更新 → Bug3

# 检测 TV 是否显示
grep "TV:" data/auto_card_BTCUSDT.md data/auto_card_BTCUSDT_full.md
# 应有 "TV:C等待" 或 "🔥TV:A多"
```

## 检测缓存格式问题

```bash
python -c "
import json
cache = json.loads(open('data/tv_dmi_cache.json').read())
print('Keys:', list(cache.keys()))
print('Has tv_data:', 'tv_data' in cache)
print('Has table_raw:', 'table_raw' in cache)
print('Has action:', 'action' in cache)
print('Has treatment:', 'treatment' in cache)
"
# 根据键名判断格式版本 → 确认读端是否兼容
```
