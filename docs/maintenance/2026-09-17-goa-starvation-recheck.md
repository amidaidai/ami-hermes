# GO-A 饥饿复核（2026-09-17 晚间）：为什么「一直不能出现可以做的」

背景：用户问「你再审计一下看看，为什么一直不能出现可以做的，是太严格了吗？」
承接 09-15（GO-A 零出现审计 + PLAN-B）与 09-16（影子账本可执行性取证）。本轮**只读**，未改任何代码/指标/配置。

## 一、复跑取证

`gate_starvation_audit.py`：505 条信号 / 234 条已标注，窗口 2026-07-10 23:28 → 09-17 16:52。

| 项 | 实测 |
|:--|:--|
| final_state | NO-GO 438（86.7%）· WAIT 66 · GO-B 1 · **GO-A 0** |
| grade | B等待 298 · C等待 163 · X禁做 44 · **A 级 0** |
| 有方向候选 | 111/505（22%，**全部在 09-15 之前**） |
| 有方向拦因 | haldro_invalid 82.9% · b_wait 82.0% · cross_source 47.7% |
| 只差一步 | 14 个，其中 12 个 = **07-11 同一组幽灵记录**（真实近邻 0） |
| 零拦因 | 1/505 |

现场探针 `a_grade_probe.py BTCUSDT`（缓存 17:10）：**9/24 通过**；NoTrade=1024（副指标冲突/降权）、S3 冲突、OI 离散 3.06、无触发（age=999）、无方向、无位置。本帧是「真等」，未通过项为行情/结构条件。

## 二、修复窗口（09-15 16:00 之后）49 条逐条分解

| 类别 | 条数 | 特征 | 硬门 |
|:--|--:|:--|:--|
| **幽灵记录** | 30 | `entry=63884.0`（7 月几何）；`cross_validation.hard_blockers=["tv_main"]`；无 TV 载荷；证据全缺；7 条固定拦因 | cross_source ×30 |
| **真实记录** | 19 | 现场价格；C等待/观望 | risk_constitution ×16 · advanced_confluence ×11 · haldro_state_conflict ×6 · x_forbidden ×4 · cross_source ×3 |

- **无硬门记录 = 0/49** → PLAN-B 资格（需无硬门）从未满足 → 账本 0 条 PLAN-B；`data/*.md` 卡面「人工方案」段从未渲染过。
- `risk_constitution` 主因：无真实计划时，系统用**合成 ATR 参考几何**（stop/target = ±ATR 倍数，实测隐含 R:R 0.48–1.28）去跑风控 **RR<1.5 硬否决**——否决的是系统自己造的默认计划；另有 3 条 ATR 止损夹层（3.1–3.4×ATR）、2 条 09-15 旧格式（“<2.0 底线”）。
- `advanced_confluence`：full 模式「多周期共振 3/6<4 → ✗否决」（quick 模式跳过；无否决时也可能待定）。

## 三、幽灵记录生产线（P0，仍在活动）

- 精确口径 `main.entry == 63884.0`：**209 条**（07-11 → 09-17），09-15 之后 **30 条**；**审计当天仍在写**（6 条：07:16 / 13:11 / 13:27 / 15:55 / 16:39 / 16:52）。
- 该三元组（63884 / 64139.536 / 63372.928）在当前**任何缓存/快照/配置中都不存在**（全盘扫描）；只存在于账本自身。
- 写入路径唯一 = `auto_card._resolve_card_final_verdict` 影子写入口（schema_version 20260905 + bar_pos_ms 证明为当前代码）。运行特征：无 TV 载荷（tv_main payload_present=false）、副指标无效（valid_code=0）、证据缺失（version/direction/symbol/timeframe/study_id/source_time 全部报错）、风险快照 stale（source_date 2026-07-15）。
- 影响：账本「B 级候选」统计被同一组 7 月几何撑起；WFO/校准若不过滤 = 系统性假样本。与 09-16 发现同源；当时只禁了 WFO，未修写入侧。
- 下一步：影子写入口加**陈旧几何守卫**（`|entry−现价|/现价` 超阈值 → 标 `stale_geometry`、不入账），并用探针定位该输入源（候选：会话/交互式 auto_card 运行的降级路径）。

## 四、副指标 Bus 与 A 级可达性

- `dual.valid_code`：全期 0 占 66.7%（337/505）；后段（≥09-15）0 占 73%（36/49）。有方向信号 82.9% 撞 `haldro_invalid`。
- 指标侧 A 级 68 天 0 次：≥14 项 AND + 不对称稳定器（升级需连续 N 根、撤销即时）→ 按系统判据属结构缺陷。

## 五、判定

**不是单一「太严格」。零可做 = 三件叠加：**

1. **设计层**：A 级可达性（0/505）+ 全门串联（GO-A = 指标侧 ≥14 项 AND + 决策侧 ~35 项条件几乎同时全绿）。
2. **工程层**（后段实测主拦因）：risk 合成几何自否决（13/19 真记录）、cross_source 把「TV 载荷缺失」记成「核心来源失效」（幽灵 30 + 真 3）、advanced 共振 3/6 长链、副指标 Bus 无效约 2/3。
3. **数据层**：幽灵记录 30/49 污染。

## 六、修复顺序（先工程、后政策）

- **P0-a 幽灵记录**：陈旧几何守卫 + 探针定位（不改授权语义）。
- **P0-b risk_constitution**：无真实计划时不拿合成 ATR 几何做 RR 硬否决（真计划 RR<1.5 硬否决保留）。⚠ 定性（设计 or 语义错配）需用户确认。
- **P0-c cross_source**：「未运行/载荷缺失」≠ 冲突 → 降为可见降级；真冲突才硬。
- **P0-d 副指标 Bus**：查 valid=0/冲突偏高成因（采集窗口 vs 接线）。
- **P1 渲染可见性**：核对 PLAN-B/人工候选为何久未上卡（用户已有裁决：B/C 可给人工候选价、不给授权）。
- **P2 待拍板**：A 级稳定器对称化 / advanced 门槛 —— 工程修完观察 1 个月再议。

**边界**：本轮只读；未改代码；未提交。复跑入口：`hermes/skills/trading/trading-system-architecture-design/scripts/gate_starvation_audit.py`。

## 七、2026-09-17 深夜定案（覆盖上文 §二/§三/§六 的对应条目）

### 7.1 重大更正：幽灵记录 = 测试夹具污染，不是生产数据线

- 夹具源两处：`tests/test_card_render_locked.py:45` `prices.primary=63884`（2026-06-19 起）、
  `tests/test_p0_p1_audit_regressions.py:41` `_minimal_klines(price=64000.0)`（2026-06-21 起）。
  随每次 pytest 经影子写入口写入生产账本，共 223 条（214×63884 + 9×64000）。
- 证据链：修复前在 pytest 运行中现场复现（账本 20:26/20:38 新增两条 63884 记录，几何与夹具逐字一致）；
  09-16 10:15/10:30 两条 64000 记录同源。
- 修法：影子写入口 pytest 隔离守卫（`PYTEST_CURRENT_TEST` 且无显式 `_shadow_path` → 不写生产账本）；
  已清污 223 条至 `data/shadow/quarantine_20260917/`（账本 509→286 信号 / 238→18 结果）。
- 结论：§三「幽灵记录生产线」不存在；§二 30 条幽灵的 cross_source 归因作废。
  其余重复几何组（4348/4119/4486/1.16 等）与当日 `source_snapshots` 逐字一致 ⇒ 是**真实降级运行**（源冻结），保留。

### 7.2 P0 落地 / 撤回

- **P0-a**（已落地）：`geometry_guard` 陈旧几何守卫，|entry−现价|/现价 >10% → `stale_geometry` 硬门 + 转隔离。
  局限：夹具价=夹具现价时偏差 0，抓不到夹具；夹具防御靠 pytest 隔离守卫。
- **P0-b**（已落地，用户拍板）：无真实计划时不再拿合成 ATR 参考几何做 RR/夹层硬否决 →
  改可见等待 `risk_reference_geometry`（永不授权）；真计划 RR<1.5 硬否决保留。
  接线：来源标记在 `decision_main.setdefault` 兜底之前采样；路由计划须自带完整三件套
  （`geometry_from_result` 标记）才算真实几何——实跑暴露「兜底回填恒真」后修正。
- **P0-c**（撤回）：cross_source「未运行→降级」不再实施。依据数据为夹具污染；
  且无主源运行的降级会让合成几何流进「人工方案」段，fail-closed 正确。§六 P0-c 条目作废。
- **P0-d**：按原计划继续观察。

### 7.3 修正后的真实后段样本（09-15 16:00 后，去夹具 = 18 条，全 NO-GO）

硬门频次：risk_constitution 15（其中合成几何误拦部分已被 P0-b 消除）· advanced_confluence 11 ·
haldro_state_conflict 7 · x_forbidden 2 · svp_entry_forbidden 2 · trigger_pack_forbidden 2 ·
exhaustion_chase 1 · tv_live 1 · cross_source 1。

### 7.4 生产验证（修复后调度器真实运行）

- 09-17 23:51:14 与 09-18 00:29:23 两条记录：`risk.plan_geometry=False`、`violations=[]`、
  blockers 含 `risk_reference_geometry`（可见等待）、**硬门仅 `haldro_state_conflict`**。
- ⇒ 合成几何假否决已在生产消除；剩余硬门为真实副指标状态。

### 7.5 现在仍拦「方案」的真实条件（非工程缺陷）

① SVP 转 A 级授权（当前 C等待）；② haldo 退出 S3 冲突；③ advanced 共振 ≥4/6；④ 触发/位置/收线等行情条件。
以上状态翻转即出方案。回归：1466 passed / 1 skipped（新增 `tests/test_p0_gate_semantics_20260917.py`）。

## 八、S3 拆位与副指标口径修复（2026-09-18 凌晨 · 用户拍板「全做」）

### 8.1 取证结论（为什么修）

- 全账本 S3 记录 **38 条，100% 由 OI 跨所分歧（bit128）驱动**；CVD 背离（bit16）**0 次**。
- 旧判定「4 所方向非全体一致即分歧」（纯符号、无死区）与合格线「一致率 ≥75%」自相矛盾：
  3:1（75%）同时算「合格」和「分歧」→ S3 → 主指标封 A（aggAllow 要求 S1/S2）+ 决策层硬禁。
- 副指标「确认态」S1 从未出现、S2 仅 3 次（有状态样本 78 条）→ A 级通路结构性不可达。

### 8.2 Python 侧（已落地 · 1471 passed / 1 skipped）

- `decision_loop`：state==3 拆位——bit16 → 硬拦 `haldro_state_conflict`；bit128 → 可见等待
  `haldro_state_consensus`（降权不硬禁，永不授权）；风险码缺失/无法归因 → 保守维持硬拦；family 归「副指标未确认」。
- `auto_card`：`_dual_indicator_verdict` 同源拆位（`_s3_hard`/`_s3_soft`）——「X禁做观察」只对 bit16；
  bit128 → 「B等待（副数据分歧）」+ 文案「副数据分歧·降权观察」；risk_defs 位表对齐 AggVol 现行版
  （删死位 bit8；补 128=OI跨所分歧、256=数据未就绪）。
- `decision_matrix.synthesis_verdict`：新增 `haldro_risk` 入参同源拆位（bit16 否决 / bit128 降权）；
  `_apply_matrix_guard` 随之把 GO-A 降为 WAIT/B 而非 NO-GO。
- `go_nogo_gate`：门7 黄灯前缀补「副数据分歧」。
- 回归新增：`test_decision_loop_vnext` +2 · `test_v13_decision_matrix` +2 · `test_audit_fixes_20260913` +1。

### 8.3 Pine 侧（fixed15 已生成 · 待用户编译保存）

- 文件：`outputs/pine_20260905/AggVol_audit_fixed15_20260918.pine`（971 行，sha24 `125489ac95e71a36e16487ff`；
  diff 存档 `AggVol_fixed15_diff_20260918.diff`）。
- 改动 6 处：① 新增输入 `OI_DIR_EPS`（跨所OI方向死区%，默认 0.05，可调）；② 单所方向计数加死区 +
  新增 `oiDirVotesA`；③ 一致率分母改「有效方向票」；④ `oiDivergeA = oiDispersionRiskA`
  （分歧 = 一致率<75% 或 离散度>2.5，与合格线同源）；⑤ dataQualityRiskA 去 any-split 票；
  ⑥ 风险码 bit128 改由 oiDispersionRiskA 驱动。
- 静态分析：离线检查 0 问题（与 fixed14 基线一致）；括号平衡；旧变量名零残留。
- 预期：3:1 多数一致不再判 S3（S1/S2 恢复可达）；2:2 真分歧仍 S3（Python 侧记等待，不硬禁）。
- 待办：用户编译保存 → 云端三方核验 → pin 三处更新（contract / field-map / alignment）。

### 8.4 边界

- 授权强度不变：A 仍要求副确认（S1/S2）；本修复只收窄「否决」的适用范围——真矛盾（CVD 背离）才否决。
- 不采用「只留 OI」：CVD 承担方向票 + 背离检测 + 订单流面板；修的是语义，不是数据源。

## 九、方案可达性复查（2026-09-18 上午 · 全指标审计）

用户再报「从来不会出现可以做的方案」。按「当前证据优先」全面复查（291 条账本 + 实跑 + 源码）：

### 9.1 复查数据
- GO-A 0 次（窗口 07-10→09-18）；零拦因 1/292；**292 条扫描全部带几何候选**（e/s/t 全非空）。
- 候选 rr 分布：**≥1.5 占 48%（141/292）** · ≥2.0 占 31%。
- 等级：C等待 170 · B等待 87 · X禁做 35（无 A）。
- B 级帧（有裁决 25 条）全 NO-GO；真硬门（reason 前缀口径）：tv_live 18 · cross_source 18（09-11/09-13 TV 链路故障期产物，XAU 侧 09-16 还有一次）· risk_constitution 16（假否决，已修）· advanced_confluence 5 · exhaustion_chase 3。
- 全账本真硬门 Top：risk_constitution 85（已修）· advanced_confluence 47 · haldo_state_conflict 38（S3 拆位后 OI 部分降为等待）· x_forbidden 21 · cross_source 21 · tv_live 19 · svp/trigger forbidden 各 19。
- 08:47 实跑（修复后）：state=WAIT · 14 条全等待 · **0 硬门** · 结论「副S4降权·仅候选」（总线修复生效）；该帧候选 rr=0.54。

### 9.2 结构（源码）
- 主指标 A 链 = **14 项 AND**（fixed18 L2662-2663）+ **A 级需连续 2 根**（L2695-2702）；B 链（bcDirectRaw）≈10 项（L2719-2720）。
- 决策层：PLAN-B = B 级 + 方向 + 几何 + **无任何硬门** + rr≥1.5（L617-624）；GO-A = A + 无硬门 + 无等待 + 非弱副。
- 高级门控：共振<4/6 → execute=False → 硬门 advanced_confluence（auto_card L4212-4215 → decision_loop L578-582）。

### 9.3 发现
- F1（显示）：render_v96 把非执行态一律渲染「⚠️主推 禁做」——**WAIT 也写禁做**；card_reformat 写「等待，不做单」。两渲染器口径不一致，是「从来都是禁做」观感的一半来源。
- F2（政策候选）：共振<4 连坐人工方案（PLAN-B）——执行级门控误杀非授权方案。建议对 PLAN-B 豁免并标注（GO-A 不变）。
- F3（结构）：A 链 14 项 + 稳定器 → GO-A 结构性稀有；建议先通 B/PLAN-B 通道 1-2 周再议分层。
- F4（副指标）：**非瓶颈**——B 级帧 0 次硬拦；当前帧 A 探针 24 项中副相关仅 2-3 项。结论：保留，不删。

### 9.4 状态
- fixed15 尚未编译（截至 09-18 08:31 核验，云端仍 09-14 版）。
- 待拍板：① PLAN-B 豁免共振硬门 ② WAIT/禁做卡面文案分离 ③ A 链分层（缓）。

## 十、PLAN-B 豁免执行级硬门 + WAIT/禁做文案分离（2026-09-18 上午 · 用户批准）

### 10.1 ① PLAN-B 豁免共振硬门（策略变更·明文披露）
- 变更点：`decision_loop.PLAN_B_EXEMPT_HARD = {"advanced_confluence"}` —— 共振<4/6 不再连坐「非授权人工方案（PLAN-B）」。
- 边界：**GO-A 不变**（advanced 仍硬拦，授权语义零变动）；豁免门完整保留在 `blockers` / `warnings` / `plan.upgrade_prereqs`；
  方案帧 `reason` 用「人工方案（非授权）：…·未达执行级门：advanced_confluence」前缀——审计口径（「硬闸门：」前缀）不受污染。
- 依据：全账本 advanced_confluence 硬门 47 次；B 级帧 5/25 本可出人工方案却被连坐。

### 10.2 ② WAIT/禁做 卡面文案分离
- `render_v96`：非执行态不再一律「⚠️主推 禁做」——「禁做」只留给 NO-GO / X；
  WAIT（含 rr<2 曾被误折的等待帧）→「⏳主推 等待」；PLAN-B →「🧭主推 人工方案（非授权）」并指向方案区。
- `card_reformat`：main_push 解析支持 ⏳/🧭；人话映射更新（⏳→「等待，不做单」· 🧭→「人工方案（未授权…）」· ⚠️禁做→「禁做，不做单」）。
- 生产实况（09:36 实跑）：首屏「⏳主推 等待 — dual_alignment」／④「⏳主推 等待 | 待 15m·VAH 确认」／裁决「🔵等待 — 主线R:R不足(<1:2)」——三处不再误标禁做。

### 10.3 验证与遗留
- 定向 12 文件 **207 passed**；全量 **1477 passed / 1 skipped**；账本零泄漏。
- 新增测试 6：豁免（3）+ 文案分离（2）+ 方案帧主推（1）。
- 遗留：fixed15 待编译；推送卡 `render_tv_card` 对 PLAN-B 仍显示「⭐主推 等待」（已分离、但未指向方案区——后续项）。
