# SVP_v6_ready.pine 修复会话 2026-07-09

## 修复清单

### P0: Token 超限 (81,088 > 80,000)
- 删66行独立注释 + 精简tooltip + 补回误删的 `//@version=6`
- 最终: 79,380/80,000, 余量620
- **陷阱**：`//@version=6` 以 `//` 开头被注释删除逻辑误删，必须排除保留

### P0: `:=` 赋值引用后声明变量 (Undeclared identifier)
- `cvdBearStars :=` 在 L1786 引用 `cvdAbsorbBuyQualified`（声明在 L1789）
- Pine 自上而下编译，`:=` 重新赋值同样受 def-before-use 约束
- 修法: 4个 `bool` 声明放前面, 2个 `:=` 赋值移到 L1789-1790

### P1a: BOS/CHoCH 文案优先级
- L2208: `bosBull ? "BOS↑" : ... : chochBull ? "CHoCH↑" : ...` → CHoCH 永不显示
- chochBull 是 bosBull 的超集（chochBull=true → bosBull 必=true）
- 改为 `chochBull ? "CHoCH↑" : chochBear ? "CHoCH↓" : bosBull ? "BOS↑" : bosBear ? "BOS↓" : ""`
- MCP 编码 L2800 原本就是 choch 优先（正确），只有文案错

### P1b: bcDirectRaw 补 OB/Breaker 汇合
- bcLongDirectRaw / bcShortDirectRaw 不含 OB/Breaker → 回踩OB不触发B/C挂单
- 追加 `or inBullOB or inBullBreaker` / `or inBearOB or inBearBreaker`

### P1c: 风控参数 MCP 编码
- RISK_PER_TRADE_PCT / DAILY_MAX_LOSS_PCT / WEEKLY_MAX_LOSS_PCT 原为死代码
- 新增 `MCP Risk Pack` plot: `Risk%*10000+DailyLoss%*100+WeeklyLoss%`
- MCP Data Window 11→12

### P2: CVD 星级算法
- cvdBearStars/cvdBullStars 原恒0，补星级计算:
  - 确认背离+吸收/派发=3星, 确认背离=2星, 未确认背离=1星, 无背离=0

### CW10002: ta.* 在条件表达式内（逐轮修复）
- 第一轮：`ta.sma(volume, 20)` 在 `or` 条件内 → 提取 `volSma20` 全局变量
- 第二轮：`ta.crossover(close, sVwap)` / `ta.crossunder(close, sVwap)` 在 `and` 条件内 → 提取 `xoverS` / `xunderS`
- 第三轮（待修）：`ta.lowest(close, ACCEPT_BARS)` / `ta.highest(close, ACCEPT_BARS)` 在 `and` 条件内
- 经验：CW10002 需逐个排查，每个新编译错误都要继续提取全局变量
- 注意：`request.security(..., ta.sma(high-low, N)[1], ...)` 中的 ta.sma 不算 CW10002

### FVG/OB/LV 标签框内定位（用户两轮反馈）
- 第一轮：用户反馈「标签都没有在那个框里面」→ 加 `textalign=text.align_right` + x 缩 `-1`
- 第二轮：用户反馈「箭头和边框重叠了，标签要左移一点点」→ x 从 `-1` 改为 `-3`
- 根因：`style=label.style_none` + 默认 `text.align_center` + x在框右边界 → 文字溢出
- 修法（6个 label.new + 3个 set_x）：x 缩 `-3`，`textalign=text.align_right`，textcolor 用区域色非 white
- 调参经验：`-1` 仍重叠 → `-2` 贴边 → `-3` 完全在框内
- 社区依据：TradingCode.net 确认 `label.style_none` 下 `textalign` 仍然有效

### BOS/CHoCH 告警精简
- 用户说「bos这些还需要不需要就删掉」
- 依赖链分析：BOS 是 OB 触发条件 + MCP 编码 + 面板确认行 → 逻辑骨架不能删
- 删除4个 BOS/CHoCH alertcondition（弹窗告警），保留逻辑
- alertcondition 从 20 降到 16

### OB HTF 确认缺失（用户反馈，待实现）
- 用户指出「ob的设置和fvg差不多，高周期可以确认低周期」
- 当前 OB 没有 HTF 确认，FVG 有完整 HTF 确认链
- 需对齐 FVG 的 HTF 确认模式：HTF BOS → 本级 OB htfConf → 标签 " HTF" + MCP 升级

## execute_code replace 重复匹配陷阱
- 同一脚本中 `code.replace(old, new)` 成功后，第二次用同一 `old` 字符串 replace 会报 ❌
- 因为已经被改过了，旧字符串不存在了
- 修法：多步替换后重新 read_file 拿最新内容再下一步，或一个脚本内一次性做完再验证

## 配额验证（最终）
- request.security: 9 (代码级, 原10中1个在注释行)
- request.security_lower_tf: 2
- dynamic_requests: 1
- plot(): 24 (原23 +1 Risk Pack)
- Data Window: 12
- alertcondition: 16 (原20-4 BOS/CHoCH)
- Token: 79,339/80,000

## 三路径同步 SHA: d9d82e1446816b6d
- ~/.hermes-web-ui/upload/default/SVP_v6_ready.pine
- ~/Desktop/SVP_v6.pine
- ~/Desktop/SVP_v6_ready.pine