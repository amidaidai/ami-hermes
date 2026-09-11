# Pine Script 2026 生态与配额（2026-08-09 联网核实）

来源：TradingView Pine docs（release-notes / writing/limitations / other-timeframes-and-data）、TV 官方博客、TradersPost/Supa/Pineify 2026 解读。以下均为跨会话稳定事实，直接引用。

## 版本

- **Pine v6 仍是当前版本（2026 全年无 v7）**。@version=6 是正确写法。
- 2025-08：字符串最大长度提升 10 倍（长警报消息/Webhook 无压力）。
- 2026-01 release notes + 2026-03-02 官方博客：volume footprints 正式进 Pine。

## request.footprint()（2026 新能力，审计增强方向）

- 当前签名：`request.footprint(ticks_per_row, va_percent, imbalance_percent) → series footprint`；后两项可选，默认分别为 70 和 300。
- 对象方法：`buy_volume()` / `sell_volume()` / `delta()` / `total_volume()` / `poc()` / `vah()` / `val()` / `rows()`；行对象可取价格、分类量、delta 和 imbalance。
- **仅 Premium/Ultimate 可用**；低阶账户不能使用含该请求的脚本。不要把它作为“免费档可自动降级”的同一脚本分支，除非已在目标账户实测其加载/编译行为。
- 单脚本只允许 **一个唯一 footprint 请求**。嵌套在 `request.security()` 的不同数据集也可能形成第二个 footprint 请求并触发运行时错误。
- 无 footprint 数据的 bar 返回 `na`，必须先判 `na`。
- 官方语义：TradingView 按低周期 intrabar price action 把成交量分类为 “buy/sell”；它不是官方声明的交易所原生 bid/ask aggressor tape。仍应标注来源/估算分类口径，不得称“真实逐笔订单流”。

## 配额（2026-08 官方复核）

- **64 plot counts / script，所有计划相同**。Data Window-only 与 `display.none` 的 `plot*()` 也在内。基本 `plot(series)`=1；真正 series-qualified 的 color/textcolor 参数各再加 1；`plotcandle()` 最多 7。`alertcondition()`、`bgcolor()`、`barcolor()`各 1；`fill()`仅 series color 时占 1；`hline/line/label/box/table`为 0。
- **40 个已执行的唯一 `request.*()` 上下文**；Ultimate 64，没有“60”档。Pine v6 dynamic requests 可让一个调用点执行零/一/多个上下文；相同函数+相同参数通常复用，库内调用仍单独计。动态循环可能在第 41 个不同上下文时报运行时错误。
- **Intrabar**：Basic/Essential/Plus/Premium 100K；Expert 125K；Ultimate 200K。用 `calc_bars_count` 限制实际抓取量。
- 价格页当前列出 Pine 计算时间：Basic 20s、Essential/Plus/Premium 40s、Ultimate 100s；Pine Limitations 文字仍概括为 Basic 20s/其他 40s，存在官方页面不同步，交付时注明来源日期。
- 价格页当前列出图表历史 bars：5K / 10K / 10K / 20K / 40K；这是账户可加载图表历史，不等同于所有 series 的历史引用缓冲。
- `alert()` 不绕过账户的技术警报数量限制；它只改变脚本内触发/消息方式。Basic 是否可创建该类警报以实时价格页为准，不能拿运行时 `alert()` 当免费替代。

## CVD/订单流 2026 社区共识

- **背离必须 confluence**：价格结构（关键位/VA）+ 摆动幅度（>1.5ATR 过滤噪声）+ 吸收/派发方向区分。纯价格-CVD divergence 无 standalone edge（GitHub SoCloseSociety/TradeBobbyTerminal commit bed5b8b 实测）。
- CVD 指南（2026 quantum-algo / takeprofit / united-daytraders）一致：CVD 不预测方向，只揭示"推动当前波动的攻击性是否在减弱"——背离是主要用法。

## 审计方法备注

- 锚定一致性核对：建 market×timeframe 矩阵（SVP 分布图 / S VWAP / CVD 主 / CVD 副 四列），逐格比对。已知典型分叉：CVD 锚定缺市场维度；1d+ 图 SVP=12M vs CVD/VWAP=M；注释声称"一致"但实现不一致。
- 市场判定：BINANCE:XAUUSDT.P 的 syminfo.type=='crypto'，必须用 ticker 字符串检测（XAU/XAG/GOLD/SILVER/GC/SI）判定贵金属，否则 XAU 会被当加密聚合处理。
