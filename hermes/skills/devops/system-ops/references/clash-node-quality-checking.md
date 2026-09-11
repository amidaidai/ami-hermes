# Clash Verge 节点质量检测与清理流程

适用场景：用户想检测 Clash/Clash Verge 节点是否干净、住宅/原生、风险高低，或要求把第三方检测结果显示到 Clash 客户端节点名中。

## 社区结论

- Clash Verge Rev 社区已有“内置节点 IP 纯净度/风险检测”提议，但维护者重点质疑第三方检测服务依赖与隐私风险。
- 社区观点：不建议把 Ping0/IPPure 等第三方检测长期内置到 Clash Verge；检测结果受服务可用性、Cloudflare、节点当时出口、WebRTC/浏览器泄露等影响。
- 更稳妥做法：临时检测、生成报告；不要污染原订阅，不要长期保留打标导入配置，除非用户明确要在客户端展示。

## 推荐检测矩阵

| 维度 | 工具/方式 | 判定 |
|---|---|---|
| 连通性/延迟 | Clash Verge 自带延迟测试 / API delay | 先筛超时、高延迟 |
| 出口 IP | Clash External Controller 切节点后访问检测站 | 确认实际出口，不只读订阅名 |
| 风控/纯净度 | Ping0、IPPure、Scamalytics、IPinfo 等交叉 | 单源不作为最终结论 |
| 类型 | 住宅/机房、原生/广播、ASN/Hosting | 住宅原生优先，机房广播谨慎 |
| 目标站实测 | Google/GitHub/YouTube/ChatGPT/交易所等 | 以实际目标可用为准 |
| 稳定性 | 3 轮以上重复检测 | 单次超时不直接判死刑 |

## 安全工作流

1. 先备份 Clash Verge 配置目录中的关键文件：`verge.yaml`、`clash-verge.yaml`、`profiles.yaml`。
2. 优先生成“节点质量报告”，不导入 Clash 客户端：排名、风险分、IP 类型、目标站结果、建议用/禁用。
3. 只有用户明确要求“像推文那样在客户端显示”时，才生成 `_checked.yaml` 并通过 `clash://install-config?url=...&name=...` 导入。
4. 导入前确认 External Controller 已启用且只监听本地，例如 `127.0.0.1:9097`，secret 与检测工具配置一致。
5. 导入后验证 `profiles.yaml` 是否新增目标 remote 条目；但不要把该配置设为 current，除非用户要求切换。
6. 用户要求“删掉这个”时，不只删本地导出文件；必须同时检查并清理 Clash Verge 的 `profiles.yaml` 以及 `profiles/` 下由导入产生的 merge/script/rules/proxies/groups/remote 文件。

## Clash Verge 常见路径

Windows Clash Verge Rev 配置目录通常是：

```text
C:/Users/Administrator/AppData/Roaming/io.github.clash-verge-rev.clash-verge-rev/
```

关键文件：

```text
verge.yaml                 # UI/应用设置，enable_external_controller 等
clash-verge.yaml           # 当前运行配置，含 proxies/proxy-groups
profiles.yaml              # 客户端订阅/profile 索引
profiles/<uid>.yaml|js     # 每个订阅及其 merge/script/rules/proxies/groups 拆分文件
```

## 重要坑

- `profiles.yaml` 的 `current` 未变不代表导入配置不存在；要全文搜索 `checked`、导入 URL、导入名称。
- Clash Verge 通过深链导入 remote 时，通常会同时生成 1 个 remote + 多个 merge/script/rules/proxies/groups 文件；删除时要按 `option` 里的 uid 链一起清理。
- 检测脚本用 `GLOBAL` 组切节点可能导致部分节点 400；应先通过 Controller `/proxies` 枚举真实代理组，并优先切用户当前主代理组（如 `主代理`）或节点所在组。
- Ping0 可能被 Cloudflare 阻挡；IPPure/Ping0 结果要作为“参考”，不要把失败直接写成节点必坏。
- 若需要保护隐私，避免浏览器 WebRTC 模式；优先走 Clash 本地代理 + 服务端 HTTP 检测，或只输出报告不打开第三方网页。

## 输出建议

默认给用户三类结果：

| 类别 | 标准 |
|---|---|
| 优先用 | 住宅/原生、风险低、目标站正常、延迟稳定 |
| 可日常 | 机房但风险低、共享少、目标站稳定 |
| 禁用/少用 | 风险高、频繁超时、目标站失败、切换失败 |

不要默认把检测结果写回原订阅；原订阅来自远端，后续更新会覆盖本地改名。