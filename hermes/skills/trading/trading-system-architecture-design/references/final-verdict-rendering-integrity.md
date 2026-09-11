# FinalVerdict渲染完整性

## 目的

避免旧TV行动格字段、缓存副指标文字或候选价格在最终闸门后重新获得执行含义。

## 不变量

1. `FinalVerdict`是卡片、告警、仓位与执行的唯一权威。
2. `GO-A`之外，`entry/stop/target`必须为`None`；候选观察位只能用`candidate_entry`或`watch_entry`表达。
3. 若`hard_conflict=true`或FinalVerdict原因包含`dual_indicator`，任何“主副同向”旧文本必须覆盖为“主副强冲突”。
4. 行动格含`⚠冲突/未收线/等收线/等解除/C等待/观望`时，迁移兼容层强制`WAIT`；新版本应输出结构化`conflict_code`、`bar_confirmed`和`execution_valid_code`，避免文本解析。

## 必测回归

- 原始`A多/A空`+FinalVerdict `NO-GO`：无星号执行单、无执行三件套。
- 原始“主副同向”+`hard_conflict=true`：卡片仅显示“主副强冲突”。
- 原始A等级+“未收线/等解除”：最终为`WAIT`，无执行三件套。
- B/C反：可显示带“候选/人工判断”标签的观察价，但不可出现“损/标”。

## 验证方法

先写失败回归测试，再修改决策/渲染代码；最后运行针对性测试、全量测试与一次真实卡片实跑，核对卡片没有泄漏旧执行字段。