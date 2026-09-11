---
name: trading-analysis-system-audit-methodology
description: 用于全面审计交易分析系统、策略流程、分析档位、TV链路和分析卡。先取证，再复现，再按P0/P1/P2给出可验证优化。
version: 1.0.0
author: 安禾
tags: [trading, audit, pipeline, tradingview, decision-loop, data-quality]
---

# 交易分析系统全面审计方法论

## 适用范围

当用户要求全面审计交易系统、分析流程、策略、模板、分析档位、TradingView流程、分析卡或全系统优化时使用。覆盖运行态、代码、数据契约、TV指标、路由执行、最终裁决、模板投递与测试，不把单个脚本检查冒充全系统审计。

## 核心原则

1. **当前证据优先**：历史报告只能作为线索；先记录当前时间、仓库、分支、工作树和配置，再引用历史结论。
2. **能力存在不等于能力已使用**：分别判断已配置、可调用、已接线、已参与裁决、已在卡片呈现。
3. **心跳健康不等于业务健康**：进程、心跳、配置有效期、批准对象数量和业务事件必须一起检查。
4. **路由必须约束执行**：比较Router声明的步骤与执行器真实调用、评分输入和FinalVerdict消费。
5. **证据分层**：每条发现标记“当前复现/静态核对/未验证”，不把测试退出码等同于生产正确。
6. **决策单一真相源**：最终卡片、告警、仓位和执行只消费冻结快照与FinalVerdict。
7. **主指标授权、副指标确认**：SVP是唯一执行授权来源；AggVol只确认、降级或否决，不能单独授权。
8. **用户人工控制**：分析系统提供方向、触发、失效和候选价，不自动下单；WAIT/NO-GO不得渲染成执行单。

## 审计顺序

### 阶段一：基线与边界

- 确认canonical仓库和运行目录；读取项目规范、manifest、关键入口。
- 执行`git status --short --branch`，把既有修改与本轮产物分开。
- 检查是否存在归档目录、双脚本目录、多个数据目录和旧兼容路径。
- 明确本轮只审计还是允许修复；未经用户要求不要修改业务代码、提交或推送。

### 修复行动前的前提核验（避免错误 P0/错误修复）

给出「修复/拉起/补cron/提交删除」建议前先核验前提——否则会把「退役」误判成「崩溃」、把「历史状态」误判成「活跃故障」。三把核验锤：

1. **守护进程「退役 vs 崩溃」**：心跳停 ≠ 崩溃。先读脚本 `__main__`：若含 `已退役`/`退役`/`生产权威为` 等字样，说明是兼容壳、真实守护已替换（如 `scripts/行情守望.py` 退役 → 生产为 `keylevel_guard`）。此时心跳文件是旧守护遗留，页面「心跳旧」≠「进程死」。**否则会错误拉起一个只打印“已退役”的壳。**
2. **cron `enabled`/`state` 才是真相**：`hermes cron list` 的 `last_status=ok|error` 可能是禁用/暂停前的历史。读调度器配置（如 `cron/jobs.json`）的 `enabled`+`state`：`enabled:false` 或 `state:paused|disabled` = 不跑，其 error 属历史非活跃故障；不要据此补 cron 或“修复失败任务”。
3. **git 批量删除安全**：提交大量删除前交叉核验 ①启用 cron 的脚本是否指向被删文件 ②被删模块是否仍被活跃脚本 import（**含懒加载** `from X import` 缩进在函数内、以及**动态加载** `importlib.spec_from_file_location("X", ...)`）。活跃依赖方显式 `try/except ImportError` 兜底（如 orion 对 `alert_dedup`）则删安全；裸 import / 无兜底动态 spec → 先 `git checkout HEAD -- <file>` restore。

**守卫生成的非零退出可能是有意诚实信号，不是 bug**：如关键位批准过期（`valid_until` 已过）时看门狗报 `exit 2 / DEGRADED`，是“批准过期不下准生证”的如实上报；续期（把 `valid_until` 重设 `now+有效期`，同步 `updated_at`/renewed_at，备份后原子写）后其退出码转 0、调度器 `last_status` 转 ok。

### 阶段二：运行态健康

按顺序检查：

1. TV Desktop/CDP连接、当前symbol、周期和study列表；
2. 行情守望、BTC守护、关键位守护的真实进程数量；
3. 心跳时间、status、PID一致性；
4. keylevels配置是否存在至少一个未来有效且批准的关键位；
5. cron enabled/state/last_status/next_run、脚本路径和provider/model；
6. 数据文件的mtime、根时间戳、symbol匹配、JSON结构和语义完整性。

同一脚本出现多个Python节点时，先排除uv venv redirector stub父子节点，再判断真多实例。常驻while True进程不能配置为普通周期cron，必须使用daemon+watchdog或支持--once。

### 阶段三：分析管线与档位

对每个资产至少验证BTCUSDT、XAUUSD，并按项目声明扩展外汇、股票、期货、期权：

- `resolve_analysis_mode`触发词是否与文档一致；
- `route_pipeline`步数、主周期和资产分类是否正确；
- quick/inherit/full/monitor的实际执行是否与Router一致；
- inherit是否明确缓存时间、symbol和“继承”语义；
- quick跳过的数据是否仍偷偷进入评分；
- full每一步是否有独立完成/跳过/失败原因；
- XAU是否走专用TV同步和Binance U本位K线，而不是不存在的现货XAUUSDT；
- crypto是否真的接入K线、VWAP/EMA、TV五层和衍生品数据。

“Router打印3步但执行了10步”属于路由-执行漂移，至少P1；若被跳过的数据影响最终方向或等级，升级为P0。

### 阶段四：指标与TV流程

TV读取固定遵循：切目标symbol→等待指标重算→`chart_get_state`核对symbol+周期→读主指标行动格→读副指标行动格→读study values/lines→截全屏图→再次核对关键身份。

- 主指标过滤`SVP+ICT+VWAP+CVD`；副指标过滤`Volume Aggregated`。
- 截图必须含价格轴与CVD窗格；旧截图不能冒充本轮更新。
- 不把`study_values`缩写值当精确关键位；必要时用pine lines/labels。
- Pine云端编译没有真实回执时，只能写“未验证”。
- CVD若为K线方向或低周期估算，必须标注估算，不能写成交易所真实主动成交。
- 检查Packed Bus的合同号、Valid Code、Coverage、OI一致率、CVD质量和数据新鲜度是否被Python正确解码。

### 阶段五：决策与策略闭环

追踪完整链路：指标/采集写入→标准化快照→特征→体制→候选方案→闸门→FinalVerdict→渲染。

强制验证：

- `X禁做`必须NO-GO；
- `WAIT/NO-GO`必须`executable=false`且清空entry/stop/target；观察价只能放watch字段；
- B/C等待只能展示触发条件和人工候选，不得给执行损益指令；
- `R:R < 2.0`不得执行；
- 主副冲突、TV未现场验证、数据过期、zone质量不足和高级门控拒绝不能被后置渲染覆盖；
- 结论包含“观望/未收线/等解除/等收线/冲突”等C等待语义时，不能被数值Grade Code兜底改成A；
- 主指标与副指标方向冲突时，卡片不得出现“主副同向”。

必须使用矛盾夹具测试，而不只测正常A多路径：主指标X/冲突/未收线+AggVol S3、主副反向、A但RR不足、错symbol缓存、多源时间不一致、异常Max Pain。

### 阶段六：模板、卡片和投递

核对模板、renderer与FinalVerdict是否同一版本：

- 五周期D→4h→1h→15m→5m；
- 结构位先于价格；
- 只允许一个⭐主推；备选仅失效路径；
- 截图首行；结论、机会/陷阱/禁做和触发/失效前置；
- quick与full形态确实不同，而非只改标题；
- RichMarkdown真表格必须走专用发送器，不能用普通MarkdownV2假设会渲染管道表；
- 推送成功必须有真实回执，cron `ok`或stdout存在不等于用户可见。

### 阶段七：问题分级与整改

| 等级 | 判定 |
|---|---|
| P0 | 会导致错误方向/执行价、数据跨品种污染、关键守护空转、FinalVerdict被绕过、生产分析不可相信 |
| P1 | 显著降低完整性、覆盖率、可观测性或档位一致性，但有明确降级 |
| P2 | 可维护性、成本、审美、文档和非关键冗余优化 |

每个问题必须记录：证据路径/命令、当前结果、根因、影响、修复建议、验收标准、证据等级。不可引用不存在的字段，不可仅凭grep行号认定调用关系；命中后必须看上下文并追踪生产者到消费者。

## 交付格式

先给总体结论和评分，再给短表格：运行态、P0/P1/P2、管线档位、TV/双指标、模板投递、优化顺序。若包含交易分析截图，截图首行并用本地绝对路径Markdown引用。报告只写已取证内容；缺少实盘收益、用户端可见性或云端编译回执时明确标“未验证”。

详细证据模板和矛盾夹具清单见`references/current-audit-evidence-pattern.md`。
