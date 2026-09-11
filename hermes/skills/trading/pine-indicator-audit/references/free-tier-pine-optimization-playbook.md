# 免费档（Basic）Pine 性能与配额手册

适用：TradingView **Basic/免费** 账号下运行 SVP+ICT+VWAP+CVD 主指标 + AggVol 副指标。目标是“在真实免费档边界内稳定运行”，不得把付费能力包装成免费可用。

复用前重访官方 Pricing、Limitations、Dynamic requests 与 Profiler 页面；账号档位和配额会变化。

## 一、官方硬边界（2026-08-08复核）

| 配额 | Basic | 设计含义 |
|---|---:|---|
| 历史K | 5,000 | 低周期只覆盖近期；不要承诺长历史 |
| 总计算时限 | 20 秒 | SVP全量重算、LTF数组和多venue请求是主要风险 |
| 指标/图 | 2 | 主+副正好占满，不再建议第三个指标 |
| Indicator-on-indicator | 1 | 可用一个 `input.source()`把副指标数值输出接入主指标 |
| 技术告警 | 0 | `alertcondition()`与`alert()`都不能绕过账号权限创建运行告警 |
| intrabars | 100K | `calc_bars_count`必须按完整计算跨度规划 |
| request配额 | 40 runtime-unique | v6动态请求按实际访问的context/expression计，不是源码调用点静态总数 |
| plot count | 64/脚本 | `alertcondition()`、`bgcolor()`及series-color输出也可能计数 |
| Footprint | 不可用 | Basic不能运行调用 `request.footprint()` 的脚本；不是“每K返回na” |

官方来源：
- https://www.tradingview.com/pricing/
- https://www.tradingview.com/pine-script-docs/writing/limitations/
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#dynamic-requests
- https://www.tradingview.com/pine-script-docs/concepts/inputs/#source-input

## 二、优先优化顺序

### 1. Basic构建物理删除原生技术告警负担

- `alertcondition()`在Basic无法被运行告警使用，且每个会占plot count；Basic构建应物理删除。
- `alert()`不占相同的独立plot count，但Basic仍不能据此创建技术告警，**绝不能写成免费绕过方案**。
- Basic实际通知交给外部扫描/推送管线。若要兼容付费升级，维护独立Pro告警模块或付费构建，不要让Basic版长期计算无消费的消息链。
- 付费构建合并告警时，用进入事件 `state and not state[1]`，闭柱需求显式用 `barstate.isconfirmed`；多条件OR组必须整体加括号，防止尾部分支绕过市场/质量门控。

### 2. `calc_bars_count`按完整profile跨度动态规划

禁止硬编码 `calc_bars_count = 1000`。例如日锚SVP使用1分钟精度至少需要1440根intrabar；1000会截断约30%，直接改变POC/VAH/VAL。

规划规则：

1. 计算当前最长会被消费的完整profile/anchor跨度；
2. 换算为所选LTF所需intrabar数量；
3. 加必要warm-up和安全余量；
4. 不得低于完整周期需求，也不得超过Basic 100K上限；
5. CVD和SVP分别按各自真实消费跨度设置，不能共用拍脑袋常数。

降低 `calc_bars_count` 后必须核对POC/VAH/VAL、CVD anchor、覆盖起点和高周期行为；“加载更快”不能替代数值等价验证。

### 3. 合并同context请求，按运行时context审计

- 同symbol/timeframe的多个 `request.security*()`字段优先合成一个tuple或UDT请求，降低运行时间、内存和compiled size。
- Pine v6默认dynamic requests。未执行的市场/venue分支可以不产生对应runtime context；因此非加密图表应短路OI/LSR/基差请求。
- 一个动态调用访问N个symbol/timeframe仍可能消耗N个unique contexts；不能把“一处源码调用”报告为“1个请求”。
- 实时阶段不能首次访问历史阶段未预取的新context或expression。审计同时报告默认配置和最坏可达配置。

### 4. 只延后渲染，不延后历史数值计算

- table、box、line等仅需最终可见状态的更新可放到 `barstate.islast`，对象优先用 `set*()`更新而非删建。
- POC/VAH/VAL、决策状态、MCP/Data Window等历史数值必须保持每K确定性；不得为了性能把整个profile数值计算只留在最后一根K。
- 大型profile优先做增量桶更新；最后一根K只负责全量对象渲染或必要重建。

### 5. 用一个 `input.source()`连接主副指标

Basic允许一个indicator-on-indicator连接。优先复用AggVol现有数值plot导出packed `valid/confirm/risk`，由主指标通过 `input.source()`读取：

- 不增加第三个指标；
- 不新增request；
- 能复用现有Composite/Valid/Risk plot时不新增plot；
- 未连接、`na`或副指标不适用品种时中性降级，不能自动扣分；
- 主指标仍是唯一Entry/Stop/Target和开单授权源，副指标只确认、降级、否决。

## 三、Profiler验收

性能结论必须使用Pine Profiler，而不是源码行数或主观估计：

1. 依次测试5m、15m、1h、4h及主战品种；
2. 覆盖默认输入和最重可达输入；
3. 每个配置重复运行，避免把资源波动当成确定结论；
4. 重点查看LTF请求、profile循环、venue循环、对象创建和table更新；
5. 优先消除循环内 `array.indexof()`、重复sum/min/range及其他loop-invariant计算；
6. 完成后再用TradingView服务器编译和Add-to-chart运行确认。

来源：https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/

## 四、静态与运行时验证

- 统计真实plot counts，不只数 `plot(` 行；series color、fill、bgcolor和alertcondition单独核对。
- 静态列出request调用点后，展开默认与最坏runtime contexts。
- 剥离注释和字符串后再检查括号平衡，避免中文括号和消息文本造成假阳性。
- 没有服务器编译回执时只能写“静态未发现超限”；没有Profiler/Add-to-chart结果时只能写“性能风险/候选优化”。
- 优化前后核对Data Window字段、行动格、POC/VAH/VAL、CVD质量码和主副联动码，防止为了省配额破坏消费链。

## 五、禁止误读

- Basic技术告警为0，不代表价格告警也为0；两者不能混写。
- `alert()`不占多个`alertcondition()`槽，不等于它能绕过Basic账号权限。
- `request.footprint()`的`na`表示某根K无可用footprint数据；Basic账号限制是脚本调用资格，不应描述为“免费每K返回na”。
- Dynamic request能让未执行分支省runtime context，但不能让N个实际venue数据集变成1个unique context。
- 更小的`calc_bars_count`不是天然优化；若截断完整anchor，它是决策正确性回归。
