# 20260814 双指标联网审计：request 条件执行语义 + 计数口径修正

来源：20260814 会话，对上传版主指标（3406 行/198 input）与副指标（732 行/50 input）做联网审计
（pine_check 服务器端编译 + pine_static_scan + 联网官方文档/社区实测交叉验证）。

## 一、request 条件执行语义（本次最重要实证）

**TV 官方支持（2024-12，SO 79288126）**：request.security 等 request.* 的计算"在
主脚本执行前基于被请求图表/周期完成，独立于局部条件或逻辑块放置位置，请求无论如何
都被处理，包括其中任何 log 函数"。TV 员工（Starr Lucky）承认手册原文有误并承诺更新：
"even with dynamic security, the execution will occur on each bar or tick"。

**对审计的影响**：
1. 三元运算符内 request（如 `cond ? request.security(...) : x`）不因条件为假而跳过执行。
   条件只控制**结果消费**，底层数据拉取照跑。
2. if 块内 request 同样无条件执行（实测 profiler + log 均证明）。
3. **唯一可能真正省**：把 request 包进用户函数，且该函数在运行时未被调用
   （如 `isCryptoA ? f_lsr_a() : na` 中 isCryptoA=false）。函数未调用则函数体不执行。
   但注意：v6 dynamic_requests 默认开启后此行为是否 100% 成立未获官方文档背书，建议
   用 profiler 实测后写入注释，不要仅凭推断。

**本指标中踩雷的注释**：
- 副指标 L81-82：`// USD 默认路径无需汇率换算：短路为常量，跳过请求（省配额+提速）`
  实际：`FX_CONV_RATE = coinusd == 'USD' ? 1.0 : request.security(...)` 仍会执行
  request（请求 FX_CONV_TICKER=当前 ticker，几乎无成本，但"跳过请求"表述不实）。
- 主指标 L750-757：`// metalSpot 无逐笔数据且 CVD 权重归零，不再拉低周期，省 intrabar 预算`
  实际：`cvdLowerDeltas = cvdUseLowerTf ? request.security_lower_tf(...) : array.new_float()`
  三元内 request 仍执行，intrabar 拉取未省（仅结果未消费）。
- 副指标 L336-337 "包进函数后只在被调用时执行"：方向正确（函数化短路），但 L82 的三元
  短路是反例——函数化 ≠ 三元化，二者效果不同。

**正确做法**：注释改中性表述（"条件为假时不消费结果"）或用 profiler 实测后写实；
优化真正靠函数化+不调用，不靠三元。

## 二、CE10116 计数口径修正（pine_external_elements_scan.py 虚报）

**TV 脚本级六项和公式**（20260813 定稿）：全部 input（含 input.source/input.timeframe）
+ plot + alert + request = 上限 254。

**扫描脚本 bug**：pine_external_elements_scan.py 统计 input 时已把 source/tf 计入
（`=` + `input.` 正则匹配所有 input 类型），随后又在六项和中**单独再加**
source + tf → 重复计数虚报超限。本次报 257/254，人工复核实际 250/254：
- 口径A（全部 input 含 source/tf）：198 + 43 + 1 + 8 = 250
- 口径B（普通 input + source + tf 分开）：191 + 43 + 1 + 8 + 3 + 4 = 250

**审计结论**：以 pine_check 服务器端编译为准（0 错 0 警 = 通过），扫描脚本输出仅作
粗筛；若脚本报 >254 而编译通过，先按上述口径人工复核再下结论。

## 三、全量 pine_check 编译用法（新验证路径）

- 主指标完整 217KB 源码可直接作为 pine_check 的 source 参数传入编译（0 错 0 警）。
- 切勿手工重构/精简源码再编译——会引入声明顺序等伪错误（本次手工重建版报 12 个
  Undeclared identifier，原文件编译全过）。要验证就传原文件，别手抄。

## 四、TV MCP 掉线恢复流程

现象：tv_health_check / pine_check 连续报 "CDP connection failed after 5 attempts"，
hint 提示 "TradingView is not running with CDP enabled"。

恢复：调 tv_launch(kill_existing=false) 拉起桌面端（成功返回 pid/cdp_port）→ 重试
pine_check。MCP server 报 "unreachable after 3 consecutive failures, auto-retry ~47s"
时等约 1 分钟再试，勿连打。

## 五、本次审计结论（基线快照，供后续 diff）

- 副指标 AggVol：732 行 / 50 input / 29 静态 request（20 聚合+4 OI+1 LSR+1 现货+
  1 单源 OI+1 汇率+1 HTF）/ 41 plot / 1 alert() / 无未定义变量。编译 0 错 0 警。
- 主指标 SVP：3406 行 / 198 input + 44 const / 8 request（6 security + 2
  security_lower_tf）/ 43 plot + 2 fill + 1 bgcolor / 1 alert()。六项和 250/254，
  CE10116 不复发。编译 0 错 0 警。
- 遗留未落地（20260812 已提方案，本次确认仍未修）：
  1. f_sup_res 次级位（DO/前日/上周高低）不查 swept（prevWeekHighSwept 变量已存在
     L1328-1333 但 f_sup_res L1690-1704 未使用）
  2. 扫N/M 显示已扫计数（L3118），未改"活N/M"
- 本次新发现 P2/P3：
  1. P2-3 死代码 `int obLife = 200 > 0 ? 200 : 400`（L2436/L2454，恒 200，参数化残留）
  2. P3 OI Pack 编码一致%=100 时主指标 `%100` 解码得 0（副 L724 编码 dir*100+agree，
     主 L3060 解码 abs%100——agree=100 时 pack=200，%100=0）
  3. P3 oiWired 守卫 `abs(oiSource)<=100`：OI 变化>100% 时误判未接副指标
  4. P3 主 L301 adrDailyRaw 无条件执行（ADR_ENABLE=false 也拉日线）
  5. P3 主 L2121-2122 HTF FVG/OB 两 request 常开（开关全关时仍请求本周期）
  6. P3 副 L30 calctype 仅 SUM 一选项=死参数（已知）
  7. P3 主副各一份 f_is_metal_ticker/autoMetal 双实现，改一处忘另一处会分叉

## 六、Pine v6 官方 breaking changes 备忘（2026 验证）

- and/or 惰性求值（v5 两操作数都求值 → v6 短路）——ta.rsi 等有状态函数放 and 右侧
  可能不再每根 K 执行，须提到全局
- 整数除法恒返回小数（v6：5/2=2.5）——需截断处显式 int()
- 动态请求默认开启（v6），request.* 可进 if/switch/循环/函数；三元内亦合法但见第一节
- v6 不允许 `6[1]` 字面量历史引用、UDT 字段直接 [n]（须 (obj[n]).field）
- 布尔不能为 na，na()/nz() 不再接受 bool

## 关联参考

- 20260814 双指标社区审计新发现（P0 主指标 CVD 背离缺锚定检查 / P1 liqA 恒真弱过滤 /
  P2 ta.mfi 图表量口径分裂 / 表格增强清单 / 社区多源验证结论）→
  `references/pine-20260814-community-audit-findings.md`
