# SVP v6 绘图配额 / 循环 step / FVG·OB 标签 / EMA 只云（2026-07-09）

## 会话结论（生产文件）

权威路径（改完必须三处同步 + 校验 sha 一致）：
- `C:/Users/Administrator/Desktop/SVP_v6.pine`
- `C:/Users/Administrator/Desktop/SVP_v6_ready.pine`（给用户粘贴的清晰副本）
- `C:/Users/Administrator/.hermes-web-ui/upload/default/SVP_v6.pine`

交付铁律：用户说「文件没有改到」时，默认视为上轮只口头描述未写盘。任何「已修好」必须先有 `write_file`/脚本写盘 → `sha1` 变化 → 关键串 grep 命中，再回复。

## P0：脚本创建了太多绘图(71)。限制为64

### 根因（与 71 对齐的估算）

TV 内部计数近似：

```
worst ≈ plot_count * 2 + fill_count * 2 + bgcolor_count * 2 + table_count
```

`input.color` / 三元色 / `color.new(hex, series_trans)` 都会让 plot 按 **2 槽**计。grep 只看到 30 个 `plot(` 仍可能报到 71。

### 修法优先级

1. **视觉 plot 改常量 hex**（最大收益）：S VWAP/带、右轴 POC/VAH/VAL/nPOC/W·M VWAP/DO 等 `color=#......`，不要 `color=POC_COLOR`。
2. **bgcolor 3→1**：会话底 + 宏观 + 银弹合并一条；**合并前必须先定义** `show_macro_bg/inMacroAm/inSilverBullet`，禁止只留引用删定义。
3. **MCP Data Window**：保留 auto_card 经典名（Side/Grade/Setup/Entry/Stop/Target/CVD/Quality + FVG CE×2）；OB/BOS/LV/FvgQ 可压成 `MCP StructPack`。
4. **EMA 只要云**：四条 EMA plot 用 `color=color.new(#hex, 100)` 全透明常量；`fill` 负责云。不要 `color=SHOW_EMA_1 ? opaque : transparent`（series 双倍）。

### 修后目标

- plot 色 series=0；est 乐观 ~30–40；最坏 <64。
- 用户 TV 仍报 71/旧行号 → 多半是编辑器未整份替换：要求搜 `by -1`/`oiBrk`/`FVG↑` 自检。

## P0：Error on bar N: 'step' in loop must be greater than zero

### 触发模式

1. `for i = array.size(arr) - 1 to 0 by -1` 在 size=1 时变成 `0 to 0 by -1`。
2. `for i = 1 to array.size(a) - 1` 在 size=1 时变成 `1 to 0`（默认 step+1 非法）。
3. `for r = 0 to pnlRowCount - 1` 在 count=0 时变成 `0 to -1`。

### 修法

- 倒序一律 `while i >= 0 ... i -= 1`，勿用 `by -1`。
- `maxIndex`：`sz<=0 → na`；`sz==1 → 0`；否则 `for i = 1 to sz-1`。
- 所有 `0 to size-1` 循环外包 `size > 0`。

Breaker 块标准写法见生产 SVP_v6（`oiBrk` while）。

## P1：FVG/OB 色易混 → 右侧标签

用户偏好：框最右边加标签，一眼区分 FVG 与 OB。

| 对象 | 标签 |
|------|------|
| FVG 多/空 | `FVG↑` / `FVG↓`（HTF 确认可 `·HTF`） |
| OB 多/空 | `OB↑` / `OB↓` |
| Breaker | `BRK↑` / `BRK↓` |
| 已缓解 OB | 后缀 `·已扫` |
| LV | `LV↑` / `LV↓` |

实现要点：
- `type FVG` / `type OBZone` 增加 `label lb`；构造参数 arity 从 7→8。
- 创建：`label.new(rightBar, mid, text, style=label.style_label_left, size=size.small)`。
- 维护：与 box 同 right 延伸；删除/shift/过期时 `label.delete`。
- HTF-only FVG 不画框也不建 label（`na`）。

## 交付自检清单（改完必跑）

```text
1. sha1(Desktop SVP_v6) == upload == ready
2. grep -c "by -1" 仅注释可有；运行时 for by -1 = 0
3. grep "FVG↑|OB↑|color.new(#00FF6A, 100)|oiBrk"
4. FVG.new / OBZone.new 参数个数全为 8
5. 回复用户前：禁止「已修好」而无写盘证据
```

## 相关

- `references/pine-token-limit-reduction-2026-07-09.md`（token 维度）
- tradingview-pine-indicators `references/data-window-output-compression.md` / `pine-plot-limit-quick-triage.md`
