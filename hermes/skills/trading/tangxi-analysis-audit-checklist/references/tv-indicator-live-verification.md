# TV 指标实盘版本读回验收法（2026-09-13 首用实证）

## 目的
回答「TV 上实际部署的指标是哪个版本」——**源码守卫 ≠ 部署验证**。定版源码在仓库、TV 云端编译过、图表挂载的版本可能各不相同；唯一实证 = 从图上**读回面板行**与定版特征串对照。

## 方法（只读，不动编辑器）
1. `tv_health_check` → 确认 cdp_connected + chart_symbol（读面板不需要改图）。
2. `data_get_pine_tables` **不带 study_filter** 读全部指标表。
   - 陷阱：filter 实测会漏——“SVP” 对面板名 `SVP+ICT+VWAP+CVD` 返回 0 命中；先无 filter 读全部再按 name 定位。
3. 对照「版本特征签名表」逐行判定。

## 版本特征签名表（2026-09-13 核验结论：实盘 = SVP fixed17 / AggVol fixed14）
| 面板/行 | 读到的特征串 | 归属 |
|---|---|---|
| SVP CVD 行 | `…·子5·基差-0.05%` | F04 子周期标注 + P2-1 基差接回 |
| SVP 前位行 | `周六低 …·被替代·仍撑·↑1.8A·14:00定` | P2-4 角色判定 + 方向箭头 |
| SVP 协同行 | `副S4降权·高周多`（仅副状态+高周） | 行精简版式 |
| AggVol 流向行 | `…单所1m·本锚近10K卖·滚动同向·前锚逆⚠` | fixed14 滚动/前锚语义 + P1-4 样本预热 |
| AggVol 信号行 | `🔴 S4降权·共振2/4·高周逆` | F18 分歧降级 |

## 铁律
- 引用历史审计报告的「待办/未修」项前，**先核对最新源码修复注释 + 实盘面板**：9-10 报告 = 修复前快照，其 P1-7 在 fixed17 已闭环（`cvdBgTag「·副滚动逆」` 已拼进 CVD 行，不是协同行）。旧报告只能当历史证据，不能当现行缺口。
- 数据管道断点诊断用「全链 probe」：`缓存 → _tv_cache_indicators_to_studies → _parse_tv_study_values → _build_tv_main_data` 逐层打印字段是否存在（本轮 DO Price 案例：全链 probe 全通，真断点在渲染层双层截断）——比静态推理快一个数量级。
- 位表容量链：`_prepare_levels` 截 7 / `_structure_table` 原截 6（已对齐 7）——**双层截断会静默吞第 7 位**；新字段接入位表前先查这两处容量。

## DO Price 接入终案（commit b91a773，供未来字段接入参考）
- 落点 = 「VWAP/EMA/DO」环境行：`_ema_disclosure_line(vwap_ema, do_price=…, price=…)`，动态前缀（同时有=VWAP/EMA/DO；仅 DO=DO；无 DO=VWAP/EMA）。
- DO 是定价参考而非结构位 → 不进②表排序竞争（此前尝试进位表被 [:7] 截，且会挤结构位）。
- 数据链：`engine_data["_tv_main"]["do_price"]` → auto_card 算 `_do_price_v` → `render_v96_card(do_price=…)`。
- 实测产物：`VWAP/EMA/DO：VWAP \`77,171\`（价在下·2σ外） · EMA9/55 \`76,903\`/\`77,145\` · 强趋势·空头排列 · DO \`77,243\`（+0.66%）`。
