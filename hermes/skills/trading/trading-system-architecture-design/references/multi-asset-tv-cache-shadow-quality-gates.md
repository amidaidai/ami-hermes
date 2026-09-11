# 多资产TV缓存、影子记录升级与数据质量闸门

## 1. 通用缓存不能作为多资产唯一真相源

单一`tv_live.json`会被BTC、XAU等轮流覆盖。即使下游有symbol gate，也会造成实时数据降级和旧缓存回退。

生产模式：

```text
tv_live.json                 # 兼容入口
tv_live_BTCUSDT.json         # BTC权威现场
tv_live_XAUUSD.json          # XAU权威现场
```

采集器每次同时写通用缓存和品种独立缓存。决策入口优先读取同品种缓存，再读取通用缓存；两者都必须经过symbol、timestamp、fresh/stale门禁。

系统符号必须先解析为TradingView完整ticker：

- `BTCUSDT → BINANCE:BTCUSDT.P`
- `XAUUSD → OANDA:XAUUSD`

若切图失败后采集器返回旧缓存，包装层必须检查`stale/fresh`和实际symbol，禁止把旧BTC缓存写成XAU独立缓存。

## 2. Data Window权限与结构位分开选源

POC/VAH/VAL在当前柱可能为null，但HALDRO Valid Code、Risk Code、OI、CVD、Composite仍有效。处理顺序：

1. 先按symbol和时间提升新鲜Data Window指标；
2. 再单独寻找POC/VAH/VAL结构缓存；
3. 不得用`poc != null`决定是否采用整个现场缓存。

## 3. 文本计划字段必须在回退前数值化

`"等触发"`、`"待确认"`、`"—"`均为真值字符串。错误写法：

```python
stop = tv_stop or calculated_stop
```

会阻止数值止损回退。正确顺序：

```python
stop = decision_float(tv_stop)
if stop <= 0:
    stop = decision_float(calculated_stop)
```

entry/stop/target/R:R都应采用同一模式。否则FinalVerdict可能安全地NO-GO，但影子记录因价格为0而静默不落盘。

## 4. 同桶影子记录允许权威升级

signal_id按时间桶幂等时，早期`valid_code=0`记录可能先落盘，后续现场HALDRO恢复为2却被“重复”丢弃。

为同ID定义质量元组：

```text
(valid_code, 嵌套契约完整度, features是否存在)
```

新记录质量更高时原位原子替换；相同或更低时保持幂等。写盘使用临时文件+replace，避免半文件。

## 5. 自动影子结果标注

零Token定时标注器每15分钟运行：

- 仅在最长周期（默认16根）闭柱齐全后标注；
- 计算4/8/16根MFE、MAE和先触发目标/止损；
- 同根同时触发按止损优先；
- 结果按signal_id幂等；
- 非支持资产只记unsupported，不伪报错误。

样本不足体制×模型门槛时只报告数量，不输出校准概率。

## 6. 新鲜度必须检查内容质量

仅看mtime会把“刚写入的API失败JSON”误判为健康。关键采集文件应附质量校验，例如清算结果全部为`api_error/no_data`时，即使文件一分钟前写入，也必须标记“接口全部失败”。

采集器在全部数据失败时：

- 不得输出“无信号/市场常态”；
- 输出“不能判断，禁止据此交易”；
- 返回非零退出码；
- 不覆盖最后一份有效快照。

## 7. 运行态优先于静态代码

全面系统审计先检查：

1. scheduler和gateway；
2. active/paused任务数量；
3. 数据年龄与内容质量；
4. 看门狗心跳是否真实更新；
5. 再做静态扫描和测试。

若所有cron同时paused，数据过期通常是结果而非多个采集器同时损坏。恢复前先手工实测上次error任务；修好后批量resume，并复核下一次真实调度状态。
