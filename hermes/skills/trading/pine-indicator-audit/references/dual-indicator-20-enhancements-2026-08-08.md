# 双指标 20 条决策向增强/强化路线图

**生成时间**：2026 年 8 月 8 日 11:20（BJT）  
**触发**：用户要求"全方位、多维度、联网社区全面查审计两个指标，给 10 个优化建议和推荐增强的地方。不要回测不要复盘。是指标本身的。"  
**来源**：TradingView Pine v6 官方 2026-01 `request.footprint()` / dynamic requests、LuxAlgo/TradersPost/Reddit/YouTube/Instagram 社区 ICT/SMC 最佳实践、Bookmap/ATAS 订单流教学、TradingView 开源 VP/OB/SMC 脚本横向扫描，以及对 `SVP_ICT_v2.pine` / `AggVol_v2.pine` 的静态审计。

---

## 当前基线速览

| 维度 | SVP 主指标 | AggVol 副指标 |
|---|---|---|
| 行数 | 3033 | 655 |
| 字符数 | 199,282 | 49,238 |
| est tokens (字符/2.33) | ~85,529 | ~21,132 |
| `request.security` 调用点 | 9 unique contexts | 8 unique contexts |
| `request.security_lower_tf` | 2 | 0 |
| `plot()` raw | 41 | 40 |
| 估算 worst plot count | 46/64 | 53/64 |
| `alertcondition` | 0（已事件化为 `alert()`） | 0（已事件化为 `alert()`） |
| `calc_bars_count` | 2 | 0 |
| 账号档位假设 | 免费 Basic | 免费 Basic |

---

## A. 决策面板与执行层（6 条）

### A1. 行动格精简为 5 行，结论永远在最上行
当前 9 行信息过密。固定为：
| 行 | 内容 |
|---|---|
| 1 | **结论**：A多/B多/C反多/X禁做 |
| 2 | **路径/风险**：触发条件或 X 原因 |
| 3 | **关键位**：最近支撑 / 阻力 |
| 4 | **止损·目标·仓位** | 5 | **共振/周期** |

### A2. 把 A/B/C/X 翻译成"下单动作语义"
- A = 自动授权（绿色进场框）
- B = 候选等确认（黄色等待框）
- C = 左侧观察（橙色虚线）
- X = 无框，硬性禁止

### A3. "等触发"必须绑定具体价位
例如："等回踩 nPOC 109.2"、"等站上 4h OB 110.5"、"等 London KZ 开盘 30m"。复用 `expectedTriggerPath`。

### A4. 关键位与入场位可视化联动
A/B/C 触发时在当前 K 右侧用 `box.new()` 画 Entry/Stop/Target 区，X 级不画任何操作框。

### A5. 实时仓位%建议
根据 R:R + 等级输出仓位：A+RR≥2.0→100%、A+RR 1.5-2.0→70%、B→40%、C→20%、X→0%。

### A6. 事件化 Alert 升级
拆成 5 类 `alert()`：A 触发、B 升 A、C 形成、X 触发、X 解除。

---

## B. 主副指标协同与冲突裁决（3 条）

### B7. 主副指标冲突裁决表
| 主指标 | 副指标共振 | 裁决 |
|---|---|---|
| A | ≥3/4 | 保持 A |
| A | ≤1/4 | 降 B |
| B | ≥3/4 | 升 A 候选 |
| X | 任意 | X 优先 |

### B8. HTF 冲突给出"能不能反手"
不再只显示"高周冲突"，而是显示：
- `X·高周空·禁追多`
- `X·高周多·禁追空`
- HTF 翻转时自动解除 X

### B9. 双指标 CVD 口径统一
主指标用 lower_tf 子 K 真实方向，副指标用影线/实体估算。建议副指标输出 `HALDRO CVD Method Code`，主指标接收后给不同权重：子 K 汇总权重 1.0，影线估算权重 0.5。

---

## C. 市场结构与 ICT/SMC 层（4 条）

### C10. 升级 liquidity sweep 为"三阶段状态机"
社区高票做法：Arming → Tracking → Confirmed/Rejected。行动格显示：
- `扫位·待确认`
- `扫位·已确认`
- `扫位·失败·重置`

### C11. FVG/OB 质量评分公开到行动格
当前只在 MCP/Data Window。建议在行动格顶部显示 FVG 评分和 OB 评分，如 `FVG-72 OB-55`。

### C12. 增加 KillZone 倒计时与开盘窗口质量
当前 KillZone 已有时段，但缺少倒计时。行动格增加 `LDN KZ 还剩 12m`；KillZone 外降级 B/C 信号为观察。

### C13. nPOC 触碰后终点冻结 + 视觉标记升级
触碰 nPOC 后线终点冻结，并在线终点加一个 `label.new()` 显示"已测试" + 日期，避免回看时误当未测试。

---

## D. 数据质量与性能层（4 条）

### D14. AggVol 非加密品种请求短路
当前 OI/LSR/基差在黄金外汇仍请求。建议 `isCryptoA` 前置门控：非加密只保留 Volume/OBV/MFI/HTF trend，释放 4-6 个 unique request。

### D15. SVP IL token 函数化主执行体
当前估算 ~85,529 tokens，逼近 100,000。把 FVG/OB/LV 维护循环、磁吸扫描、行动格构建包成函数，释放 IL 余量。

### D16. AggVol plot 槽位释放
- 零线 `plot.style_circles` 改 `hline()`（不计 plot count）
- EX 排序的 5 个 series-color plot 在 Exchange Domination 模式下可只画 top3
- 当前最坏 53/64，目标压到 ≤44

### D17. CVD `calc_bars_count` 动态预算
按锚定周期秒数 / LTF 秒数 + 背离长度 + 缓冲动态计算，同时上限 100,000 intrabar（免费档）。秒级/5S 周期诚实降级。

---

## E. 可视化与新数据层（3 条）

### E18. 接入 TradingView 2026 年 1 月 `request.footprint()`
Premium/Ultimate 专属。可以拿到真实 buy/sell volume、POC、VAH、VAL，替代当前的影线估算 CVD。免费档不可用，但可先写好条件编译/门控，账号升级后自动启用。

### E19. 右侧价格轴增加"候选触发价位"
除当前 POC/VAH/VAL/nPOC/VWAP/DO 外，当 A/B 计划形成时，把候选 Entry/Stop/Target 也显示在右侧价格轴，颜色与等级一致。

### E20. 增加周期一致性百分比
在行动格顶部显示：
```
周期共振 D↑4h↑1h↓15m↑5m↑ 60%
```
5 周期同向 100%，每少一个降 20%。低于 40% 时，A 自动降 B。

---

## 落地优先级

| 优先级 | 项 | 影响 |
|---|---|---|
| 本周必做 | A1、A2、A3 | 决策速度提升最大 |
| 本周必做 | D15、D16 | 防止 IL/plot 上限爆炸 |
| 下周做 | A4、A5、A6、B7 | 执行闭环 |
| 月底做 | B8、B9、C10、C11、C12 | 结构与冲突裁决 |
| 看账号 | E18 | Premium/Ultimate 专属 |
| 长期 | E19、E20 | 高级可视化 |

---

## 联网社区关键证据摘要

1. **ICT/SMC 社区 2026 共识（Reddit / YouTube / Instagram）**："HEAT MAP FOOTPRINT CHARTS VOLUME PROFILE AND DEEP TRADES THAT'S IT"、"Orderflow is the only tool in trading that can give you the precision"、"Add market profile/orderflow into ICT/SMC"——社区认为当前最缺的是订单流 footprint/heatmap 与 volume profile 的融合。
2. **TradingView 官方 2026-01**：`request.footprint(ticks_per_row, va_percent, imbalance_percent)` 返回 per-bar footprint，含 buy_volume/sell_volume/delta/POC/VAH/VAL/imbalance；仅限 Premium/Ultimate。
3. **LuxAlgo 2026-07**：MSS vs BOS vs CHoCH 的区分、Displacement 作为 #1 质量过滤器。
4. **TradeAlgo 2026**：TradingView CVD 仍是 bar-level 估算，不能与 Bookmap/Sierra Chart 的 tick-level 真订单流混淆。
5. **TradingIQ OrderFlow IQ / ZynAlgo Footprint Master Pane**：社区已有 footprint-style 脚本，但均为 Premium/Ultimate 或估算实现。
6. ** volatilitybox / VT Markets 2026**：波动率状态机（低/中/高/爆发）是专业交易员 2026 年重点使用的宏观过滤。
7. **TradeVizion 2026-05**：Kelly/Edge/Risk of Ruin 自适应仓位在 TradingView 社区获得高关注。

---

## 与当前双指标审计的关联

- `references/dual-indicator-cockpit-verdict-protocol-2026-07-04.md`：B7-B9 的裁决表应与此协议对齐。
- `references/dual-indicator-execution-state-oi-consensus.md`：A5-A6、B7、D14、D17 需与此状态机兼容。
- `references/svp-v2-static-decision-contract-audit-2026-08-07.md`：A1-A4、A6、C10-C13、E19-E20 需通过决策完整性检查。
- `references/free-tier-pine-optimization-playbook.md`：D15-D18 必须遵守免费档限制。
- `references/pine-ce10295-functionization.md`：D15 的函数化方法。
