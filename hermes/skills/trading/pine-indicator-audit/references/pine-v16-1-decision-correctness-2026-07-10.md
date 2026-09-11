# Pine 决策正确性与瘦身实案（2026-07-10）

## 适用范围
审计含 CVD 背离、ADX/DMI、关键位磁吸、主副指标分工的 Pine v6 交易指标。

## 四类容易漏掉的决策缺陷

### 1. 背离过滤“计算了但没消费”
发现 `cvdDivSwingOk = swingRange > 1.5 * ATR` 已定义，但 `cvdBearDivQualified/cvdBullDivQualified` 没引用它。正式背离必须同时包含：数据质量、摆动幅度、CVD slope方向、关键位门控。

```pine
bool cvdBearDivQualified = cvdQualityOk and cvdBearDiv and cvdDivSwingOk and cvdSlope < 0 and keyLevelOk
bool cvdBullDivQualified = cvdQualityOk and cvdBullDiv and cvdDivSwingOk and cvdSlope > 0 and keyLevelOk
```

### 2. 背离星级的事件方向配反
- 熊背离/顶部背离应搭配卖方派发强化。
- 牛背离/底部背离应搭配买方吸收强化。

```pine
cvdBearStars := cvdBearDivQualified ? (cvdDistributeSellQualified ? 3 : 2) : cvdBearDiv ? 1 : 0
cvdBullStars := cvdBullDivQualified ? (cvdAbsorbBuyQualified ? 3 : 2) : cvdBullDiv ? 1 : 0
```

### 3. ADX过热不应无条件否决A级
错误：A级条件直接 `and not dmiHot`，但X级只在 `dmiHot and vwapExtended` 时触发，规则互相矛盾。

正确：只禁止“过热+沿交易方向远离VWAP”，质量回踩仍可执行。

```pine
// 多
not (dmiHot and vwapExtendedUp)
// 空
not (dmiHot and vwapExtendedDn)
```

### 4. Magnet 名称/价格/距离/评分必须原子更新
最近位的 name/price 与全局最高分 score 分开选，会把一个关键位的分数套到另一个关键位。每个候选必须在同一分支内更新完整对象；多/空方向目标也同理。

## Pine 与 Python/HALDRO 的职责迁移
主指标中仅通向死文本的 DXY、VIX、永续-现货溢价请求，以及与 HALDRO 重复的 OI 请求，应物理删除而不是用 input/if 包裹。外部确认由 Python 资产路由器或 HALDRO消费；Pine保留结构、区域、触发与机器字段。

实案结果：主指标 request 调用点 12→8，源码 2893→2835 行；plot/告警/Data Window契约未因瘦身删除。

## 安全清理流程
1. 程序化找声明后全文只出现一次的变量。
2. 只删除单行纯赋值；删除后再次扫描级联死变量。
3. 沿依赖链确认 request 的所有消费者均消失，再物理删除整个请求链。
4. 为关键缺陷先写源码回归测试并看见失败，再改 Pine。
5. 跑 `pine_static_scan.py`，确认 request、plot、未定义变量、def-before-use。
6. 最后才做 TradingView 真实编译和五周期 Data Window 回归。

## 不可误删
- HALDRO 的聚合 OI/LSR/Valid/Risk Code 是副驾驶权威，不能因主指标移除重复OI而一起删除。
- FVG/OB质量分、HTF确认、MCP Data Window、box.set_text区域文字均属于稳定契约。
- 单次出现不一定必然是死代码；函数返回表达式、UDT字段、绘图参数需人工复核作用域与隐式消费。
