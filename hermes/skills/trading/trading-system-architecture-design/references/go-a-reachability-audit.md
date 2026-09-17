# 闸门饥饿审计（GO-A 授权可达性）

## 何时跑

用户说「你总是不给方案」「怎么一直是禁做」「从来没见你做过单」时——
这是一条**审计触发**，不是在抱怨语气。先取证，再解释。
不要用「今天没有优势」去回答一个系统性现象。

## 核心判据

裁决系统若在长窗口（≥1 个月且 ≥200 条信号）里可执行授权出现 **0 次**，那是**系统缺陷，不是行情判断**。
只能输出单一状态的闸门等于没有闸门：它无法区分「今天没有优势」和「永远没有优势」。

## 数据源

| 文件 | 内容 |
|:--|:--|
| `data/shadow/decision_signals.jsonl` | 每条候选：`signal_id/symbol/timeframe/side/entry/stop/target/model_id/regime/grade/final_state/blockers[]` |
| `data/shadow/decision_outcomes.jsonl` | 已标注结果：`outcome.{h4,h8,h16}.{mfe_r,mae_r,first_hit}` |

探针（本技能自带，只读，一次拿到下面全部六节）——从仓库根目录跑：
`python 'hermes/skills/trading/trading-system-architecture-design/scripts/gate_starvation_audit.py' .`（末参 = 仓库根）。

## 步骤

1. **档位/等级分布**：`final_state` 与 `grade` 分别数。出现次数为 0 的档位就是被结构封死的档位。
2. **必须把有方向与无方向分开再报比例**（最容易误导自己的一步）：账本记录**每一次扫描**，
   `side=neutral` 常占七成。直接报「85% NO-GO」会把「本来就没方向」算成「被否决」。
   正确口径：先数有方向候选（`side in (long,short)`），再**只对这个子集**报裁决分布与拦因。
3. **有方向信号的拦因频次** ＋ **「只差一个条件」子集**（`len(blockers)==1`）——后者离放行最近，修复杠杆最大。
   - **先剔幽灵再统计**：冻结快照重放会批量伪造候选样本——识别四件套：① 几何长期固定且与现价差一个量级；② 拦因签名逐条固定重复（同一组 5–8 条）；③ 关键数值全盘扫描只命中账本自身（任何缓存/快照/配置里都不存在）；④ **把数值 grep 到 `tests/`（含 git 历史）：命中测试夹具常量 ⇒ 夹具污染**——修法=影子写入口加 `PYTEST_CURRENT_TEST` 隔离守卫 + 清污，与生产数据线无关（2026-09-17 实案：63884/64000 两夹具 223 条）。命中即从可达性统计中剔除、单独列账。
4. **顺着拦因回源码，把每道门定性为「行情判断」还是「工程状态」**：
   - 第二层 = `scripts/decision_loop.py`：`hard` 列表 → 硬阻断；`wait` 列表 → 停留观察。
   - **硬门/等待拆分口径（防误计）**：账本 `blockers` 是 hard＋wait 合并元组，按名字集合硬分类会把 `svp_authorization` 这类双语义码（hard=禁做·不出价／wait=未授权）误计；唯一可靠口径 = 解析 `final_verdict.reason` 的前缀「硬闸门：a/b/c」，无此前缀即等待。
   - 第一层 = Pine 的 `setupLongA/setupShortA` 的 AND 链 ＋ `setupGradeStable` 稳定器。
5. **数 AND 链长度**。两层各 10+ 个条件串联且彼此不独立时，通过率是**乘积**不是最小值；
   链越长，「全绿」越接近不可达。
6. **查恒真/恒假门**：依赖一个从不填充的字段、一个长期陈旧的快照、或一条永远无效的副指标总线。
   恒真硬门会让系统永久 NO-GO，而且卡面只会显示「数据/风控黄灯」，不会自曝。

## 已确认的结构（复核后按最新代码更新，别背旧结论）

| 层 | 位置 | 性质 |
|:--|:--|:--|
| 第一层 | Pine `setupLongA/setupShortA` | 十余项 AND；且**升级需连续 N 根相同候选、撤销即时**——不对称稳定器使 raw-A 窗口常在被提升前关闭 |
| 第二层 | `scripts/decision_loop.py` | `is_a = grade.startswith("A")` 才可能 GO-A；再叠 hard 门 ＋ wait 门，并要求 `regime`／`risk`／`advanced` 三者非空 |
| 刀口 | `decision_loop.py` 的 `if is_bc: wait.append("b_wait")` | B 级与 C反被一律降为等待 → 中间档候选完全失去输出，是「总是禁做」的主因之一 |
| 等级来源 | `auto_card.py::_grade_from_mcp_values` | `MCP Grade Code`：3=A／2=B／1=C反／-1=X／0=C等待 |
| 副指标依赖 | Pine `aggAllowLongA/aggAllowShortA` ＋ `decision_loop` 的 `haldro_invalid` | 两条路径依赖**同一条副指标 Bus**：`valid_code<=0` 时第一层封 A、第二层记 wait，双重卡死 |

## 第一层沉默时的逐位解码（卡面只写「C等待」时必须做）

卡面只会写「副S3冲突·不执行」「C等待」——真正的封锁原因在 TV Data Window 的打包码里。
先把现场值读出来，再逐位拆解，才能定性「行情判断」还是「工程缺陷」。

读现场（TV MCP，只读）：`data_get_study_values()` — 一次拿到全部可见 study 的 Data Window 值。

拆包（解码器全在 `scripts/tv_indicator_contract.py`，**不要手算位**）：

| 现场字段 | 解码函数 | 关键位 |
|:--|:--|:--|
| `MCP NoTrade Reason Code` | `decode_no_trade` | 位表 `NO_TRADE_BITS`：1 HTF冲突X／2 过热追高／4 低流动性／8 几何不成立／16 R:R不足／32 CVD质量不达标／64 ADR禁追／128 溢折价／256 本根未收线／512 触发不新鲜／1024 副指标冲突降权 |
| `MCP Quality Code` | `decode_quality_code` | 1 HTF冲突／2 CVD质量／4 低流动／8 ADR／16 HTF-FVG／32 MSS／64 EMA顺序 |
| `MCP Evidence Pack` | `decode_evidence_pack` | 方向位 ＋ `locationValid`／`triggerConfirmed`／`barClosed` |
| `MCP Trigger Pack` | `decode_trigger_pack` | `triggerCode`／`age`／`fresh`／`signalState`；`age=999` 是无触发哨兵 |
| `MCP StructPack` | `decode_struct_pack` | FVG/OB/BOS/流动性；全 0 = 附近无有效结构 |
| `MCP Entry Valid Code` | `decode_entry_valid` | `0=无方向` ← 账本记 `neutral` 的直接来源 |
| `HALDRO State` / `Risk Code` | `decode_haldro_state` / `decode_quality_code` | Risk 位 4=上级冲突、64=LSR拥挤 |

**判据**：`Entry Valid=0` ⇒ 第一层根本没给方向，账本只能记 `neutral`，这跟「被闸门拦住」是两回事。
把 `NoTrade` 的置位逐个定性：属行情特征（上级冲突／拥挤／位置无效／无结构）的照实报；
属工程状态的（样本未成熟、字段恒空、快照陈旧）才是可修项。

## 时机直方图：抓「数据未成熟被当成质量不合格」的假阴性

同一根父周期 K 线内，低周期样本是**逐分钟长出来**的：门槛要求 `N` 个低周期样本时，
父 K 线前 `N-1` 分钟内的读数**必然**判不合格，与行情好坏无关。
若扫描／落账时机没有避开这段成长期，就会批量生产假阴性。

探针（账本 `ts` 对父周期取模，数分钟位置）：

```python
d = datetime.fromtimestamp(r['ts']/1000, timezone(timedelta(hours=8)))
pos[d.minute % 15] += 1        # 15m 父周期
```

判据：若前 `N-1` 分钟占比显著即可定性（实测约 44% 落在 +0..+4），
说明大量信号是在「数据还没长好」时被记录的，账本里的 NO-GO 有相当比例是**假的**。

## 根因类别：上游把「待定」并进「不合格」（语义合并）

比字段缺失更隐蔽的一类缺陷：上游**内部已经区分**两种状态，**上报时却合成同一个码**。

实案：Pine 里 `cvdLowSample`（低周期样本未攒够＝**待重试**）与 `not cvdQualityOk`
（样本够了但质量差＝**真不行**）被写进同一位：

```pine
int mcpQualityCode = ... + ((not cvdQualityOk or cvdLowSample) ? 2 : 0) + ...
```

而同一文件早就定义过 `cvdLowSample`、还把它标成「·存疑」显示在图上——**内部有、上报丢**。
后果：下游无法把「等一会再判」与「就是不行」分开，只能一律判负 → 长期封锁。

**检查动作**：在上游源码里搜「内部变量 → 上报码」的组装行（通常是一个大表达式），
看有没有 `or` / `+` 把「未成熟」「数据缺失」「待重试」类布尔与「真不合格」类布尔合并。
**修法**：给「未成熟／待定」单独的位，下游对这位只标记重试、不判负；
或让扫描侧加成熟度门槛（父周期内 `minute >= N` 才落候选），先低成本止血。

## 先核对契约 title 再宣布「字段名不匹配」

怀疑上游字段读不到时，**不要直接断定是命名 bug**。逐键比对：

```python
import tv_indicator_contract as TVC
TVC.DW_ALIASES_SUB['haldro_valid_code']   # 契约里注册的 Data Window title
```

把它与 `data_get_study_values()` **现场返回的 title 字符串**（含括号与中文后缀，逐字符）对齐。
两者一致 ⇒ 读取链是通的，问题在别处（判定门槛／时机／上游合并上报）。
曾据此否掉一个「字段名不匹配」的误判——当 bug 修会白改一遍。

## 结果数据不能为闸门背书

影子账本里的价位多半**不具可执行性**——大量样本在某 horizon 内既未触及目标也未触及止损。
这类结果既不能证明「闸门拦对了」，也不能证明「拦错了」。拿它当闸门正确性证据是自欺。
要用结果说话，先确认样本是真正可成交的入场位（进场价贴近现价、目标在结构可达范围内），
否则先修样本质量，再谈闸门调参。

## 拦因语义去重

同一个「现在不做」会被记成 5-7 条独立拦因（无方向／等待语言／未收线／位置／触发／对齐／收盘）。
注意 `no_direction` 与 `b_wait` **基本互斥**（分别对应 C等待 与 B 级），**不是**重复项——
真正的冗余是「等待家族」在单条信号里叠 5-7 个。汇报时折成「1 条主因 ＋ 明细」，
否则卡面的 NO-GO 看起来像几十个闸门同时红了。

## 已落地的修复：CVD 样本未成熟拆位（2026-09-17 实案闭环）

上面「语义合并」那一节的处置已完整落地。位定义必须与代码一致，**改动时同步六处，漏一处即静默不一致**：

| 层 | 文件 | 改动 |
|:--|:--|:--|
| 协议 | `tv_indicator_contract.py` | `NO_TRADE_BITS` 新增 `2048: "CVD样本未成熟·待定"`；`decode_quality_code` 新增 `cvdSampleImmature = bool(n & 128)` |
| Pine 质量码 | SVP `mcpQualityCode` 组装行 | `((not cvdQualityOk or cvdLowSample) ? 2 : 0)` → `((not cvdQualityOk and not cvdLowSample) ? 2 : 0) + (cvdLowSample ? 128 : 0)` |
| Pine 禁做码 | SVP `noTradeReasonCode` 组装行 | `not cvdQualityOk` → `not cvdQualityOk and not cvdLowSample`，并加 `+ (cvdLowSample ? 2048 : 0)` |
| 决策层 | `decision_loop.py` | quality：`quality["raw"] & ~128` 非零才落 wait，否则只记 `svp_quality_pending`；no_trade：`int(code) & ~2048` 非零才落 wait |
| 解除条件 | `decision_matrix.py` | `RELEASE_ACTIONS[2048]` ＋ 纳入 `TRANSIENT_BITS`；缺了会被 `test_every_release_action_is_verifiable_not_platitude` 直接拦下 |
| 账本 | `auto_card.py` | 影子记录新增 `bar_pos_ms` / `cvd_sample_mature`：**只打标不丢弃**，过滤权交给校准/WFO 消费方 |

测试 `tests/test_cvd_sample_immature_20260917.py`：14 条，成对覆盖「仅样本位不 wait」与「带动其它位仍 wait」。

**上线顺序不能反（渐进兼容）**：旧 Pine 仍把未成熟并进 bit2，新决策层算 `2 & ~128 = 2` 仍 wait，行为不变；
只有 Pine 开始上报 128/2048 才生效。**先改下游、再编译上游**；反过来会有一段失去拦截。

**位分配的坑**：`NO_TRADE_BITS` 已用到 1024（新位必须 2048 起），Quality 码已用到 64（新位 128）。
测试里硬编码的全位掩码（`2047`）加位即失效，一律改 `sum(NO_TRADE_BITS)`。

**主指标由用户手动编译**（用户明确定的边界：「指标编译我来做，你修改好就行」）：
改完源码后把**文件路径 ＋ 改了哪两行**交给用户即可，不要自行走云编译或改图上的脚本。

## 修复方向（按性价比）

1. **先查库，再提政策**：本技能已记录用户对 B/C 人工候选的明确立场——
   「用户允许展示清晰标注的人工候选 Entry/Stop/Target，不代表 GO-A；WAIT/NO-GO 执行字段仍清空，
   X 禁做不显示可操作候选」。所以「中间档给不给价位」**不是待决问题**，已有裁决。
   要做的是核实 `candidate_entry` / `watch_entry` 这条人工候选路径是否真的渲染到了卡面——
   若信号被打成 WAIT 后卡面只剩「主推 禁做」而候选价没出现，那是**渲染缺口，不是政策缺口**。
   ⚠ 反之，若确认要改**授权语义**（让中间档点亮 ⭐、或放宽某道门），那是策略变更：
   必须用户拍板，并在交付里明文披露改了哪一道门。
2. **查副指标 Bus 无效占比**：若大段时间 `valid_code<=0` 属工程问题，修一条同时打开两层。
3. **拦因去重**：让卡面「为什么不做」说人话。

## 坑

- 不要把「0 次 GO-A」直接解释成「行情不好」。先跑数据再下结论。
- 不要静默放宽风控或改动授权语义——那不是 bug 修复。
- **提政策改动前先检索技能库**：用户对同一问题可能早已拍过板（本次即如此）。
  重复问一个已裁决的问题，比不问更伤信任。
- 审计脚本写成 `outputs/*.py` 再跑，不要长内联 python（易被 hardline block）。
- 影子日志可能只覆盖最近数周，报窗口时如实写起止日期，不要夸大成「长期」。
- **复核外部结论（含其它模型产出的审计稿）**：每条主张对源码行逐一核验，输出用「采纳／修正／必补」三分类；必查是否还有未闭环的人工动作（如编辑器点「保存」），不要停在「可直接上线」。

## 2026-09-17 复核快照（已闭环 · 修正版）

**重大更正：所谓「幽灵记录生产线」= 测试夹具污染生产账本，不是生产数据线。**
夹具源：`tests/test_card_render_locked.py` `prices.primary=63884`（2026-06-19 起）、
`tests/test_p0_p1_audit_regressions.py` `price=64000.0`（2026-06-21 起），随每次 pytest 经影子写入口入账 223 条。
修复前现场复现（pytest 运行中账本新增同几何记录）⇒ 加 `PYTEST_CURRENT_TEST` 隔离守卫 + 清污隔离（509→286 / 238→18）。
**教训：账本异常几何先对照测试夹具常量与 pytest 运行时间分布，再怀疑生产数据线；「数值只存在于账本」不是生产 bug 的充分证据。**

**已落地修复：**

- 陈旧几何守卫 `geometry_guard`（偏离 >10% → `stale_geometry` 硬门 + 转隔离）；夹具价=现价时偏差 0 抓不到，夹具防御靠 pytest 隔离守卫。
- P0-b：无真实计划时合成 ATR 参考几何不做计划级硬否决（改可见等待 `risk_reference_geometry`，永不授权）；真计划 RR<1.5 硬否决保留。来源标记在 `setdefault` 兜底之前采样；路由计划须自带三件套（`geometry_from_result`）才算真实几何（实跑暴露兜底回填恒真后修正）。
- **P0-c（cross_source 未运行→降级）撤回**：依据数据为夹具污染；无主源运行应 fail-closed。
- S3 拆位（2026-09-18 用户拍板）：S3 的 OI 部分（bit128，旧口径「非全体一致」）从硬拦降为可见等待 `haldro_state_consensus`；CVD 背离（bit16）保留硬拦。Pine 侧 oiDivergeA 对齐合格线（一致率<75% 或离散度>2.5）+ 单所方向死区（fixed15，待编译）。实盘 S3 38/38 全由「非全体一致」误触发、CVD 背离 0 次。
- 生产验证：09-17 23:51 / 09-18 00:29 调度记录硬门仅剩 `haldro_state_conflict`，`risk_constitution` 假否决消失。

**修正后真实后段样本（09-15 后）= 18 条全 NO-GO**：risk_constitution 15（P0-b 后消除）· advanced_confluence 11 · haldro_state_conflict 7 · x/svp/trigger 各 2 · 其余 1。
仍拦方案的真实状态门：SVP A 级授权（副确认 S1/S2）/ 副指标未确认（降权等待）/ 共振 ≥4 / 触发·位置·收线。
明细：`docs/maintenance/2026-09-17-goa-starvation-recheck.md`。
