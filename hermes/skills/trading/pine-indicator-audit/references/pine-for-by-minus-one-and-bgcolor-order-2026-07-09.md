# Pine: by -1 运行时崩溃 + bgcolor 合并声明顺序（2026-07-09）

续 `pine-plot-limit-71-fix-2026-07-09.md` / `svp-v6-plot-limit-and-audit-2026-07-09.md` 之后用户 TV 报错。

## 1) Undeclared inMacroAm / inSilverBullet

报错：
```
Undeclared identifier "inMacroAm"
Undeclared identifier "inSilverBullet"
```

根因：为省 64 绘图槽把 3 条 bgcolor 合成 1 条时，过宽替换删掉了中间的 bool 定义，只留 bgcolor 调用。

正确顺序：
1. ictSessionBg
2. show_macro_bg / show_sb_bg / inMacroAm / inSilverBullet
3. 唯一 bgcolor(inMacroAm ? ... : inSilverBullet ? ... : ictSessionBg)

grep：`bool inMacroAm` 行号必须 < `bgcolor(inMacroAm`。

## 2) for ... by -1 step must be > 0

报错：
```
Error on bar N: 'step' in loop must be greater than zero
for oi = array.size(obList) - 1 to 0 by -1
```

size==1 → `0 to 0 by -1` 非法。`if size > 0` 挡不住。

修法：
```pine
int oiBrk = array.size(obList) - 1
while oiBrk >= 0
    // ...
    oiBrk -= 1
```

审计：`grep -n "by -1"` 生产循环应为空。v6 文档写 by -1 合法 ≠ size=1 安全。

## 关联

- 生产文件：Desktop + upload `SVP_v6.pine` 双写
- 绘图 71→64 主案：`pine-plot-limit-71-fix-2026-07-09.md`
