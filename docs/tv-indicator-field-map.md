# 双指标 TV Pine → 分析卡 字段映射 v2.0

> 所属：棠溪交易驾驶舱 / `tradingview-indicator-analysis`
> 更新：2026年9月11日（上一版 v1.3 = 2026-09-10，记录的是 v13 指标，**已失效**）
> 权威来源：两份**定版**指标源码 + 2026-09-11 `BINANCE:BTCUSDT.P` 实盘读数
> **唯一代码定义源**：`scripts/tv_indicator_contract.py`（改字段先改这里）

## 0. 当前生产指标（定版）

| 指标 | Pine 文件 | sha256[:24] | 行数 | 分工 |
|---|---|---:|---:|---|
| 主指标 | `SVP_主指标_行列优化_20260911.pine` | `84094d3228ff26d06fc592fe` | 3557 | 结构、位置、FVG/OB、VWAP/EMA/CVD、DMI 体制、13 行行动格、**唯一执行授权** |
| 副指标 | `AggVol_副指标_最终版_20260911.pine` | `c4c563ef4a08b77cb0ceb73f` | 966 | 5 所聚合成交、4 所 OI、估计 CVD、LSR、基差、6 行行动格、**只确认/降级/否决** |

优先级铁律不变：`X > WAIT > A > B/C`。X/WAIT 清空 Entry/Stop/Target；B/C 价格只进人工候选字段。

## 1. v13 → v16/v15 的实质变化（卡/流程必须跟着改的部分）

| 项 | v13 行为 | v16/v15 现在 | 对卡与流程的影响 |
|---|---|---|---|
| **合同号** | 22002 | **22003**（22002 向后兼容） | 主指标两个都接受；只换副不换主 → 主显示「副合同不匹配」，**fail-closed** |
| **OI 缺失** | 全缺编码成 `0` → 显示「持平 0.00%」 | `oiPctEnc == 0` 作显式哨兵；主 `oiWired` 要求 `oiPresentInBus` | **卡面不再把「没数据」写成「持平」** |
| **Coverage Feed Mode** | 1聚合/2回退/4异常（Single 也落 4） | **四态**：1聚合/2回退/**3单源不参与协同**/4异常 | 卡（`haldro_quality`）在非聚合态追加「· 数据源X」；单源不再报「异常」 |
| **Trigger Pack 低位** | `signalState+1`，X 态为 −1 → 借位 | `signalState+3`（域 1..7，恒非负） | 解码必须 `-3`（`decode_trigger_pack`） |
| **A 级执行门槛** | 不含 CVD 冲突 | **纳入 `cvdConflict`** | 面板说「等CVD」时，MCP 执行价**必须为空**；A 会变少 |
| **HTF FVG/OB** | 返回值多套一层 `[1]` | 去掉外层偏移 | 区域**提前一根高周期柱**出现（日线早一天、4h 早 4 小时） |
| **触发选择** | 先按优先级选、再看新鲜度 | **先按新鲜度过滤**再按优先级 | 路径行可能换成更新的那个触发 |
| **扫线事件** | 被「隐藏已扫线」吃掉 | 事件判定不看视觉隐藏 | H1+ 开启隐藏时，结构/MSS/评分会变化 |
| **稳定位** | 只在破位/走远/更优时更新 | 增加 **48h 年龄上限** | 超龄退役到「前位」，不再冒充活跃位 |
| **OB 回踩资格** | `bar_index > bornBar`（来源柱） | `bar_index > confirmBar`（确认柱） | 新建 OB 当根不再算「已回踩」 |
| **信号持续** | 无计划时只累加不复位 | 无计划即复位 | 多→无→无→多 不再算「持续 3 根」 |
| **SMT** | 对照只请求 close | 对照请求 OHLC，两侧同用 high/low | 影线创高但收盘回落不再漏判 |
| **执行价格式** | `"#.####"`（丢前导零、低价截 0） | `f_fmt_exec` 按 `format.mintick` | **入场/止损/目标是可直接下单的值** |
| **结构行** | `…·守摆高·收缩·等放量·未扫N/M` | 结构文本已含同状态词时省略 regime 段 | 行更短；原版语义保留 |
| **磁吸行** | `↑周四 纽 高 …·分74·100%(30/30)` | `周四纽高 …·分74·40%`（满窗不标样本量） | 去掉与行标签重复的箭头；未满窗才标 `(n/30)` |
| **副指标文案** | `扫N`（实为未扫）、`⚠主导`、`·OI` | `未扫N/M`、`⚠永续主导`、`·OI最弱` | 语义纠正 |
| **Single 模式请求** | 单源仍发 20 个 request | 补 `datatype=='Aggregated'` 门控 | 单源不再空烧配额 |

## 2. 解码契约（读之前必看）

`scripts/tv_indicator_contract.py` 是唯一权威，已提供：

```
decode_basic_bus(pack)     → {contract, valid, state, priceCode, oiDir, oiAgree, oiPct, oi_present, cvdBg}
decode_trigger_pack(pack)  → {triggerCode, age, fresh, signalState}   状态偏移 -3
decode_feed_mode(code)     → {mode, text, usable, aggregated, fallback, single, abnormal}
decode_oi_presence(pack)   → {present, pct, text}   「OI未接 / OI缺失 / 空串=正常」
decode_entry_valid / decode_no_trade / decode_haldro_state
```

| 常量 | 值 | 含义 |
|---|---|---|
| `CONTRACT_CURRENT` | 22003 | 当前合同 |
| `SUPPORTED_CONTRACT_VERSIONS` | (22002, 22003) | 主指标两个都接受 |
| `CONTRACT_NON_CRYPTO` | 22000 | 非加密 → 副不参与 |

**精度边界**：最大合法总线 `2200342299199994` < 2^53 ✓
**这也是「不能靠上移合同号新增字段」的原因** —— `22003×1e12` 越界，整数精度会崩；
所以 F05 用「0 当哨兵」的零位移方案。

## 3. 分析卡的消费规则

- **面板行按【行标签】取文本**：`位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位`
  —— 行**值**的格式变动（去掉箭头、regime 段省略、样本量条件显示）**不破卡**；
  但**禁止按 `·` 拆值取下标**（结构行段数会变）。
- **「风控」行标签是动态四态**：`风控` / `风控·观察` / `风控·未授权` / `禁做·不出价`。
  只认字面「风控」会在观察态漏读执行价。
- **执行价只在「风控·观察」及以上存在**（`panelPlanVisible`）；X/WAIT 恒为 `止—`。
- **OI 三态必须分清**：`OI未接`（总线没通）/ `OI缺失`（副说没数据）/ 有值（含真持平 0.00%）。
- **单源降级写作「副单源·仅参考」**，不写「副指标无效」。

## 4. 分析流程（对齐后的执行顺序）

1. `chart_get_state` → 确认品种/周期，**并确认两个 study 都在图上**
2. `capture_screenshot`（full，含右侧价格轴 + 底部 CVD）→ 首行放核验截图
3. `data_get_study_values` → 主指标 DW（MCP 系列 + 执行/触发/体制/合同包）
4. **解码**：`decode_basic_bus` / `decode_trigger_pack` / `decode_feed_mode` / `decode_oi_presence`
   —— 不自己拆位
5. `data_get_pine_tables` → 主 13 行 + 副 6 行，按行标签取值
6. `data_get_pine_lines` → DO/EMA/POC/VAH/VAL/W·M VWAP/nPOC 价位
7. 多源交叉（Binance 衍生品 / CoinGecko / X·Grok 情绪）—— 只做催化剂与盲点，**不改裁决**
8. 出卡：`render_tv_card.py`；唯一 `⭐主推`，`🔁备选` 只是失效路径
9. 外部源失败**不阻塞**主流程，但状态必须可见（live/cache/stale_cache/unavailable/quota_cooldown）

**验收口径**：主副两行的 S-code 必须一致（`副S0未接` / `副S4降权` / `副S3冲突` …）。
不一致 = 总线没接或合同不匹配，先解决再出卡。

## 5. 本轮验收

- `python -m pytest tests/ -q` → **702 passed**
- 契约 DW 清单 vs 指标源码 plot 标题 → 主指标全对齐；副指标仅多一个视觉标记（非 DW 字段）
- 两个指标云编译 **0 错 0 警**；绘图槽 主 41(≈45/64) / 副 59(≈63/64)
- 主指标 CE10117 推算 99,865 / 100,256
