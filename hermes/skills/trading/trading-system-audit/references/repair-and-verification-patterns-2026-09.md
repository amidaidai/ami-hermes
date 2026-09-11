# 棠溪系统修复与验收模式（2026-09）

这份参考记录的是可迁移的修复方法，不是某次机器的故障清单。

## 1. 证据分层：不要把退出码当质量

生产采集器必须把以下结果分开：

- **进程结果**：退出码、超时、异常。
- **身份结果**：symbol/ticker 是否与请求一致，不能接受空身份或共享缓存的旧身份。
- **时间结果**：根时间戳、文件 mtime；`fresh=true` 只能作为生产者提示，不能覆盖重新计算的年龄。
- **内容结果**：必需字段、语义行动格、报价、结构位、来源覆盖是否完整。
- **决策结果**：FinalVerdict 是否真的消费了上面各层，而不是只在卡片里展示。

推荐的缓存验收顺序：

```text
读取 → 解析 → 校验身份 → 重新计算年龄 → 校验必需字段 → 写入 usable
```

任何一层失败都应写出 `fresh=false / stale=true / usable=false` 或明确 unknown，并让执行闸门 WAIT/NO-GO。若为了兼容旧调用保留退出码 0，必须另外提供 strict-exit 模式并让生产 Cron 使用它；不能用“退出码0”表示同步成功。

## 2. 共享缓存必须做品种隔离

`source_snapshot.json`、`tv_live.json` 等通用文件会被不同资产依次覆盖。它们只能作为兼容缓存，不能直接作为某一品种的新鲜证明。

- 优先读取 `source_snapshot_<SYMBOL>.json` / `tv_live_<SYMBOL>.json`。
- 读取通用文件时必须解析 payload 内的 symbol，并与请求 symbol 精确归一化比对。
- 归一化只能去掉交易所前缀和已知永续后缀，不能把空 symbol 当作匹配。
- 新鲜度 watchdog 的候选路径也必须做同样的隔离；只改消费方而保留 watchdog 的共享文件候选，会继续误报健康。

## 3. TV Data Window 内容契约

只返回 Volume/Plot 或只有一个指标值，不等于 SVP 现场完成。生产 TV cache 至少应同时满足：

- 当前图表品种已切换并由 `chart_get_state` 回读确认；
- 请求周期正确；
- SVP 行动格核心语义行存在（结论、方向、路径、风控；项目若使用其它等价字段必须显式映射）；
- 真实报价可解析；
- 结构位/指标值能被消费层解析；
- 加密品种的 AggVol/HALDRO 只作确认，不独立授权；黄金不得套用加密 OI/Funding。

TradingView 常把大数显示成 `4.43 K`、`1.2M`，解析器要处理 Unicode 负号、窄不换行空格、逗号和 K/M/B 后缀。quote CLI 若返回 JSON，必须先解析 `last/close/price`，不能取 JSON 最后一个 token。

## 4. FinalVerdict 闭环

生产顺序必须是：

```text
TV/数据边界 → 主指标语义解析 → 副指标/高级门控 → FinalVerdict → GO/NO-GO/渲染/影子记录
```

硬规则：

- 高级订单流、Meta-Labeling 的否决必须作为 FinalVerdict 输入；展示字段 `gate_verdict` 不能旁路授权。
- `tv_status.usable=false` 必须硬阻断。
- TV payload 非空但没有 freshness/现场验证状态，不能推断为实时可用。
- 加密/黄金完全缺 TV 时必须 fail-closed；非 TV 必需资产可以保留降级，但要明确区分。
- FinalVerdict 缺失时，旧八问不得返回 LEGACY GO；应 NO-GO。
- B/C 只能保留观察方向和条件描述，不产生执行权；NO-GO/WAIT 清空 Entry/Stop/Target 执行字段。
- Pine 行动格含“观望、未收线、等解除、等收线、冲突”等 C 语义时，应在数值兜底前锁定 C 等待，不能被 Side/Grade code 升成 A/B。
- R:R 硬底线在所有等级统一为 1:2；不要给 B 级旧例外。

每一条新增硬闸门都要有一个先红后绿的最小测试，并至少跑一组“明确失败”和一组“字段缺失/unknown”的对照。

## 5. Windows asyncio liveness witness

Windows 原生 asyncio 不提供可用的 `asyncio.start_unix_server` witness。跨平台实现应：

- POSIX：继续使用 PID 后缀 Unix socket；
- Windows：使用只绑定 `127.0.0.1` 的临时 TCP 端口；
- 将端口和 PID 写入 heartbeat；
- 外部 supervisor 在独立线程/进程中探测 loopback TCP，不能在被测 event loop 内同步拨号，否则探针会自己阻塞被测 loop；
- 配置/代码改完后必须重启常驻 Gateway，再验证 heartbeat 与 probe；旧进程的日志不能当新代码已生效。

## 6. MCP 依赖修复

遇到 FastMCP 导入 `request_ctx` 等符号错误时，先看 Hermes 项目 `pyproject.toml` 的精确 pin，再看运行解释器的实际版本。不要只升级一个包：

```bash
python -m pip show fastmcp mcp pydantic pydantic-core
python -m pip check
# 按项目声明恢复精确版本，例如 mcp==1.26.0
hermes mcp test <name>
```

安装可能顺带升级 Hermes 核心依赖；安装后必须按项目 pin 恢复并再次 `pip check`。现有 Gateway 不会自动加载新环境，必须在获准后重启，再验证常驻进程实际状态。

## 7. 外部副作用默认拒绝

交易辅助系统的默认路径是人工决策，不是自动执行：

- Binance `create_order/cancel_order` 在签名/网络前默认只读阻断；若未来开放，至少需要进程级显式开关 + 每次人工确认 + 参数校验。
- 自动 Telegram 外发使用独立显式开关；统一 RichMarkdown 出口也要有默认关闭语义。
- 旧维护脚本中的远端删除、强推、token 读取应在读取凭据前设置显式授权闸门。
- 不自动 flush 失败消息队列；队列目标、parse mode、限流和线程失败都要人工复核。
- 任何涉及服务重启、关键位批准、模型切换、队列补发的操作都要单独确认并读回外部状态。

## 8. 验收矩阵

修复后至少记录：

1. 针对性回归先红后绿；
2. 项目全套测试；
3. live Python 编译；
4. MCP/Node 语法与连接测试；
5. 真实无推送 quick/full 管线；
6. TV 当前 symbol、周期、主副行动格、截图视觉复核；
7. Cron 的实际脚本、解释器、模型、状态和输出质量；
8. 写接口拒绝探针（确认没有网络调用）；
9. Git 状态，确认没有 reset/commit/push 或覆盖用户既有工作树。

最终报告分开写：已修复且验证、已修但未重启、仍阻断、待人工批准、环境/依赖债务。