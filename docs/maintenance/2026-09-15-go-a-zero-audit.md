# GO-A 零出现审计与 PLAN-B 修复（2026-09-15）

用户反馈：「感觉你一直都是不给出方案的，总是禁止做。」本文是取证、根因与修复记录。

## 一、取证：不是感觉问题

数据源 `data/shadow/decision_signals.jsonl` + `decision_outcomes.jsonl`，区间 2026-07-10 → 09-15。

| 指标 | 实测 | 含义 |
|:--|--:|:--|
| 信号总数 | 454 | — |
| `final_state = GO-A` | **0** | 两个月一次都没有 |
| `NO-GO` / `WAIT` / `GO-B` | 85.2% / 14.5% / 0.2% | 全是「不做」 |
| grade 分布 | B等待 58.4% · C等待 32.8% · X禁做 8.8% | **A 级 0 次** |
| 无任何 blocker 的信号 | 1 / 454（0.2%） | 几乎每个信号都被拦 |
| 有方向信号（111）主拦因 | `haldro_invalid` 82.9% · `b_wait` 82.0% · `cross_source` 47.7% | 三个门吃掉绝大多数 |
| 只差一个条件 | 14 / 111（其中 12 个只差 `haldro_invalid`） | 差一步的极少 |
| 至少撞 1 条「等待家族」 | 438 / 454 | — |
| 同时撞 5–7 条同义门 | 190 | 一个「不做」被记成 5–7 条独立否决 |

## 二、根因

**两层 AND 串联 + 一刀切**：

1. **Pine SVP 的 A 级 = 14 个条件同时成立**（趋势分≥阈值、分差≥2、CVD、价在 VWAP 一侧、接受度、高周允许、社区闸、非过热、离散度、溢折价、ADR 空间、流动性、OB 或关键位、副指标授权），外加上升需连续 N 根候选、撤销即时的不对称稳定器。
2. **`decision_loop.py` 第二层再叠 ~30 项**（9 个硬门 + 十几个等待门 + regime/risk/advanced 必须都在且非空）。
3. **致命一刀**：`P0-1(2026-08-31)` 把 B 级和 C反一律塞进 `b_wait`。B 级占 58%，本意是「结构成立、方向明确、等触发」，从此等同于不做单。

结果：卡面把**「不能自动执行」和「不能给方案」压成同一个状态**，中间的等待带全部塌缩成 ⚠禁做。

## 三、一个不能忽略的数据质量坑

103 个已标注的有方向样本（h4）：命中目标 **1** 次、止损 14 次、**88 次既没到目标也没到止损**。说明影子账本记录的价位本身不具可执行性，因此这份结果数据**既不能证明闸门对，也不能证明闸门错** —— 不能拿它替「不做」背书。

## 四、修复

| 项 | 改动 | 文件 |
|:--|:--|:--|
| P0 | 新增 `PLAN-B` 四态：B 级结构成立+方向明确+几何有效+R:R≥1.5+**无任何硬门** → 出「人工方案」（参考进场区/失效位/参考目标区），`executable` 恒 false，方案只写 `plan` 字段 | `scripts/decision_loop.py` |
| P0 | 两层渲染：原生卡 `## 人工方案（非授权·需人工确认）`；v7 表格版 `**④ 人工方案**` + 总结改口（不再说「当前不给入场价」） | `scripts/render_v96.py`、`scripts/card_reformat.py` |
| P1 | 拦因归并：`primary_blocker` + `blocker_groups`，卡面加 `主因 <code>（家族） · N 类 / M 条`，证据层一字不减 | `scripts/decision_loop.py`、两层渲染 |
| P2 | 新增 A 级可达性探针：逐项对照并区分「行情没机会」与「工程封死」 | `scripts/a_grade_probe.py` |

**不可退让的边界**：`PLAN-B` 恒 `executable=false`、`state` 永不带 `GO`、`⭐` 只在 GO-A 点亮、有硬门则连 `plan` 都不生成。

## 五、验收

- 全量回归 **1273 passed / 1 skipped**（基线 1250）。
- 新增用例：`tests/test_plan_b_manual_plan.py`（11）、`tests/test_plan_b_card_render.py`（6）、`tests/test_a_grade_probe.py`（5）。
- 单条语义变更并已在用例中注明理由：`tests/test_decision_bar_closed.py` 的 `B多` 期望由 `WAIT` 改为 `PLAN-B`（该用例的实质不变量——无执行权、三件套为空、watch 价全保留——未变）。
- 真实管线复核：`data/auto_card_BTCUSDT_full.md` 已带 `主因：exhaustion_chase（风控/体制拦截）` 行；影子账本新增条目已带 `primary_blocker` 与 `blocker_groups`。

## 六、现场复核（2026-09-15 15:00–16:00 BJT，BTC 15m）

- 主指标 SVP：`Grade Code=-1`（X禁做）、`Entry Valid=-3`、`Side Code=9`、`NoTrade=过热追高X+副指标冲突/降权`。
- 副指标 AggVol：`Valid Code=2`（**有效**，非无效）、`State Pack=3`（S3 冲突），覆盖 5 所现货/4 所永续。
- 探针结论：本帧 9/24 项通过，未通过项**都是行情/结构条件**，不是接线故障。**纠正了「副指标长期无效封死 A 级」的初判**：`valid_code` 在影子样本里 67% 为 0，但现场为 2，属间歇而非恒坏，待后续按 `a_grade_probe.py` 持续采样定性。
- 另一条初判也已收回：`risk_constitution.py` 的「风险快照陈旧」在 2026-09-13 就修成「只上报、不硬拦」，不是硬门来源。

## 七、追加发现与修复（同日）：R:R 一处软一处硬

顺着「44% 的信号撞 `risk_constitution` 硬门」往下查，得到一条同类缺陷。

**同一事实、两种定性**：

| 位置 | 对 R:R<2.0 的定性 | 后果 |
|:--|:--|:--|
| `decision_loop.py`（rr_ratio） | **等待类**：「WAIT 保留人工观察候选」 | 给观察价 |
| `risk_constitution.py` 检查2（原实现） | **violation → `allowed=False` → 硬门 `risk_constitution`** | 连候选价都不给 |

合同与 `tv_indicator_contract` 都明写「1.5–1.99 = B/C 人工观察候选·不授权执行」。一律硬否决等于**把合同中段整段杀掉**。

**实测规模**（203 条 `allowed=False` 的信号）：

| R:R 区间 | 条数 | 应然 |
|:--|--:|:--|
| < 1.5 | 137 | 硬否决（连候选都不给）—— 原逻辑正确 |
| **1.5–1.99** | **46** | **应为 B/C 人工观察候选 —— 被错杀** |
| ≥ 2.0 却记 violation | 4 | `f"{rr:.1f}"` 把 1.96 印成 2.0 的格式伪影 |
| 其它（止损夹层 ×ATR、历史陈旧快照） | 16 | 止损夹层属真违规 |

另有 **52 条 B 级信号同时被 `risk_constitution`（硬）+ `rr_ratio`（等待）拦下** —— 同一事实两处计数。

**修复**：`risk_constitution.py` 新增 `OBSERVE_RR_RATIO = 1.5`（与 `tv_indicator_contract.RR_BC_MIN` 对齐，并用用例钉住一致性），检查2 改分层：

- `rr < 1.5` → violation（维持硬否决）
- `1.5 ≤ rr < 2.0` → 不记 violation，写 `observe_only_rr` + 原因「仅B/C人工观察候选」
- 格式改 `:.2f`，消除「2.0:1 < 2.0:1」

**执行权不变（关键安全不变量）**：GO-A 需要 `not wait`，而 `rr_ratio` 仍在 wait 里 → R:R<2 物理上到不了 GO-A。已用 `test_observe_band_can_never_authorize_execution` 钉住。

## 八、实测：改之前 / 改之后

把影子账本里记录的真实输入（`main`/`dual`/`regime`/`risk`/`advanced` 快照）用新逻辑原样重放 459 条：

| 状态 | 改之前 | 改之后 |
|:--|--:|--:|
| NO-GO | 86.3% | 72.8% |
| WAIT | 13.5% | 7.2% |
| **PLAN-B** | **0** | **20.0%（92 tick）** |
| **GO-A** | **0** | **0** ← 不新增任何执行权 |

**必须同时说明的口径问题**：92 个 tick 里 87 个是**同一套位**在连续 15m tick 上的重复记录。按价位去重后只有 **6 个不同方案**（BTC 5 · AAPL 1），即约两个月 6 套。所以「20%」是 tick 加权口径，**不代表真的每 5 次分析就有 1 次出方案**；真实频率要低一个量级。两个数都要看，不能只引用好看的那个。

