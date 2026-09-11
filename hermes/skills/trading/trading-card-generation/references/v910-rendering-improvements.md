# v9.10 渲染排版优化（2026-07-11）

## 背景

用户要求"优化一下我的排版，发到电报的排版和流程还有排版好看一些"。

## 四项改动

### 1. 结构位「用法」列去内部ID

**问题**：`_klines_to_levels()` 用 `f"{tf}{typ}"` 拼接名称（如 `5mVWAP`、`1hVWAP`、`D高点`），显示在关键位表的「用法」列很难看。

**修复**：
- `_level_kind()` 返回值从 `(label, icon)` 扩展为 `(label, icon, use)`，`use` 用中文语义：
  - VWAP → `VWAP均价锚`
  - VAH → `VAH上沿阻力`
  - VAL → `VAL下沿支撑`
  - POC → `POC密集区`
  - nPOC → `nPOC裸区`
  - FVG → `FVG缺口`
  - 阻/支 → `阻力位`/`支撑位`
- `_klines_to_levels()` 名称改为 `f"{tf} {typ}"`（加空格）
- `_prepare_levels()` 存储 `use` 字段
- 关键位表渲染用 `item.get("use")` 优先

### 2. 订单流压缩

**问题**：`_multi_source_line()` 输出过长（~80字），包含 `cvd_quality`、`taker_ratio`、`haldro_confirm`、`kill_zone` 等冗余字段。

**修复**：去掉四个冗余字段，只保留：
- `CVD{方向}`（如 `CVD🔴卖`）
- `主动{方向}`（如 `主动卖`）
- `费{rate}`（如 `费0.01%`）
- `恐贪{value}`（如 `恐贪35`）

行宽从 ~80 字压到 ~40 字。

### 3. HALDRO 精简

**问题**：`_dual_short()` 中 HALDRO 截断 34 字，常显示 `偏空 4/4共振 配合主指标 A空 = 可做` 等冗余后缀。

**修复**：`hal` 截断从 34 字缩到 24 字。

### 4. 快速卡加裁决收尾

**问题**：`_render_push()` 末尾只有订单流行，没有裁决总结。

**修复**：
- 双指标 SVP+HALDRO 合并为一行：`SVP {svp} · HALDRO {hal} · {verdict}`
- 末尾加 `【裁决】{方向} · 主副指标已纳入 · 不追单`

## 影响文件

| 文件 | 改动 |
|:---|:---|
| `scripts/render_v96.py` | `_level_kind` 返回三元组、`_multi_source_line` 压缩、`_dual_short` HALDRO 截断、关键位表用 `use` 字段 |
| `scripts/render_tv_card.py` | `_render_push` 双指标合并一行 + 裁决收尾 |
| `references/master-template-v68.md` | 版本升级 v9.10、快速卡模板加裁决行、渲染器映射更新 |

## 实测

```bash
cd "D:/Hermes agent" && python -c "
from render_v96 import render_v96_card
# ... 完整卡输出正常，结构位用法干净
"
cd "D:/Hermes agent" && python -c "
from render_tv_card import render_tv_card
# ... 快速卡输出正常，有裁决收尾
"
```

语法检查：`render_v96.py` ✅ `render_tv_card.py` ✅
