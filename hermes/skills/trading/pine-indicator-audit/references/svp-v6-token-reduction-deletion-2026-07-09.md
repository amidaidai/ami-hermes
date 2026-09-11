# SVP_v6_ready Token 削减执行实录 (2026-07-09)

## 背景
编译通过后 Token 79,957/80,000 余量仅 49。用户要求删除必删+建议删项。
最终削减 ~1,905 tokens → 78,017/80,000 余量 1,983。

## 删除清单 (7项)

| # | 项目 | 释放Token | 类型 | 删后处理 |
|---|------|----------|------|---------|
| 1 | 5个死函数 | 352 | 零依赖直接删 | grep确认无残留 |
| 2 | 银弹窗Silver Bullet | 327 | 5 input+2逻辑+bgcolor | 删inSilverBullet后bgcolor三元减一分支 |
| 3 | Band2(±2σ) | 315 | 3 input+2计算+2 plot | 删sVwapUpper2/sVwapLower2 |
| 4 | EMA单线input(4组×4=16个) | 630 | 16 input删+EMA周期硬编码 | EMA_1_LEN→9, EMA_2_LEN→21等 |
| 5 | 精简/标准模式 | 87 | 1 input+1变量+1 if条件 | 删if行后body缩进需修 |
| 6 | 降级提示 | 92 | 1 input+2变量 | showDegradeWarn→degrade直接替代 |
| 7 | 性能模式 | 100 | 1 input+1变量+6引用 | proLightMode→false, not proLightMode→true |

## 三大执行陷阱

### 陷阱1: 残留引用
删 input 后代码中仍引用已删变量名。
- `EMA_1_LEN` → 硬编码 `9` (同理 21/34/55)
- `proLightMode` → `false`
- `showDegradeWarn` → `degrade` (底层变量直接替代)
- `showSpanWarn` → `spanTooLongForDrawing`

检测: 删后 grep 所有被删变量名，逐一替换残留。

### 陷阱2: 缩进错位
删 `if panelDetailStd` 行后，body 保留了多一层缩进(12空格 vs 同层4空格)。
Pine 报 `Mismatched input "string" expecting "end of line without line continuation"`。
修法: 逐行减4空格缩进，或用 patch 工具精确修。

### 陷阱3: 多行 replace 匹配失败
Pine 字符串含 `\\n` 转义，Python `code.replace()` 中 `\\\\n` 与文件实际 `\\n` 不匹配。
修法: 改用 `lines[i] = 'new'` 逐行修改再 join。

## plot 条件修改
删 EMA 单线 input 后 plot 条件从 `(SHOW_EMA_1 or SHOW_EMA_12_CLOUD)` 改为 `SHOW_EMA_12_CLOUD`。
云填充仍工作，只是无法独立显隐4条线条。

## 删后保留的功能
SVP+VWAP+CVD+ICT+FVG+OB+LV+BOS/CHoCH+HTF确认(FVG+OB)+SMT+ADR+KillZone+宏观窗
+行动格+MCP 12plot+EMA云(9/21+34/55)+轴标+EMA_FILTER开关

## 删后验证
- request.security: 12/40 ✅
- plot(): 20/64 ✅ (删Band2减2, EMA不变因为云仍plot)
- alertcondition: 16/16 ✅
- MCP Data Window: 12 ✅
- OBZone.new: 6处全9参 ✅
- 关键串全在: @version=6 / dynamic_requests / f_htf_ob / f_htf_fvg / MCP Risk Pack ✅