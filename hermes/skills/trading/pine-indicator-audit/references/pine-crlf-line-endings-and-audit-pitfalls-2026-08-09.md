# Pine 行尾（CRLF→CE10156）与外部审计报告核验 —— 2026-08-09 实战记录

## 1. CRLF 行尾导致 CE10156：完整证据链

**症状**：TV 编译报 `Syntax error at input "end of line without line continuation"(CE10156)`，用户误以为修复引入的语法错误。

**根因**：Windows 上传的 .pine 文件带 CRLF 行尾。Pine 编译器把行尾 `\r` 当残留字符，所有跨行三元表达式（行尾是 `?`/`:` 的续行）在 CRLF 下报 CE10156。**报错与代码逻辑无关，纯换行符问题。**

**证据（2026-08-09 实测）**：
- 用户上传原文件主指标：`CRLF=3007, LF=57`（混用）→ 原版在 TV 上本身就编译不过
- 副指标原文件：纯 LF → 无此问题
- Hermes `patch` 工具改写文件时会把文件按 CRLF 重写（diff 可见未改行也 \n→\r\n）→ patch 后必须重新转 LF
- 修复后（纯 LF）桌面文件编译正常

**修复命令**：
```bash
sed -i 's/\r$//' <file>.pine        # 转 LF
# 验证：三种方式任选
python -c "d=open(f,'rb').read(); print('CRLF:',d.count(b'\r\n'),'LF:',d.count(b'\n')-d.count(b'\r\n'),'bare_r:',b'\r' in d)"
# 或用仓库内 scripts/check_line_endings.py
```

**铁律**：每次 patch 后、交付前必须跑行尾检查。交付到用户桌面后，TV 操作必须提醒「Pine 编辑器全选删除→重新粘贴/拖入→旧指标实例移除重加」，否则用户测的还是旧实例。

## 2. 外部审计报告核验：官方限制口径（纠错）

第三方报告 P0-1 称「免费档 plot 上限 40，两脚本会 Too many plots」——**误报**。

官方真实口径（联网核验 TradingView 官方 Visuals/Plots + 免费档限制文档）：
- **plot 上限 64，所有档位通用**（series color 计 2，const color 计 1）
- 免费档真实硬限制：5000 历史 bar / 2 指标/图 / 0 技术告警（只能用 alert() 事件化）/ 3 价格告警 / 20s 计算限制 / 100K intrabars / 40 request.security / 64 plot
- 官方确认：`input.color` 属于 series color → 计 2 plot（StackOverflow 佐证）

**核验方法**：外部报告的每条发现必须落代码行号验证，区分「属实 / 误报 / 部分属实 / 无法静态验证（需编译回执）」。宁可多花一轮 grep，不直接采信或直接推翻。

## 3. 本会话实证的 Pine 通用陷阱（均已修复并验证）

### 3.1 input.source 未接线假数据
```pinescript
float oiSource = input.source(close, "OI来源(AggVol)")  // 未接线时 = close
```
close 恒 > 0 → 显示「▲ 新多 65000.00% ✓一致」完全误导。
**修法**：接线检测 `bool wired = sourcetostring(src) != "close"`；未接线显示「OI 未接副指标」，接线但 na（非加密品种）显示「非加密无OI」。同时把 wired 检测用于 `input.source` 的其他消费端（状态码 1/2/3/4 判断 close 恰好相等的概率≈0，但严谨起见同样加门控）。

### 3.2 模糊 contains 拦截精确匹配（死分支）
```pinescript
// 错误：invalidText=="跌回扫低" 同时含"扫"+"低"，被 contains 分支先拦截 → 死代码，双向扫当根失效价=na
float v = str.contains(t, "扫") and str.contains(t, "低") ? ictEventPrice : t == "跌回扫低" ? curVal : na
// 正确：精确特判前移
float v = t == "跌回扫低" ? curVal : str.contains(t, "扫") and str.contains(t, "低") ? ictEventPrice : na
```
影响链：失效价 na → priceGeometryOk=false → A/B 计划当根无法执行。

### 3.3 var 固化 table 位置（改输入不生效）
```pinescript
var string pos = POS_INPUT == "右上" ? position.top_right : ...  // 首根固化
var table t = table.new(pos, ...)                                 // 位置无 setter
```
**修法**：`string pos = ...`（去 var，每根重算字符串）+ `var table t = na` + `if barstate.isfirst or pos != posPrev` 时 `t := table.new(pos, ...)` 重建。

### 3.4 timenow 回放失效
`time >= timenow - windowMs` 在回放模式下 timenow 是真实时间 → 历史回放点连线全消失。修法：`barstate.isreplay ? true : ...`。

### 3.5 Coinbase -PERP 后缀
`str.replace(ticker, ".P", "")` 不覆盖 `BTC-PERP` 风格 → spotTicker 仍指向永续 → 基差恒 0。修法：双替换 `str.replace(str.replace(t, ".P", ""), "-PERP", "")`（无效 symbol 由 ignore_invalid_symbol 兜底 na）。

## 4. 交付位置（用户偏好）
修复后的 .pine 交付到 `桌面/hermes下载文件/<任务名>_YYYYMMDD/` 单独文件夹；文件名带修改日期（如 `SVP_ICT_v2_20260809_fix.pine`）；旧日期版本保留。
