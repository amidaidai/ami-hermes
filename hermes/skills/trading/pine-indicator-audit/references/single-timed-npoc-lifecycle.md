# 单一限时 nPOC 生命周期与图面契约

适用于棠溪 SVP 主指标中历史 POC 的最终生产语义。

## 最终产品规则

- 物理删除 `pPOC`：输入、颜色、对象、数值、轴标和所有消费端均不得残留。
- nPOC 固定只保留最近 **1** 个，使用常量 `NPOC_LIMIT = 1`，不要保留可调数量输入。
- 活跃 nPOC 显示为短虚线，不是从形成点无限延伸的长射线；当前基线为滚动 **8 根K**：
  - `NPOC_VISIBLE_BARS = 8`
  - `x1 = max(createdBar, bar_index - NPOC_VISIBLE_BARS)`
  - `x2 = bar_index + 1`
  - 创建和维护都使用 `line.style_dashed`
- nPOC具有独立K线时效，超过 `NPOC_EXPIRE_BARS`后删除对象并移出数组。

## 触碰生命周期

触碰检测应同时覆盖K线高低范围穿越和跳空越过。确认时机沿用ICT的 `SWEEP_MARK_MODE`。

触碰后必须：

1. 设置 `swept=true` 与 `sweptBar=bar_index`；
2. 将线终点固定在触碰柱附近；后续K线不得继续调用 `line.set_x2()`；
3. 低周期保留淡色虚线；
4. H1+在 `HIDE_SWEEPS_ON_HTF`开启时删除线并标记hidden；
5. 立即退出支撑/阻力、Magnet、关键位、事件候选和价格轴候选。

## 常见错误

- **只把默认数量改成1**：用户要求固定1个，应删除数量输入，使用常量，避免设置面板还能改回多个。
- **虚线但仍是长射线**：`line.style_dashed`只改变笔画，不改变整条线的几何长度；必须滚动更新x1形成短线段。
- **触碰后继续延伸**：在`swept`分支每根K继续`set_x2(bar_index+1)`会违背ICT扫线语义；触碰后冻结端点。
- **只改图形不改消费端**：已扫、已过期或隐藏nPOC不得继续进入方向位、磁吸、关键位、事件和轴标。
- **把nPOC误写成前一期POC**：nPOC的身份是形成后尚未测试；它不等于pPOC。当前生产版明确不要pPOC。

## 最小回归断言

- 源码不存在 `pPOC|prevProfilePoc|prevPocLine|SHOW_PREV_POC`；
- 存在 `const int NPOC_LIMIT = 1`；
- 存在短线宽常量与`line.set_x1`滚动窗口；
- 创建和活跃维护均为`line.style_dashed`；
- swept后不存在持续`line.set_x2(np.ln, bar_index + 1)`路径；
- 过期路径同时执行`line.delete`和`array.remove`；
- 静态扫描、契约测试、上传源cmp/SHA均通过；TradingView服务器编译需单独报告。
