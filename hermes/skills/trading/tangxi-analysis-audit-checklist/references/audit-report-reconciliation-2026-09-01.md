# 审计报告与当前运行态复核模板

用于复核用户提交的带时间戳审计报告。目标不是重写原报告，而是区分历史证据、当前复现、已修未提交和未验证项。

## 复核顺序

1. 记录当前时间、实际仓库根目录和 Hermes profile。
2. 读取有效配置路径：`hermes config path`、`hermes config env-path`；不要猜 Roaming/Local 路径。
3. 读取 `git status --short --branch` 和相关文件的 `git diff`，确认报告基于 `HEAD`、工作树还是旧副本。
4. 对每个结论建立证据行：文件/工具、当前行号或返回值、最小可重跑探针、状态标签。
5. 重新运行最小探针，再决定是否升级为 P0/P1；不要只凭报告中的退出码或截图。

## 证据状态表

| 标签 | 含义 | 报告写法 |
|---|---|---|
| `historical` | 报告时间点成立，当前未重跑 | 保留日期，不写成当前状态 |
| `current` | 当前同样复现 | 可进入现行 P0/P1 |
| `fixed-uncommitted` | 当前工作树已修，尚未提交/锁定 | 写修复位置和剩余风险 |
| `not-reproduced` | 当前反例不成立 | 删除旧结论或降为历史项 |
| `unverified` | 缺少可靠探针 | 不得作为硬证据 |

## 裁决门对照探针

对 TV freshness 至少测试两种输入：

- 显式 `{"usable": false}`：期待 `tv_live=red` 且 `go=false`。
- 不提供 freshness 状态但提供非空 TV 数据：如果得到 green，记录为 unknown-status fail-open，而不是宣称所有 stale cache 都会放行。

对高级门控同时检查：

- `resolve_final_verdict()` 是否接收 `advanced`；
- `_advanced` 的赋值是否发生在 FinalVerdict 调用之前；
- GO/NO-GO 函数是否实际读取高级门控，而不是只把原因写进展示字段。

## 不应混淆的对象

- `tv_live_<symbol>.json` 与 `xau_tv_state.json` 分开计算 mtime 和内容质量。
- “现场 MCP 可读”不等于“auto_card 已直接读取现场”；要追踪生产入口是否只读本地缓存。
- “脚本 exit 0”不等于“数据质量通过”；检查 stale、missing、semantic error 和降级标记。
- “全量测试收集失败”与“定向测试回归失败”分别计数。
- 没有 `package-lock.json` 时，根目录 `npm audit` 结果只能写为 ENOLOCK/unverified。

## 最终报告格式

先写一张当前状态表，再写历史差异表：

1. 当前仍阻断生产的项目；
2. 已修但未提交的项目；
3. 原报告中未复现或证据过时的项目；
4. 未验证、不能升级为硬结论的项目；
5. 当前工作树和测试闭环风险。

不要因为报告总体结论正确，就自动接受其中每一条行号、数量和 provider 状态。