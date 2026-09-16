# 双指标审计增量（2026-09-16）：对称修复核对 + 生态增量

对象：SVP fixed17（`68a34fc3…`，3558 行）+ AggVol fixed14（`c4c563ef…`，967 行）。
三方一致已验证：用户上传 == 仓库定版 == TV 云端保存（pine-facade readback 逐字相等）。
本轮产物：`outputs/pine_audit_20260916/`（报告 + 读回 + fixed18 候选 + 验证脚本）。

---

## 1. 对称逻辑修复必须两侧核对（本轮实案，新的审计签名）

F13「稳定位 48h 年龄上限」修复**只接了支撑侧**：
supStale 已进退役条件（`supBroken or supExpired or supImproved or supStale`）与原因码（`supExpired or supStale ? 3 : 2`）；
阻力侧 `resStale` **只声明、零消费** → >48h 且未破/未走远/无更优候选的阻力位永不因超龄退役，F13 缺陷在阻力侧残留。

**审计签名（每次双指标审计必跑）**：列出所有成对量（`sup*/res*`、`Long/Short`、`High/Low`、`Bull/Bear`、
`Above/Below`），两侧的出现次数与消费位置必须对称；「声明后零读取」的一方 = 漏接。
本轮实测：稳定位引擎 4 对量仅 `resStale` 一处漏接，其余（Broken/Expired/Improved/Improved 阈值）均对称。

**修法（fixed18，与支撑侧逐字对称）**：

```pine
// L1894
else if resBroken or resExpired or resImproved or resStale
// L1900
lastWatchReason := resBroken ? 1 : resExpired or resStale ? 3 : 2
```

展示路径已存在：前位行 `lastWatchReason==3 → 「·过期」`（L3470），无需额外改动。
候选验证套件（本轮实测）：云编译 0/0、绘图预算不变（41）、DW/行名/授权态字面量对齐不变、diff 仅 2 逻辑行 + 1 注释。
Δ +80 字符 ≈ +35 token（对 0.4% 余量可接受）。

**教训**：任何「两侧对称」的修复交付前，把两侧代码块**并排 diff 一次**，不要只验被改的一侧。

## 2. 生态增量（2026-08 ~ 09-16）

- Pine 官方 2026-08：`once` 条件结构（块首次执行后不再执行，替代 `var done` 模式）；
  Pine Screener 支持指数源（最多 4,000 符号）+ 完整指标对话框。与本双指标相关性低。
- 2026-09：截至 9/16 无新发布说明（最新=8 月）。
- **重申**：Taker Buy/Sell Ratio 不可实现（TV 无 `taker_buy_volume`，20260812 已回滚）——审计报告勿再列入「必加」。
- TV Desktop 3.4.1（9/13 同步演练通过）。

## 3. 本轮余量快照（修复预算判断用）

| 项 | SVP | AggVol |
|---|---:|---:|
| token 推算 | ≈99,865/100,256（余约 0.4%） | ≈31,045/100,256 |
| 绘图槽（本地估算→TV） | 41 → ≈45/64 | 59 → ≈63/64（最紧） |
| request | ≈6/40 | ≈30/40 |
| TV 六项和 | 237/254 | 91/254 |
| 死变量 | 8（resStale 已修；清单见报告 3.2） | 0 |

**任何新增前先答「从哪扣」**：SVP 靠功能置换，AggVol 靠绘图槽置换。

## 4. 可复用验证命令（本轮实跑）

```bash
# 云端保存读回（只读）
node outputs/pine_audit_20260916/verify_cloud_source_20260916.mjs
# 服务器编译（fresh）
node tools/tradingview-mcp/scripts/tv_pine_check_files.mjs <file.pine>
# 绘图预算
python outputs/pine_20260905/plot_budget_20260910.py <file.pine>
# 契约对齐（定版 pin 在脚本头部；候选文件需手跑 scan_plots/scan_rows 对比）
python scripts/tv_indicator_alignment_check.py
```
