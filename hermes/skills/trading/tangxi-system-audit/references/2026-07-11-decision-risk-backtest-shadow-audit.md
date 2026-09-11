# 2026-07-11 只读审计：决策、风控、回测、影子校准架构一致性

## 审计范围
对 `decision_loop.py`、`risk_constitution.py`、`backtest_runner_v2.py`、`shadow_calibration.py`、`model_router.py`、`decision_regime.py`、`go_nogo_gate.py`、`auto_card.py`、`position_sizer.py` 的架构一致性进行只读静态审计。

---

## 核心发现：四大架构不一致

| # | 不一致点 | 现状 | 影响 | 优先级 |
|---|---------|------|------|--------|
| 1 | **FinalVerdict 非唯一真相** | `go_nogo_gate.py` 有独立裁决逻辑（门1-8），`auto_card.py` 既调用 `resolve_final_verdict()` 又追加 `check_gate()` | 双裁决路径可能冲突：`FinalVerdict=WAIT` 但 `go_nogo_gate` 绿灯 6/8 仍判 GO | P0 |
| 2 | **风控口径三处不一** | `risk_constitution.py:combined_risk_check()` 声称唯一出口，但 `position_sizer.py:72-85` 读 `risk_state.json` 算 `remaining_daily`；`auto_card.py:125-162` `_adaptive_risk()` 再调 `adaptive_risk_usd()` 叠加连亏/硬上限 | 同一 `engine_data` 三路算出的 `risk_usd` 可能差异 >50% | P0 |
| 3 | **回测/实盘决策路径分叉** | `backtest_runner_v2.py:72-78` 复用 `resolve_final_verdict()` ✅，但 `auto_card._resolve_card_final_verdict()` 内部维护一套平行裁决逻辑 | 影子记录回测结果 ≠ 实盘同快照产出 | P0 |
| 4 | **影子校准样本门控泄露** | `shadow_calibration.py:129-137` 样本不足仍返回 `reliable: False` 记录，`model_router.py:37-40` 仅检查 `cal.get("reliable")` 但未强制忽略 `calibrated_win_rate` | 不可靠校准概率可能进入路由评分，污染模型选择 | P1 |

---

## 详细证据链

### 1. FinalVerdict 双裁决路径
```python
# go_nogo_gate.py:66-250 — 独立八门裁决
def check_gate(symbol, engine_data, meta) -> dict:
    # 门1-8 各自硬编码红/黄/绿灯逻辑
    # 第213-221行：若 FinalVerdict 非 executable 则强制 go=False
    # 但门1-7 的红灯逻辑与 decision_loop.py 110-170 重叠且不完全一致

# decision_loop.py:89-233 — 统一裁决
def resolve_final_verdict(symbol, main, dual, regime, risk) -> FinalVerdict:
    # 硬闸门：data/background/regime/dual_indicator/risk_constitution/rr_ratio
    # 等待闸门：location/trigger/zone_quality/no_direction
    # 最终 state ∈ {GO-A, GO-B, WAIT, NO-GO}
```

**冲突示例**：`valid_code=1` (HALDRO 回退) + `conflict=True` → `decision_loop` 判 `WAIT`（`haldro_fallback_conflict`），但 `go_nogo_gate` 门7 仅看 `hard_conflict`，`valid_code=1` 时给黄灯不红灯，可能仍判 GO。

### 2. 风控三口径
| 模块 | 调用链 | 关键差异 |
|------|--------|----------|
| `risk_constitution.py:660-702` | `combined_risk_check(account_balance, atr_pct, current_drawdown_pct)` | 组合：回撤降级分母 × 波动率自适应分子 → 硬上限 |
| `position_sizer.py:39-49` | `_get_max_risk_usd()` → `adaptive_risk_usd(account_balance, atr_pct)` | 单独读 `risk_state.json` 算 `remaining_daily`，**未用回撤降级** |
| `auto_card.py:125-162` | `_adaptive_risk()` → `adaptive_risk_usd()` → 连亏≥3 打半、≥5 归零、余额膨胀上限 1%、铁律 10U | **叠加了连亏守卫**，但未用 `combined_risk_check` 的回撤层级 |

### 3. 回测 vs 实盘裁决分叉
```python
# backtest_runner_v2.py:72-78 — 正确复用
final = resolve_final_verdict(symbol, main, dual, regime=_regime(regime_raw), risk=risk)

# auto_card.py:674-820 — _resolve_card_final_verdict 内部平行逻辑
# - 单独算 regime（707-718）
# - 单独算 dual_indicator_verdict（472-610）
# - 单独投影 final_verdict（1323-1370）
# - 再追加 go_nogo_gate.check_gate()（3940-3950）
```
**结果**：同一 `engine_data` 快照，回测复现的 `FinalVerdict.state` 与实盘 `auto_card` 产出的可能不同。

### 4. 影子校准不可靠样本泄露
```python
# shadow_calibration.py:124-138
result[key] = {
    "samples": len(hits),
    "decisive_samples": decisive,
    "wins": wins,
    "losses": losses,
    "calibrated_win_rate": calibrated,  # None if len(hits) < min_samples
    "reliable": len(hits) >= min_samples,  # 仅标记，不阻断
}

# model_router.py:37-40
cal = calibration.get(f"{regime.code}|{model_id}") or {}
if cal.get("reliable") and cal.get("calibrated_win_rate") is not None:
    score_components["calibration"] = float(cal["calibrated_win_rate"]) * 10.0
# 但 cal["calibrated_win_rate"] 可能为 None，cal.get("reliable") 为 False 时不进分支
# 风险：若 future 代码改为 cal.get("calibrated_win_rate", 0) 会把 None 当 0 进分
```

---

## 测试覆盖缺口

| 缺口 | 建议测试 | 关联文件 |
|------|----------|----------|
| FinalVerdict 唯一真源 | `test_final_verdict_single_source()`：所有渲染/告警/执行层仅消费 `engine_data["_final_verdict"]` | `tests/test_decision_loop_vnext.py:88-95` 已有雏形 |
| HALDRO Valid Code 硬门边界矩阵 | 4×4 决策表：`valid_code ∈ {0,1,2}` × `conflict ∈ {T,F}` → `GO-A/GO-B/WAIT/NO-GO` | `tests/test_dual_indicator_gate.py:148-150` 需补齐 |
| WAIT vs NO-GO 复盘区分 | 回测 `state_stats` 区分 `WAIT`（可复盘触发/质量）与 `NO-GO`（硬违规） | `backtest_runner_v2.py:100-106` 仅计数 |
| 风控口径一致性集成测试 | 同一 `engine_data` 三路输出 `risk_usd` 必须一致（容差 ≤0.01） | 新增 `tests/test_risk_constitution_single_exit.py` |
| 回测=实盘决策路径 | `replay_shadow_records()` 与 `_resolve_card_final_verdict()` 对同一快照产出逐字段相等 | 新增 `tests/test_backtest_live_parity.py` |
| Shadow calibration 样本门控 | `calibrate_groups()` `reliable=False` 时 `model_router` 必须忽略 `calibration` 分量 | `tests/test_model_router_vnext.py:10` 需扩展 |

---

## 建议修复优先级

| 优先级 | 动作 | 验收标准 |
|--------|------|----------|
| **P0** | 统一 FinalVerdict 为唯一真源：删除 `go_nogo_gate.check_gate()` 独立裁决，改为只读 `FinalVerdict` 渲染闸门报告 | `auto_card.py` 直接投影 `engine_data["_final_verdict"]`；`go_nogo_gate.py` 仅 `gate_report_card(final_verdict)` |
| **P0** | 风控口径合一：`position_sizer.py`、`auto_card._adaptive_risk()` 删本地逻辑，仅调用 `risk_constitution.combined_risk_check()` | 三路 `risk_usd` 差异 ≤0.01 |
| **P0** | HALDRO Valid Code 硬门对齐：`go_nogo_gate.py` 门7 与 `decision_loop.py:125-141` 逻辑一致 | `valid_code=1 + conflict` → 红灯/WAIT |
| **P1** | 回测/实盘共用裁决：`auto_card._resolve_card_final_verdict()` 内部直接复用 `resolve_final_verdict()` | 影子记录回测 `state/executable/risk_usd` 与实盘逐字段相等 |
| **P1** | 清理 `risk_constitution_v2.py` 或完成迁移，确保全库仅一个 `combined_risk_check()` 出口 | `grep -r "adaptive_risk_usd" scripts/` 仅剩 `decision_gate` 与内部 |
| **P2** | 补齐上述 6 个测试缺口，纳入 CI 阻断合并 | `pytest tests/test_*.py` 全绿 |

---

## 关键文件映射

```
scripts/
├── decision_loop.py           # 统一裁决 resolve_final_verdict() → FinalVerdict
├── decision_regime.py         # 体制分类 classify_decision_regime() → DecisionRegime
├── risk_constitution.py       # 风控宪法 combined_risk_check() 唯一出口（声称）
├── go_nogo_gate.py            # 独立八门裁决（冲突源）
├── backtest_runner_v2.py      # 影子回测复用 resolve_final_verdict() ✅
├── shadow_calibration.py      # 影子记录/标注/分组校准
├── shadow_outcome_labeler.py  # 零Token结果标注器
├── model_router.py            # 体制→模型路由（消费校准）
├── auto_card.py               # 主管线：平行裁决 + 追加 go_nogo_gate
└── position_sizer.py          # 仓位计算：独立风控口径

tests/
├── test_decision_loop_vnext.py       # FinalVerdict 行为测试
├── test_dual_indicator_gate.py       # HALDRO 闸门测试
├── test_backtest_runner_v2.py        # 回测复现测试
├── test_model_router_vnext.py        # 模型路由测试
└── test_auto_card_final_verdict.py   # auto_card 裁决投影测试
```

---

## 审计元数据

- **审计日期**：2026-07-11
- **审计类型**：只读架构一致性审计（静态代码分析 + 测试覆盖映射）
- **触发指令**：用户 "只读审计决策、风控、回测和影子校准架构一致性"
- **工具链**：`search_files` + `read_file` + 交叉引用验证
- **产出**：本参考文档 + 会话中结构化汇报