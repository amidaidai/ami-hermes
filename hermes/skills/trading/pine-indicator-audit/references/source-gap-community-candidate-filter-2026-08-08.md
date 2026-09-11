# 源码差距＋社区实现候选筛选（2026-08-08）

适用：用户要求先读当前 Pine 源码，再与 2025–2026 TradingView 开源脚本、GitHub、SMC/Volume Profile 实现横向对标；只筛指标本体增强，明确不要回测/复盘。

## 一、正确工作流

1. **源码优先**：完整读取主、副指标，记录准确行号；先定位已有状态机、消费链、对象上限和性能热点，禁止拿社区功能表直接套用。
2. **分四类裁决**：
   - 真缺失：源码中没有对应状态、对象或消费链。
   - 部分实现：已有底层状态，只缺投影、路由或面板消费。
   - 重复：已有同语义功能，或社区新标签在当前架构中不会产生区分度。
   - 低价值：只增加图面/分数/估算副本，不改变方向、触发、失效、目标或质量闸门。
3. **每项必须给**：当前源码状态＋行号、决策价值、实现复杂度、增量 plot/request/object 成本、来源 URL/日期、推荐结论。
4. **成本默认目标**：主指标增强优先 `+0 plot / +0 request`；复用现有 VP/FVG/OB 数组、box/line 和打包 MCP 字段。若必须加对象，写明硬上限。
5. **先修原子合同再加区**：任何 iFVG/BPR/HVN/OB 新触发都必须让 winning zone 的名称、top/bot/CE、Entry、Stop、Target、score、HTF/id 原子绑定，不能“显示 OB 承接但 Entry 来自无关 POC/FVG”。

## 二、本轮源码基线与关键差距

主指标 `ce6a2557447ee392.pine`：3033 行、9 个静态 request 调用点、41 个 plot 调用；副指标 `ab8d7695be530f20.pine`：655 行，聚合 CVD/OI/量能确认完整，不应复制进主指标。

### 真缺失、高价值

- iFVG 极性翻转状态机：普通 FVG 有检测/质量/填补删除，但没有 close-through 后角色翻转。
- EQH/EQL：现有流动性仅会话、前日、前周，没有结构 pivot 聚类的 resting liquidity。
- HVN/LVN：VP 已有桶分布，但只输出 POC/VA；没有局部峰谷/prominence/相邻桶合并。
- BPR：已有多空 FVG 数组，但不计算反向 FVG 重叠区。
- 前日 VP VAH/VAL/POC 投影：已有前日 H/L、completed profile、nPOC；缺显式前日 VAH/VAL 和当前日投影。
- Developing POC/VA migration：现有 `valueMigrating` 只是价格远离 POC，不是 POC/价值区本身上移、下移或重叠。
- Adaptive ATR-confirmed major/minor pivots：当前 BOS/CHoCH/OB 使用固定对称 pivot。

### 部分实现，应增强而非重造

- First touch：nPOC 已有 touch/gap/sweep 状态；FVG/OB 已有 touchCount。只需把统一 `untouched → touched → reclaimed/accepted/consumed` 状态扩展到前日 VP、HVN/LVN、EQH/EQL，勿再造一套 nPOC first-touch。
- OB mitigation：已有 `mitigated` 和删除开关，但当前近端浅触即可消费。应增 proximal/50%/wick-through/close-through/full-fill 模式。
- Object lifecycle：各数组已有上限和 delete；真正增量是统一 Zone Registry、语义去重和对象复用，不是再加一个“最大数量”输入。
- HTF FVG/OB：expression 内已使用确认偏移，外层 `lookahead_off` 是额外发布延迟，不是未来泄漏；可改标准 `lookahead_on` 及时发布上一根确认 HTF 区。

## 三、关键重复/低价值裁决

1. **Mitigation Block 单独标签不进入候选**：2026 Quant SMC Pro 的定义是“BOS 后第一个 OB 标 MB”；当前源码本来只在 `breakBull/breakBear` 后创建一个 OB，因此几乎所有 OB 都会被重标 MB，没有新决策信息。保留“缓解规则增强”，不加 MB taxonomy。
2. **Breaker/FVG CE/HTF FVG/nPOC 首触不重复建议**：源码均已有。
3. **不再加 0–100 总分**：当前已有 FVG/OB quality、Magnet score、setupTotalScore、readiness；应统一为 blocker-first final decision，而非第五套分数。
4. **Liquidity Void 倾向并入 FVG/iFVG 或删除**：默认关闭，公式近似错位 FVG，只写 MCP StructPack，未进入正式裁决；可回收对象和维护循环预算。
5. **不做 VP Up/Down “真主动量”分色**：普通 OHLC/低周期方向法不是交易所 aggressor tape，且主副指标已有 CVD，属于共源重复。
6. **不把 OI/LSR/聚合量复制到主指标**：副指标专职确认；复制会形成假独立投票。
7. **PineCoders 旧仓库不当 2025–2026 证据**：`PineCoders/pine-utils` 最新提交为 2019-08-21；性能/对象结论改以当前 TradingView v6 官方文档为准。

## 四、工程前置与预算释放

- 当前 VP `processAndRender()` 每根 K 全量遍历历史样本并重建分布，属于主要性能风险。优先做增量桶更新＋range 扩张 dirty rebuild；不要只加更多 zone 循环。
- `htfBull/htfBear` 未确认 pack 只有定义无消费者，可删除一条 HTF request，静态调用点 9→8。
- 会话 CVD lead/suffix 链最终无面板消费；要么接回唯一有价值的行，要么整链删除，禁止每 K 白算。
- 单K Profile：数值计算不能要求 `endBar > startBar`；有 intrabar 时应计算 POC/VA，仅零宽绘图跳过。
- 面板当前 11 个显示行；位置/就绪、确认/结构、进场路径存在重复。收敛为结论、方向/位置、唯一 blocker/触发年龄、Entry、Stop、Target/R:R、CVD 等约 6–7 个决策概念，详细诊断留 Data Window。

## 五、经实页核验的来源与日期

- Quant SMC Pro [JOAT]，TradingView 开源，2026-06-14：adaptive pivot、structural-extreme OB、wick/close mitigation、iFVG、EQH/EQL、compact heatmap。  
  https://www.tradingview.com/script/ugOBLSa3-Quant-SMC-Pro-JOAT/
- Order Block Detector [SMC ChartSense]，TradingView 开源，2026-05-06：deepest counter candle、FVG gate、mitigation mode。  
  https://www.tradingview.com/script/1ORCJ6hv-Order-Block-Detector-SMC-ChartSense/
- ICT Balanced Price Range – Double FVG with Volume，更新 2025-03-05：反向 FVG 重叠 BPR；其无界向后扫描不宜照搬，当前有限 FVG 数组可做有界配对。  
  https://www.tradingview.com/script/YlUwYZQa-ICT-Balanced-Price-Range-Double-FVG-with-Volume/
- Adaptive Pivot Structure，2026-02-25。  
  https://www.tradingview.com/script/QhXQwVpN-adaptive-pivot-structure-willyalgotrader/
- Volume Profile With HVN & LVN Detector，2025-02-19：邻域局部峰谷算法。  
  https://www.tradingview.com/script/CHxGnqBD-Volume-Profile-With-HVN-LVN-detector/
- LVN/HVN Auto Detection [PhenLabs]，2025-06-24：多会话节点、分离、持久线与限频处理。  
  https://www.tradingview.com/script/RvNPu7jq-LVN-HVN-Auto-Detection-PhenLabs/
- Previous Day Volume Profile Levels，2025-08-15。  
  https://www.tradingview.com/script/DYXcuVyA-Piman2077-Previous-Day-Volume-Profile-levels/
- Volume Profile Vision，2025-12-09：POC shift、HVN touch、LVN entry。  
  https://www.tradingview.com/script/uHrzzvNI-Volume-Profile-Vision/
- Fib-Weighted Volume Profiles，2026-07-29：POC first-touch 事件。  
  https://www.tradingview.com/script/KPUDW7dp/
- Vestrix.ai Liquidity Atlas，2026-04-28：EQH/EQL、Naked POC 首触、跨模块价位汇合。  
  https://www.tradingview.com/script/NgWB7Udh-Vestrix-ai-Liquidity-Atlas/
- V-Profile Matrix，GitHub，功能提交 2026-06-01：VP 密度/梯度/ATR 参与 FVG vacuum score；源码可查但阈值不可盲抄。  
  https://github.com/VTS92/V-Profile-Matrix-for-TradingView
- TradingView 官方当前文档（访问 2026-08-08）：Profiler、对象 GC/上限、request/plot 限额、VP 语义。  
  https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/  
  https://www.tradingview.com/pine-script-docs/visuals/lines-and-boxes/  
  https://www.tradingview.com/pine-script-docs/writing/limitations/  
  https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/

## 六、交付格式

输出先给“进入最终20项”的候选矩阵，再单列“重复/低价值/已实现”清单。候选按 `执行完整性前置 → 真缺失决策层 → 工程性能 → UX` 排序。结尾必须给直接推荐顺序，并明确“未修改文件、未回测/复盘、未做盈利主张”。
