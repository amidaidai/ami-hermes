# 棠溪双指标全面修复计划

时间：2026年7月10日02：01

## 目标

以用户本轮上传的两份 Pine v6 源码为唯一输入基线，修复全面审计报告中所有可落地的 P0/P1/P2 缺陷；服务器编译、BTC/XAU 运行态、Data Window 和行动格全部回归后，再同步桌面与生产上传目录。

## 输入与输出

- 主输入：`C:/Users/Administrator/.hermes-web-ui/upload/default/eb05e066077677c2.txt`
- 副输入：`C:/Users/Administrator/.hermes-web-ui/upload/default/f0af01cfbb0debd6.txt`
- 证据目录：`D:/Hermes agent/outputs/pine-fix_20260710_020125/`
- 主修复输出：`C:/Users/Administrator/Desktop/主指标_全面修复版_2026年7月10日.txt`
- 副修复输出：`C:/Users/Administrator/Desktop/副指标_全面修复版_2026年7月10日.txt`

## 有序任务

### 1. 备份与建立唯一基线

- 原附件按 SHA256 归档为 `main.original.txt`、`sub.original.txt`。
- 修复仅在 `main.fixed.txt`、`sub.fixed.txt` 工作副本进行。
- 验证：原始 SHA 保持 `1cd1d916...` 与 `e8c056f7...`。

### 2. 主指标修复

- 修复 OB 选K：LTF/HTF 都使用最后一根反向蜡烛本身，不再偏移 `+1`。
- 修复 Breaker 生命周期：看涨OB向下破坏后翻为看跌Breaker；看跌OB向上破坏后翻为看涨Breaker，避免同根反复翻转。
- 修复 HTF OB：只使用已收 HTF 柱结果，消除 `lookahead_on` 前瞻。
- 重写确认分：按当前唯一计划方向消费 CVD、扫线、接受、FVG、HTF FVG、OB、Breaker；双边候选冲突进入等待。
- MCP 增加/修正可执行语义：X/等待时 Entry、Stop、Target 均不导出可执行价格；提供显式 Executable Code。
- 把 CVD 摆动幅度、质量、关键位、斜率真正接入背离与告警。
- “Funding Rate”改为“永续基差”。
- 修正独立池开关、session open 语义、截止时间 `timenow`。
- 多市场自动锚定统一为 `<1h=D、1h至<4h=W、≥4h=M`。
- 行动格改为 `已扫N/剩M`；区域标签改为“缺口/订单块/破坏块/真空”。
- 删除零调用函数、零消费输入与旧叙事残留；保留真实活跃依赖和 Data Window 兼容字段。

### 3. 副指标修复

- 修正 LSR 拥挤方向；缺值明确显示不可用；同向拥挤扣确认分并进入 Risk Code。
- OI 改为逐交易所百分比变化与上涨/下跌广度，停止跨单位原始绝对值相加；保留兼容字段但改成诚实口径。
- “爆仓”改为“疑似清算代理/杠杆成交量异常”，不再宣称真实强平。
- 把 14K Delta 改名为滚动 Delta；Cumulative Delta 使用锚定 `sessCvdA`。
- 提取 `ta.highest/lowest` 到每K执行变量，消除两条服务器警告。
- 覆盖率按数据流计算，分别呈现现货、永续和 OI 覆盖。
- 绿灯与强告警统一受最终 Confirm、Valid、Risk、CVD 同向性门控。
- `SHOW_ACT=false` 时清理旧表格。
- 修正 32/40 配额注释，删除死函数与零消费变量。

### 4. 静态与服务器验证

- 运行 `pine_static_scan.py`。
- 验证 Pine v6、动态请求唯一、未定义变量、UDT 构造参数、负步长循环、CW10002 风险行。
- 验证 request、plot、对象、alert 配额。
- 使用 TradingView 会话服务器编译两份文件，目标：两者均 0 error、0 warning。

### 5. TradingView 运行态验证

- 把修复版更新到图表后，验证 `BINANCE:BTCUSDT.P` 15m：行动格、Data Window、对象、主副放行规则。
- 验证 `OANDA:XAUUSD` 15m：主指标锚定与CVD通道；副指标 Valid=0 且表格/Data Window不产生可执行方向。
- 回到 BTC，切换 5m/15m/1h/4h/1D 检查锚定与显示。
- 截取全屏新图，必须包含价格轴和 CVD 窗格。

### 6. 同步与交付

- 仅在全部验证通过后，把 fixed 版本同步到桌面和 Web UI 上传目录。
- 计算 SHA256，要求证据目录、桌面、生产三处逐字节一致。
- 生成修复报告，逐条列出已修、验证证据、剩余固有限制（两套CVD仍为估算而非逐笔）。

## 边界与风险

- 不把估算 CVD 宣称为真实 bid/ask Delta。
- 不增加 `request.footprint()`，避免套餐依赖和配额变化。
- OI跨所单位不可靠时宁可输出方向广度，不制造虚假的绝对总量。
- 删除输入前必须证明零下游消费；删除 UDT 字段前必须核对全部 `.new()`。
- 每次修改后重新服务器编译，不能用静态扫描代替 TradingView 编译。
