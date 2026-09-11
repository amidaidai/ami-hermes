# 双指标 TV Pine → 分析卡 字段映射 v3.0

> 所属：棠溪交易驾驶舱 / `tradingview-indicator-analysis`
> 更新：2026年9月11日（v2.0 记的是 `行列优化` 版；**已被 `空格修正` 取代**）
> 权威来源：两份**定版**指标源码 + `BINANCE:BTCUSDT.P` 实盘读数
> **唯一代码定义源**：`scripts/tv_indicator_contract.py`（改字段先改这里）
> **对齐守卫**：`scripts/tv_indicator_alignment_check.py`（改完指标必跑，退出码 0 才算对齐）

## 0. 当前生产指标（定版）

| 指标 | 上传文件名 | 仓内文件 | sha256[:24] | 行数 | 分工 |
|---|---|---|---:|---:|---|
| 主指标 | `SVP_主指标_空格修正_20260911.pine` | `outputs/pine_20260905/SVP_audit_fixed17_20260910.pine` | `68a34fc32da035880a0b332c` | 3557 | 结构/位置/FVG·OB/VWAP·EMA·CVD/DMI 体制、13 行行动格、**唯一执行授权** |
| 副指标 | `AggVol_副指标_最终版_20260911.pine` | `outputs/pine_20260905/AggVol_audit_fixed14_20260910.pine` | `c4c563ef4a08b77cb0ceb73f` | 966 | 5 所聚合量、4 所 OI、估算 CVD、LSR、基差、6 行行动格、**只确认/降级/否决** |

优先级铁律不变：`X > WAIT > A > B/C`。X/WAIT 清空 Entry/Stop/Target；B/C 价格只进人工候选。

## 1. SVP 执行授权四态（本轮最重要的新增契约）

主指标行动格的「风控」**行标签**是 SVP 唯一的执行授权出口（源码 L3396）：

| 行标签 | 含义 | Python 侧结论 | 价格 |
|---|---|---|---|
| `风控` | 已授权计划（`setupX` 为假且非 S3 冲突） | 仍须 A 级 + 三件套完整 + 几何有效才 **GO-A** | 值来自 **DW 执行导出**（`MCP Entry/Stop/Target Price`）三件套必须同时存在 |
| `风控·观察` | `pendingPlan`：只有观察价 | **WAIT**，未授权 | 观察价只进 `candidate_*`，卡面写「人工候选，未授权」 |
| `风控·未授权` | 副指标 S3 冲突 | **WAIT**（不让副指标覆盖成 NO-GO） | 同上 |
| `禁做·不出价` | `setupX` 结构禁做（是行**值**不是行标签） | **NO-GO**，`svp_authorization` 硬阻断 | 一律不出价 |

铁律：
- 标签一旦出现在载荷里，**任何数字等级都不得把它升级成可执行**（`decision_loop` 的 `svp_authorization` 闸）。
- 键**缺失** = 旧载荷/无电视行动格 → 不加阻断，保持向后兼容。
- `gates["risk"]`：禁做红、观察/未授权黄、授权绿。

## 2. 「风控」行解析

```
风控                            | 入79056.6·止80482.8·1.8A·标76151.9·2.0R
风控·观察                        | 入79056.6·止80482.8·标76151.9
风控·未授权                      | 入…·止…·标…（S3 冲突，未授权）
风控                            | 禁做·不出价            ← setupX：值是禁做短语
```

- 行**标签**用 `risk_row_label(rows)`：反序扫 `RISK_ROW_VARIANTS`，先命中越保守的 → fail-closed。
- 行**值**用 `risk_row_value(rows)`：与标签成对取，不混用。
- 标签与值必须原子消费：`auto_card._build_tv_main_data` 里
  `风控` → 从 DW 三件套取（缺一即 `price_contract_error`，**不回落到表内四舍五入价**）；
  另外三态 → 清空 entry/stop/target **和** `mcp_*_price`。

## 3. 解码契约（读之前必看）

`scripts/tv_indicator_contract.py` 是唯一权威，已提供：

```
decode_basic_bus(pack)     → {contract, valid, state, priceCode, oiDir, oiAgree, oiPct, oi_present, cvdBg}
decode_trigger_pack(pack)  → {triggerCode, age, fresh, signalState}   低位偏移 -3
decode_feed_mode(code)     → {mode, text, usable, aggregated, fallback, single, abnormal}
decode_oi_presence(pack)   → {present, pct, text}   「OI未接 / OI缺失 / 空串=正常」
decode_entry_valid / decode_no_trade / decode_haldro_state
risk_row_label / risk_row_value / ordered_main_rows / ordered_sub_rows
```

| 常量 | 值 | 含义 |
|---|---|---|
| `CONTRACT_CURRENT` | 22003 | 当前合同 |
| `SUPPORTED_CONTRACT_VERSIONS` | (22002, 22003) | 主指标两个都接受 |
| `CONTRACT_NON_CRYPTO` | 22000 | 非加密 → 副不参与 |
| `DW_ALIASES_MAIN/SUB` | — | canonical snake_case → DW 标题 |
| `LEGACY_DW_ALIASES_MAIN/SUB` | — | 只补历史缓存里才有的旧名（canonical 优先） |
| `DEGRADED` | False | True = 契约没导入，卡面必须报「契约缺失」 |

**精度边界**：最大合法总线 `2200342299199994` < 2^53 ✓
**这也是「不能靠上移合同号新增字段」的原因** —— `22003×1e12` 越界，整数精度会崩；
所以 F05 用「0 当哨兵」的零位移方案。

## 4. 分析卡的消费规则

- **面板行按【行标签】取文本**：`位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位`
  —— 行**值**的格式变动不破卡；但**禁止按 `·` 拆值取下标**（结构行段数会变）。
- **唯一 `⭐主推` 行，三种形态**：
  - `⭐主推 多/空` —— 只有 `FinalVerdict` GO-A 且几何有效才出现
  - `⭐主推 等待` —— WAIT；带 `【人工候选，未授权】` 时，价格**只来自 `FinalVerdict.watch_*`**
  - `⭐主推 禁做` —— NO-GO / X
- **候选价三条铁律**（`render_tv_card._candidate_view`）：
  1. 只读 watch 元组，**永不回落**到原始 entry/stop/target；
  2. 元组不全 → 写「候选数据不完整」，不补半个订单；
  3. R:R 由 watch 元组**现算**（`|标-入|/|入-止|`），不信上游 `rr` 字段。
- **未授权时「风控」「路径」两行自动剥价**（`_redact_order_prices`）：去掉 `入/止/标/候选` 数字与 `x.xA / x.xR`；
  磁吸/结构/现位里的价位是**行情事实**，不剥。
- **OI 三态必须分清**：`OI未接`（总线没通）/ `OI缺失`（副说没数据）/ 有值（含真持平 0.00%）。
- **单源降级写作「副单源·仅参考」**，不写「副指标无效」。

## 5. 分析流程（对齐后的执行顺序）

1. `chart_get_state` → 确认品种/周期，**并确认两个 study 都在图上**
2. `capture_screenshot`（full，含右侧价格轴 + 底部 CVD）→ 首行放核验截图
3. `data_get_study_values` → 主指标 DW（MCP 系列 + 执行/触发/体制/合同包）
4. **解码**：`decode_basic_bus` / `decode_trigger_pack` / `decode_feed_mode` / `decode_oi_presence`
   —— 不自己拆位
5. `data_get_pine_tables` → 主 13 行 + 副 6 行，按行标签取值
6. `data_get_pine_lines` → DO/EMA/POC/VAH/VAL/W·M VWAP/nPOC 价位
7. `risk_row_label` → 判授权四态；只有 `风控` 才读 DW 三件套
8. 多源交叉（Binance 衍生品 / CoinGecko / X·Grok 情绪）—— 只做催化剂与盲点，**不改裁决**
9. `resolve_final_verdict(...)` → 唯一裁决；出卡 `render_tv_card.py`
10. 外部源失败**不阻塞**主流程，但状态必须可见（live/cache/stale_cache/unavailable/quota_cooldown）

**验收口径**：主副两行的 S-code 必须一致（`副S0未接` / `副S4降权` / `副S3冲突` …）。
不一致 = 总线没接或合同不匹配，先解决再出卡。

## 6. 变更纪律（防止再次三处漂移）

- 指标改字段 → **先改 `tv_indicator_contract.py`**，再改消费方；**禁止**在消费方另写白名单。
  历史事故：`auto_card` 曾同时维护三份 DW 映射（缓存反查一份、主数据一份、桥接一份），
  结果主指标 13 行只有 4 行能吃到。
- 改完必跑：`python scripts/tv_indicator_alignment_check.py`（退出码 0）。
  判定规则不靠手写白名单：`display.data_window` / `display.price_scale` 的 plot 必须在契约里；
  纯视觉 plot（柱状/模式切换）不算漂移。
- 回归测试：`tests/test_indicator_alignment_20260911.py`（源码改动未同步契约 → 立刻红）。

## 7. 本轮验收

- `python -m pytest tests/ -q` → **751 passed**（新增 8 项指标契约/候选价回归）
- `python scripts/tv_indicator_alignment_check.py` → **退出码 0**
  主 35/35 字段、副 27/27 字段、主 13 行、副 6 行、行序一致
- 端到端实跑（真实 TV 数据，`outputs/pine_20260905/e2e_card_20260911.py`）：
  `风控` 行无 DW 三件套 → `price_contract_error=SVP执行三件套缺失`，卡面不出价；
  `Basic Packed Bus` 解码 S4 与副指标「信号」行 S4 一致
- 两份指标云编译 **0 错 0 警**；绘图槽 主 41(≈45/64) / 副 59(≈63/64)
- 主指标 CE10117 推算 99,865 / 100,256
