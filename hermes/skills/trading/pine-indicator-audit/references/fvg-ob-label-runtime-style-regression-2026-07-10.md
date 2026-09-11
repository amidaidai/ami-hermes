# FVG/OB 标签运行时样式覆盖回归（2026-07-10）

## 症状

创建时标签坐标已经位于 box 边界内，`label.new()` 也使用 `style_none + text.align_right`，但用户实测标签仍持续显示在框外。

## 根因

维护循环每根K线再次执行：

```pine
label.set_style(f.lb, label.style_label_left)
label.set_style(ob.lb, label.style_label_left)
```

`style_label_left` 会让标签主体从锚点向右展开，因此“锚点在框内”不代表“文字在框内”。创建阶段的正确样式被运行时 setter 覆盖。

## 正确修复

FVG 与 OB/Breaker 的维护路径统一为：

```pine
label.set_style(zone.lb, label.style_none)
label.set_textalign(zone.lb, text.align_right)
```

坐标仍使用 box 右边界内缩，纵向使用 `min(ATR*lift, zoneHeight*0.25)`。

## 强制审计清单

修复区域标签时同时检查：

1. `label.new()` 的 style/textalign；
2. `label.set_x()` 与 `label.set_y()`；
3. 所有 `label.set_style()`；
4. 所有 `label.set_textalign()`；
5. FVG、OB、Breaker 三条维护路径；
6. 维护区不得残留 `style_label_left`。

只改创建行或 x/y 坐标不算完成。若不同缩放下独立 label 仍无法可靠约束，改用 box 内置 text（右对齐、底对齐）。

## 用户工作流边界

用户明确“只修改指标，验证我来”时，完成源码修改、静态扫描、文件同步和哈希核验即可，不操作 TradingView 图表实例。
