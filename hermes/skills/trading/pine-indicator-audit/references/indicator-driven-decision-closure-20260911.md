# 指标驱动决策闭环（2026-09-11）

适用于以 Pine 主/副指标为核心的系统审计、策略接入和分析流程设计。不是某一版源码的替代，而是跨版本可复用的验收方法。

## 权限边界

- 主指标（SVP）拥有结构、位置、方向候选、路径和执行授权。
- 副指标（AggVol/HALDRO）只能确认、降权或否决，不能把 B/C 升成 A，也不能替主指标生成执行权。
- Python FinalVerdict 负责数据新鲜度、闭柱、体制、风险、R:R 和组合闸门；渲染器只消费 FinalVerdict。
- GO-A 且 executable=true 才能输出执行 Entry/Stop/Target；WAIT 只能输出明确的人工观察候选；NO-GO/X 必须清空全部执行与观察价格。

## 必接机器字段

主指标至少接入并在裁决前消费：

- `MCP Entry Valid Code`：-3 X、-2 几何无效、-1 R:R 不足、0 无方向、1 待确认、2 B/C 观察候选、3 A 候选。
- `MCP NoTrade Reason Code`：位掩码原因；非零必须进入阻断/等待原因，不能被数字等级或文字兜底覆盖。
- `MCP RR Ratio`：A 执行门槛为 >=2.0；1.5–1.99 仅人工观察，不授权执行。
- `MCP Trigger Pack` / `MCP Evidence Pack`：触发年龄、触发新鲜度、位置证据和闭柱状态。

副指标至少接入：

- `HALDRO Valid Code`：无效时不能制造冲突。
- `HALDRO State Pack`：S0 无效、S1 支持多、S2 支持空、S3 冲突、S4 降权。
- `Basic Packed Bus`：主副唯一总线；合同号、OI 缺失哨兵和 CVD 背景必须按合同解码。
- 覆盖率、单所主导、CVD/OI 新鲜度与一致度：决定确认强度，不是独立方向授权。

## 审计顺序

1. 对用户交付的源码做 SHA-256 与行数记录；确认仓库定版文件逐字一致。
2. 从源码重新提取 `plot(title=...)` 和行动格行名，与唯一 Python 契约比对；禁止只相信旧文档。
3. 运行契约对齐守卫；非零即停止接入，不出“看起来正常”的空卡。
4. 追踪生产者→解析器→FinalVerdict→渲染器，确认机器字段在裁决前已消费，而不是只写进卡面元数据。
5. 对 EntryValid、NoTrade、HALDRO S0–S4、R:R、X/WAIT/B/C 做笛卡尔积测试；重点验证 fail-closed 和价格清空。
6. Pine 编译通过后仍需现场 Data Window、行动格、symbol/timeframe 和新截图验收；编译通过不等于上线。

## 可复用验证入口

仓库中的 `scripts/indicator_source_audit.py` 用于源码哈希、DW 字段存在性和契约完整性检查；随后必须运行 `scripts/tv_indicator_alignment_check.py`。数据源或字段缺失时标记 unavailable/degraded/stale_cache，禁止用旧缓存伪装 live。

## 常见错误

- 只读行动格文字，不消费 EntryValid/NoTrade/State Pack，导致数字等级绕过指标硬状态。
- 把 R:R 1.5–1.99 写成“B/C直通”；正确语义是“B/C观察候选·不授权”。
- 用 HALDRO 无效值制造主副冲突，或把 S4 降权误报成 S3 硬冲突。
- 只校验 Pine 源码或只校验 Python 契约，未做双向字段完整性检查。
- 在用户可读分析中优先显示 quick/full 等机器名；面向用户使用中文档位“轻量/标准/完整/监控”，机器名只放内部映射。