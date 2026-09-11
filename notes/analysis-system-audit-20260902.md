# 棠溪分析系统全景审计与改进方案

审计时间：2026年9月2日 21：47（本机运行态输出）
审计范围：采集契约、六类资产、档位路由、分析卡/模板、FinalVerdict、指标应用、TradingView、缓存并发、Cron与守护。
证据原则：当前代码/当前运行态优先；历史技能中的“已接入”只作为待复核声明。

## 一、结论先行

当前系统处于“代码链路基本可用、运行态数据不可直接用于正式交易卡”的状态。

- 代码质量：已修复本批 P2 类型边界；目标采集器 Pyright 0 errors；全量测试 381 passed；compileall 通过。
- 档位规则：已按用户新规则落地。轻量=quick；“现在呢/继续/接着看/更新”=standard；“分析/全面/深度/完整卡”=full；裸品种=quick。
- 完整管线：BTC 当前路由 15 步，XAU 8 步；不能再以旧文档的“加密10步”作为代码完成度真相。
- TV：CDP 当前 OK，但 BTC TV实时缓存/来源快照约2.34小时过期；XAU单源快照约0.25小时有效，但五周期完整证据仍失败。
- 风控：FinalVerdict已经是生产裁决中心；B/C等待不产生执行权，R:R统一至少1:2，X禁做硬阻断；需持续验证所有渲染器均消费最终裁决。
- 运行态：批准关键位 configured=8、active=0；BTC关键位看门狗最近 error。心跳或Cron“进程活着”不能等同于“业务健康”。
- 自动交易边界：未启用自动下单；本审计不修改Cron、不重启守护、不外发Telegram。

正式BTC/XAU分析前，当前应输出 WAIT/不宜使用旧快照，先恢复TV五周期、来源快照和有效批准关键位。

## 二、当前实测证据

| 维度 | 当前事实 | 影响 | 等级 |
|---|---|---|---|
| Pyright | 目标12个采集/桥接脚本 0 errors | P2类型闭合 | ✅ |
| 测试 | `python -m pytest -q`：381 passed in 19.71s | 回归通过 | ✅ |
| 编译 | `python -m compileall -q scripts tests`：通过 | 语法通过 | ✅ |
| 档位 | resolve实测：quick/standard/full符合用户关键词 | 对话定档正确 | ✅ |
| BTC TV | `tv_live_BTCUSDT.json` stale，age=2.34h | 不得冒充实时 | P0运行态 |
| BTC快照 | `source_snapshot_BTCUSDT.json` stale，age=2.34h | 完整卡数据门禁失败 | P0运行态 |
| XAU TV | `tv_live_XAUUSD.json` cache，age=0.25h，身份有效 | 单源可读 | ⚠️ |
| 五周期 | BTC五周期过期；XAU缺D/4h/1h/15m/5m完整层 | Full不能声称完成 | P0/P1 |
| 关键位 | configured=8，active=0 | 看门狗空转，不能触发有效事件 | P0 |
| Cron | 25总任务，4 enabled；BTC守护最近error | 需看业务健康而非enabled | P1 |
| TV CDP | OK | 连接本身正常 | ✅ |

原始证据来自：`python scripts/audit_preflight.py`，失败退出码1；不能把该失败包装为健康。

## 三、六类资产路由审计

| 资产 | 主周期 | Full路由实测 | 必须保留的数据源 | 明确禁用/隔离 |
|---|---:|---:|---|---|
| 加密 BTC/ETH/SOL | 15m | 15步 | TV、Binance衍生品、CoinGecko、宏观、X、Cron落盘、CVD、Depth、Corr、模型/体制/双指标/高级订单流/风控 | 不让情绪或副指标改写FinalVerdict |
| 黄金 XAU/XAG | 5m | 8步 | TV、宏观/金十、X、Cron、CVD、Corr、GLD/GDX/TIP/COT | 禁AggVol、Funding、Taker、加密情绪缓存 |
| 外汇 | 15m | 7步 | TV、宏观/金十、X、Cron、Corr、利差/央行窗口 | 禁Binance衍生品语义 |
| 股票 | 1h | 8步 | TV、宏观、X、Cron、Corr、FMP、期权链、财报/跳空 | 区分盘前盘后、财报窗口 |
| 期货 | 15m | 6步 | TV、宏观、X、Cron、Corr、合约/库存/事件 | 区分连续合约、交割月、夜盘 |
| 期权 | 跟随底层 | 3步 | 底层TV、期权链、卡片 | 先标的后期权；MaxPain无效不得入结论 |

当前优点是资产画像已进入 `pipeline_router.py`；主要风险是部分历史技能仍写旧的“10步/8步”叙述，模型容易按文档而非router执行。改进：每次卡片从router返回的结构化步骤生成完成度表，不手写步数。

## 四、分析档次与卡片审计

### 已有结构

- quick：执行周期截图/报价/主指标行动格；加密补Binance方向票。
- standard：quick基础上补相邻周期结论行，不跑完整全源。
- full：五周期和全源管线。
- monitor：只做事件检测，不输出方向卡。

### 已修复

- “现在呢/继续/接着看/更新”现在稳定返回 `standard`，不再因缺少上下文误降quick或误升full。
- `auto_card.py`兼容 `standard`，其范围等同执行+上下文，不会触发完整全源块。
- FinalVerdict的WAIT/NO-GO不输出可执行Entry/Stop/Target；B/C只保留人工候选字段。

### 仍需改进

1. 卡片档位、管线档位、输出密度必须拆成三个字段：`analysis_mode`、`pipeline_scope`、`render_profile`。当前历史代码/技能仍有把“full采集”和“8表展示”混称的风险。
2. 完整卡必须显示15步实际router审计，不再固定10步文字。
3. 标准卡必须有固定“相邻周期结论行”字段，缺失时显示 `unavailable/missing_timestamp`，不能静默退化为主周期卡。
4. 每张卡必须绑定 `run_id`、symbol、timeframe、captured_at、source matrix revision；截图与文字卡必须同一run_id。
5. 卡片只允许一个⭐主推；WAIT时写“等待/不宜”，不能用旧A/B菜单制造方向错觉。

## 五、模板审计

当前权威模板：`references/master-template-v68.md`，文件头 v9.10；渲染器 `render_v96.py`/`render_tv_card.py`为v9.9级别标记。存在版本号漂移，虽不一定改变业务，但会让维护者无法判断哪个模板权威。

建议采用单一版本源：

- `contracts/card_schema.py` 定义字段与版本。
- `pipeline_router.py` 定义步骤和档位。
- `master-template-v68.md`只定义人类展示顺序。
- 渲染器读取schema/version，禁止在渲染器内硬编码步骤数量。
- CI断言：模板版本、两渲染器版本、卡schema版本必须一致；管道步骤来自router。

推荐卡片四层：

1. 首行：截图MEDIA；随后方向、价格、中文时间。
2. 当前状态：上方结构｜现价｜下方结构；一句推荐或等待。
3. 三/四个核心表：周期体温、关键位、多源验证/双指标、唯一主推。
4. 尾部：FinalVerdict、失效、数据完整性和降级原因。

普通对话输出保持简明；完整数据在后台/产物中留证，不把15步流水账塞进用户首屏。

## 六、指标应用审计

### 主指标：SVP+ICT+VWAP+CVD

应承担：结构、价值区、POC/VAH/VAL、VWAP/EMA、FVG/OB/Breaker、市场结构、CVD、行动格、入场条件、失效条件、磁吸目标。

规则：主指标行动格是方向第一真源。行动格含“冲突/未收线/等收线/等解除/观望/C等待”时，必须WAIT，不能用外部指标或数值兜底改成A做多/做空。

### 副指标：Volume Aggregated/HALDRO

仅承担：多所成交量、OI聚合、持仓四象限、CVD/主动买卖确认、覆盖率与质量。

规则：只确认、降级或否决；不独立授权，不得覆盖主指标。非加密资产必须标记不适用，不得把AggVol、Funding、Taker语义移植到XAU/外汇/股票。

### 外部源

- Binance：实时价格、K线、持仓、Funding、多空比、主动买卖、深度。
- CoinGecko/FinanceKit：市值、板块、流动性、趋势；失败可见降级。
- Dune/稳定币/清算/QLib/Deribit：背景与确认；必须有本地原子落盘和显式captured_at。
- 宏观/金十/COT/相关性：事件和跨市场背景；不能单独生成执行方向。
- X/Grok：情绪、催化剂、盲点；绝不能改FinalVerdict或价格三件套。

### 指标层改进

建立 `indicator_evidence` 结构，逐字段记录：值、来源、周期、采集时间、质量、作用（主裁决/确认/降级/否决/仅观察）。禁止把“指标文字出现在卡里”当成指标已使用。

## 七、TradingView审计与改进

当前优点：CDP可用；主/副指标读取路径、截图工具、五层周期规则、身份校验和缓存质量契约已有代码/测试覆盖。

当前风险：

- BTC缓存过期；XAU虽有单源缓存，但五周期记录缺失。
- 共享TV图表是全局状态；多个任务切品种/周期存在污染风险。
- 旧技能仍有“每周期连续切换”与“独立会话”两种叙述，必须只保留经过实测的路径。
- 截图必须验证 symbol+resolution，并与文字卡绑定；不能以文件mtime冒充市场观测时间。
- 主指标和副指标必须分开读取；研究列表中没有独立OI时，使用AggVol OI字段并在卡中写明来源。

建议：

1. 为TV读取实现统一事务：lock → set symbol/timeframe → wait → chart_get_state → read → chart_get_state二次核验 → 原子发布。
2. 每个五周期记录强制字段：symbol、timeframe、resolution、captured_at、bars、action_table_complete、identity_valid、source_quality。
3. 任一层错品种/错周期/缺时间戳/空行动格：整层unavailable，不覆盖上一份有效缓存。
4. 图像和JSON使用同一`batch_id`与最大时间偏差；不匹配就不发卡。
5. 建立TV现场健康分与业务健康分：CDP连接是连接层，五周期完整+主指标行动格才是业务层。

## 八、采集、缓存与来源契约

本批修复已完成：有界线程池、共享缓存原子合并、`captured_at`与`observed_at`分离、缺时间戳降级、结构化`_source_records`、目标采集器Pyright清零。

仍需推进：

- 对 `coingecko_collector.py`、`forex_rate.py`、`options_chain.py`、`jin10_gold_bridge.py`、`correlation_matrix.py`逐一确认attach_source_contract和原子落盘覆盖，不以import存在判定完成。
- 所有cron采集器必须落本地结构化JSON；仅stdout/TG的QLib、清算、稳定币输出不能作为cron_read真源。
- 每个来源保留失败记录（not_run/empty/unavailable/quota_cooldown），不让可选源影响FinalVerdict。
- 缓存选择按captured_at，不按mtime；文件mtime只能作为运维指标。
- 429按源级15分钟熔断，但每张卡必须展示熔断状态。

## 九、流程改进：建议的“数据到决策”唯一闭环

1. 资产识别：`asset_analysis_profile()`。
2. 关键词定档：`resolve_analysis_mode()`。
3. 生成router步骤：不得手写步骤。
4. TV事务读取：身份、周期、时间戳、行动格。
5. 实时报价仲裁：TV与Binance只做时间邻近和结构位校验。
6. 结构裁决：SVP主指标。
7. 副指标确认/降级/否决：AggVol仅加密。
8. 外部多源交叉：价格/持仓/资金费率/宏观/链上/情绪分层。
9. FinalVerdict：唯一执行权，失败关闭。
10. 风控检查：R:R≥1:2、风险上限、事件、保护状态、组合暴露。
11. 生成卡：同run_id、同source matrix、唯一主推。
12. 发布校验：截图身份、文字术语、WAIT无执行价、来源状态可见。
13. 复盘记录：预测与结果分离，按资产/模型/体制统计胜率与期望。

## 十、P0/P1/P2改进顺序

| 优先级 | 任务 | 验收标准 |
|---|---|---|
| P0 | 恢复BTC有效批准关键位 | active>0、valid_until未过期、看门狗last_status=ok、触发器单次无误报 |
| P0 | 恢复BTC TV五周期与source snapshot | 五层identity_valid=true、显式captured_at、TTL通过 |
| P0 | 补齐XAU五周期现场证据 | D/4h/1h/15m/5m均有记录；HALDRO不参与方向 |
| P1 | 统一15步router为唯一完成度真相 | 卡片审计步骤动态生成，文档不再硬编码10步 |
| P1 | TV读写事务锁+batch_id绑定 | 并发切图压测无污染，错身份不覆盖缓存 |
| P1 | 来源落盘全覆盖 | 每个cron源有JSON envelope和status/error/timestamp |
| P1 | 模板/schema/渲染版本统一 | CI断言版本一致；quick/standard/full输出快照测试 |
| P1 | 标准档相邻周期合同 | 15m主执行补4h/5m；XAU 5m补1h/15m；缺失明确显示 |
| P2 | indicator_evidence字段化 | 每个结论可回溯到源、周期、时间和作用 |
| P2 | 复盘统计按模型/体制/资产拆分 | 不是只看总体命中率；含样本量与置信区间 |
| P2 | 资产专属模板 | 黄金、外汇、股票、期货、期权不共享加密术语 |
| P2 | 健康看板 | 连接健康、数据健康、业务健康三层分开 |

## 十一、最终建议

不要继续无边界增加指标或API。下一阶段最有效的提升不是“再加十个源”，而是：

- 让router、source contract、FinalVerdict、renderer成为四个唯一真相层；
- 把TV现场读取做成不可污染的事务；
- 把所有声明“已接入”的源改成可验证的结构化证据；
- 把quick/standard/full变成机器合同而非自然语言约定；
- 把复盘结果反馈到“资产×模型×体制×时段”，用真实期望值淘汰无效方案；
- 保持人工开单边界，不做自动交易；
- 当前在运行态恢复完成前，正式卡只报等待/不宜，不给伪实时执行三件套。
