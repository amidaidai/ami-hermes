# Pine 区域文字必须真正内嵌 box：复现、修法与验收

## 适用范围

TradingView Pine v6 中 FVG、OB、Breaker、Liquidity Void 等矩形区域，需要把 `FVG A HTF`、`OB C` 等文字稳定放在对应框内右下角。

## 失败模式

### 独立 label 的坐标在框内，但文字仍越界

即使 `label.new()` 的 x/y 锚点位于 box 边界内，文字仍按像素宽度围绕锚点展开。短文本可能看似正常，`FVG A HTF`、`OB C HTF` 等较长文本会部分越出框。

单纯调整以下项目不能提供强保证：

- 从框右边界减去 1～3 根K线；
- `label.style_none`；
- `text.align_right`；
- ATR 上抬并限制为区域高度比例。

另一个常见回归是：创建标签时设为 `style_none`，维护循环又执行 `label.set_style(..., label.style_label_left)`，下一根K线再次把文字推到框外。

## 正确实现

不要为区域文字创建独立 label。把文字直接写入 box：

```pine
f_set_zone_box_text(box bx, string txt, color txtCol, string txtSize) =>
    if not na(bx)
        box.set_text(bx, txt)
        box.set_text_color(bx, txtCol)
        box.set_text_size(bx, txtSize)
        box.set_text_halign(bx, text.align_right)
        box.set_text_valign(bx, text.align_bottom)
```

创建和每根维护统一调用：

```pine
f_set_zone_box_text(zoneBox, zoneText, zoneColor, ZONE_LABEL_SIZE)
```

UDT 若历史上保留 `label lb` 字段，可暂传 `na`，后续再安全迁移字段，避免一次改动所有构造器造成参数错位。

## Pine 主体长度陷阱

把 `box.set_text*()` 五行在 FVG 多空、OB 多空、BRK、LV 多空及维护循环中重复展开，可能触发：

```text
The main body of the script is too long. Use functions to reduce its size.
```

因此从一开始就封装 `f_set_zone_box_text()`，不要先重复展开再补救。函数既保证行为一致，也缩减 Pine 主执行体。

## HTF 后缀

HTF 只改变 box 内文字，不改变定位方式：

```pine
string txt = "FVG↑ " + grade + (htfConf ? " HTF" : "")
```

OB 同样可使用独立 HTF 检测链：

1. `SHOW_HTF_OB`；
2. `f_htf_ob()`；
3. `request.security()`；
4. `htfObList`；
5. 本级 OB 与同向 HTF OB 重叠确认；
6. `ob.htfConf`；
7. 质量分、面板和执行门控消费确认结果。

## 必须执行的验收

```bash
# 区域悬浮标签必须为 0
grep -nE 'label\.new\(.*(FVG|OB|BRK|LV)' 主指标.pine

# 旧坐标补丁必须为 0
grep -nE 'ZONE_LABEL_X_IN|ZONE_LABEL_X_RIGHT|ZONE_LABEL_Y_ATR' 主指标.pine

# box 内建文字函数必须存在并被多处调用
grep -n 'f_set_zone_box_text\|box.set_text_halign\|box.set_text_valign' 主指标.pine
```

然后必须做 TradingView 编译验证。静态扫描不会捕获“main body too long”。视觉验证时重点看最长文本 `FVG A HTF`、`OB C HTF`，不能只检查短标签。

## 用户工作流偏好

若用户明确说“只修改指标，视觉验证我来”：

- 仍要完成本地静态扫描和文件同步；
- 不替用户操作图表或宣称视觉已正常；
- 但必须处理用户截图里的编译错误，不能把静态扫描通过等同于 TradingView 编译通过；
- 交付时直说修改内容、文件和哈希，避免反复解释未验证的视觉结论。
