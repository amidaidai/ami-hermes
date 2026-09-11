# 决策链架构静态审计记录 (2026-07-11)

## 触发指令
用户要求：`全面只读审计 D:/Hermes agent 的分析策略、FinalVerdict、模型路由、风控、回测/影子闭环。找出能力声明但未在 auto_card/decision_loop 运行态消费的模块，给出P0/P1/P2及文件行号。不要修改文件。`

---

## 核心发现：vNext 核心模块已实现但主流程未接入

| 模块 | 文件 | 状态 | 备注 |
|------|------|------|------|
| FinalVerdict 单一真相 | `scripts/decision_loop.py:15-35` | ✅ 实现完整 | `auto_card.py:703-862` `_resolve_card_final_verdict()` 已调用，**但主流程 `build_setup_metadata()` 未使用** |
| 决策体制分类器 | `scripts/decision_regime.py:23-87` | ✅ 实现完整 | 仅在 `_resolve_card_final_verdict()` 内部使用 |
| 模型路由器 | `scripts/model_router.py:17-56` | ✅ 实现完整 | 仅在 `_resolve_card_final_verdict()` 内部使用 |
| 影子校准闭环 | `scripts/shadow_calibration.py:27-138` | ✅ 实现完整 | 仅在 `_resolve_card_final_verdict()` 内部写入 |
| 特征构建器 | `scripts/feature_builder.py:45-112` | ✅ 实现完整 | 仅在 `_resolve_card_final_verdict()` 内部调用 |
| 风控宪法 v2 | `scripts/risk_constitution_v2.py` | ✅ 存在 | 未在主流程消费 |

---

## P0 — 必须修复（阻断单一真相与风控一致性）

### 1. 引入 `decision_gate.py` 单一决策入口
- **现状**：`auto_card.py:71-90` `build_setup_metadata()` 本地计算风险/方向/状态，**未消费 FinalVerdict**
- **目标**：`build_setup_metadata()` → 调用 `decide()` → `to_auto_card_meta()`
- **参考设计**：`scripts/audit_decision_chain_patch.md:30-108` (`decision_gate.py` 伪代码)
- **涉及行号**：
  - `auto_card.py:71-90` `build_setup_metadata()`
  - `auto_card.py:125-162` `_adaptive_risk()` — 删除，改调 `risk_constitution.combined_risk_check()`
  - `auto_card.py:470-626` `_dual_indicator_verdict()` — 核心裁决提取到 `decision_gate._resolve_main_sub()`

### 2. 统一风险出口
- **现状三重口径**：
  1. `risk_constitution.py:660-702` `combined_risk_check()` — 设计为唯一出口，**无调用方真正用作最终出口**
  2. `position_sizer.py:39-49` `_get_max_risk_usd()` — 重复调用 `adaptive_risk_usd`
  3. `auto_card.py:125-162` `_adaptive_risk()` — 再次调用 `adaptive_risk_usd()` 并叠加连亏/硬上限，**参数 `atr_pct` 重新估算，不一致**
- **修复**：`position_sizer.py` 删去本地 `daily_loss` 读取，委托 `decision_gate` 产出的 `risk_usd/risk_pct`

### 3. HALDRO Valid Code 硬门化
- **现状**：`decision_loop.py:126-141` 已实现 0/1/2 逻辑，**需接入主流程**
- `auto_card.py:337-339` `_tv_cache_indicators_to_studies()` 反向映射存回 study，**未消费**
- `auto_card.py:489-492, 500-503` `_dual_indicator_verdict()` 读取 `sub_haldro_valid_code`/`sub_haldro_risk_code`，**仅用于 risk_text 文案，未把 0/1/2 作为硬门**

---

## P1 — 高优先级（能力声明未落地）

### 4. 体制分类统一阈值
- **三处硬编码 ADX≥25、EMA斜率>0.05%**：
  - `regime_classifier.py:51-174` — 仅卡片展示
  - `regime_backtest.py:93-109` — 仅回测分栏
  - `decision_regime.py:55` — 仅决策闭环内部
- **修复**：新建 `regime_thresholds.py` 共享常量，三处 import 复用
- `signal_validators.py:90-113` `tf_alignment()` 新增返回 `regime_label: "trend"|"range"` 供 `decision_gate` 消费

### 5. 模型路由接入主流程
- `model_router.py:17-56` `select_primary_model()` 仅在 `_resolve_card_final_verdict()` 调用
- 主流程 `auto_card.py:65-69` `_best_fixed_model()` 仍用硬编码 6 个固定模型
- **修复**：`build_setup_metadata()` 内引入 `model_router.select_primary_model()`

### 6. FVG/OB 质量分进入评分闸门
- `decision_loop.py:151-153` 已有 `zone_quality` 闸门（`<55 → WAIT`）
- `auto_card.py:636-637` `_build_tv_main_data()` 存入 `main["mcp_fvg_quality_code"]` 等，**仅透传 render，无评分消费逻辑**
- `tv_data_bridge.py:326-328` 读取 `mcp_fvg_quality_code`/`mcp_fvg_quality_score`/`mcp_ob_quality_score` 存 cache
- **修复**：主流程消费 `zone_quality` 闸门

---

## P2 — 中优先级（补全闭环）

### 7. 影子校准默认开启
- `_shadow_enabled = True` 默认，写入 `data/shadow/decision_signals.jsonl`
- 当前仅在 `_resolve_card_final_verdict()` 条件写入

### 8. Walk-Forward/三重障碍接入定时任务
- `scripts/walk_forward.py`、`scripts/triple_barrier.py` 仅 CLI 可用
- 需 cron/守护进程定期跑批

---

## 关键文件行号速查表

| 文件 | 关键函数/行号 | 问题 |
|------|---------------|------|
| `auto_card.py` | 71-90 `build_setup_metadata()` | 本地风险计算，未用 FinalVerdict |
| `auto_card.py` | 125-162 `_adaptive_risk()` | 重复风控逻辑，参数不一 |
| `auto_card.py` | 470-626 `_dual_indicator_verdict()` | 仅文案降级，未覆盖最终字段 |
| `auto_card.py` | 660-672 `_apply_tv_dmi_override()` | 与双指标裁决分离 |
| `auto_card.py` | 703-862 `_resolve_card_final_verdict()` | **完整决策链但未被主流程调用** |
| `risk_constitution.py` | 660-702 `combined_risk_check()` | 设计为唯一出口，**无调用方真正用作最终出口** |
| `position_sizer.py` | 39-49 `_get_max_risk_usd()` | 重复调用 `adaptive_risk_usd` |
| `position_sizer.py` | 52-154 `position_size()` | 本地读 `risk_state.json` 计算 remaining_daily |
| `decision_loop.py` | 89-233 `resolve_final_verdict()` | **已实现单一真相，需接入主流程** |
| `model_router.py` | 17-56 `select_primary_model()` | 仅在 `_resolve_card_final_verdict()` 调用 |
| `shadow_calibration.py` | 27-138 | 仅在 `_resolve_card_final_verdict()` 写入 |
| `regime_classifier.py` | 51-174 `classify_regime()` | 仅卡片展示 |
| `regime_backtest.py` | 93-109 `classify_regime()` | 仅回测分栏，阈值重复 |

---

## 修复路径（按 `audit_decision_chain_patch.md` 第 6 节）

1. **新建 `scripts/decision_gate.py`** + `scripts/regime_thresholds.py`（共享常量）
2. **写 16 个失败测试**（`tests/test_decision_gate.py`）
3. **实现 `decide()` 核心流程**（按伪代码顺序）
4. **实现三个 `to_*()` 适配器**（对照现有返回结构逐字段映射）
5. **在 `auto_card.py` 顶部加开关**，`build_setup_metadata` 改为调用适配器
6. **在 `position_sizer.py`、`signal_confluence.py` 同理接入适配器**
7. **跑全量测试**（现有 `test_render_tv_card.py`、`test_card_render_locked.py` 等必须全绿）
8. **删除 `_legacy_*` 兜底代码**（验收通过后）

---

## 验收标准（来自 patch 设计）

- [ ] 16 个测试全部绿灯
- [ ] 现有 `auto_card.py BTCUSDT` 终端输出逐行对比 **无差异**（除决策字段来源变为 `decision_gate`）
- [ ] `signal_confluence.py` 推送报文结构不变
- [ ] `position_sizer.py` CLI demo 输出格式不变
- [ ] `risk_constitution.combined_risk_check` 成为**全代码库唯一**风险金额计算出口（grep `adaptive_risk_usd` 调用处仅剩 `decision_gate` 与 `combined_risk_check` 内部）
- [ ] `regime_classifier` 与 `regime_backtest` 共享 `regime_thresholds.ADX_TREND=25`、`EMA_SLOPE_PCT=0.05` 常量