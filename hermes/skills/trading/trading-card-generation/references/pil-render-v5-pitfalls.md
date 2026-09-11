# PIL 渲染器 v5 实战坑（2026-08-31）

`scripts/render_analysis_card.py` 升级到 v5（深色终端式 + 多结构扩列）时踩到的具体坑，未来修改时对照。

## 坑 1：PIL `Image.LANCZOS` 不可用

`Image` 模块里没有 `LANCZOS` / `BICUBIC` 常量属性（Pyright 也报红）。要用整数：

```python
im = im.resize((new_w, new_h), 3)  # BICUBIC=3, LANCZOS=1, BILINEAR=2, NEAREST=0
```

更稳的写法是 `from PIL.Image import BICUBIC, LANCZOS` 后用 `PILImage.BICUBIC`。

## 坑 2：`draw` 不能 paste

`ImageDraw.Draw(img)` 返回的 `draw` 对象没有 `.paste()` 方法。要 paste 必须用底层 `img.paste()` 或 `draw._image.paste()`：

```python
img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)
# ...
img.paste(thumb, (x, y))   # ✅ 用 img
# draw.paste(thumb, (x, y))  # ❌ AttributeError
```

## 坑 3：表格 `_draw_table` 必须支持多元组混用

不同时段的表用不同列数，但同一个 `_draw_table` 会被反复调用。必须用 `isinstance(cell, tuple) and len(cell)==N` 分支处理 2/3/4 元组：

```python
# 错
for i, (val, level) in enumerate(row):  # 收到 4 元组就崩
    ...

# 对
for i, cell in enumerate(row):
    if isinstance(cell, tuple):
        if len(cell) == 4:
            lbl, val, level, _ = cell
        elif len(cell) == 3:
            lbl, val, level = cell
        elif len(cell) == 2:
            val, level = cell
            lbl = ''
    else:
        lbl, val, level = '', str(cell), 'white'
```

## 坑 4：col_w 不能塞 None

```python
# 错
y = _draw_table(draw, y, [...], rows, col_w=[180, 200, None])  # None 加到 x 会 TypeError

# 对
y = _draw_table(draw, y, [...], rows)  # 让函数内部按 inner_w // n 均分
```

或者在函数里把 None 替换为 `inner_w - sum(cw[:-1])`。

## 坑 5：fill 颜色太接近背景看不出"填充"

参考图风格常用 #1F0707 红色"深红填充"——但底色 #0E0E12 几乎黑，#1F0707 视觉上跟黑底没区别。要"明显填充"必须用：

- 红色深填充：`#3A0808`（深红但能看见）
- 绿色深填充：`#062812`（深绿能看见）
- 蓝色深填充：`#0B1F3A`（深蓝能看见）

调试方法：`PIL.ImageDraw.Draw.rectangle()` 后 `img.crop()` 一小块用 vision_analyze 确认颜色。

## 坑 6：每行单独 column 渲染 vs 统一 _draw_table

v4 用 2-tuple 行，v5 混用 2/3/4 tuple。改造时**别写两套函数**（`_draw_table_v4` + `_draw_table_v5`），统一升级到支持多元组的一版。否则 KPI/矩阵/monitor 三种表会三套代码，bug 翻倍。

## 验证清单

升级 PIL 渲染器后跑这个：

```python
# 数据：1) 2-tuple 行  2) 3-tuple 行  3) 4-tuple 行
# 必须三种都能渲染不崩
from render_analysis_card import render_card
import sys
out, size = render_card(
    out_path="outputs/test_v5.png",
    title="TEST",
    badge_text="A", badge_level="good",
    kpis=[("L1", "V1", "good")],
    multi_tf=[("15m", "结论", "78K", "warn")],   # 4-tuple
    tv_thumb={"image": "test.png", "headers": ["A","B","C"],
              "rows": [[("位置","VA上","mid")]]},   # 3-tuple
    binance=[("价","78541","warn")],   # 3-tuple
    monitor=[("79K","止损","不破", "bad")],   # 4-tuple
    ab_plan={"a":{"title":"A","lines":[("入场","78K","good")]}, "b":{...}},
    risk_text="⚠", callout=("📋", [("等","white")]),
    footer="OK"
)
print("size:", size)
```

任意一行崩就回头修函数，不是改数据。
