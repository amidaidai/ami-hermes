# x_search 额度阻断时的情绪降级协议（2026-07-03）

## 触发场景
手动完整加密分析中，`x_search` 工具已注册、可描述、可调用，但返回类似：

```text
personal-team-blocked:spending-limit
You have run out of credits or need a Grok subscription
```

这不是平台 toolset 未挂载，也不是网络或 MCP 故障；属于 xAI/Grok 额度或订阅状态阻断。

## 正确处理
1. 不要继续重复调用 `x_search`，避免浪费时间。
2. 在管线审计中把 `x_sent` 标为 `⚠️`，备注写清：`x_search额度阻断·本地x_sent+web替代`。
3. 读取最近本地情绪缓存：`data/x_sentiment.json`（如存在）。
4. 用 `web_search` 补充市场情绪/新闻，但必须标注「web源·非X实时」。
5. 若 CoinGecko trending / Fear & Greed 可用，可作为情绪补充，但不能冒充 X 实时源。
6. 出卡时不要写“X情绪已完成”，而写“x_search额度阻断，已降级”。

## 输出示例
| 步骤 | 状态 | 备注 |
|---|---:|---|
| x_sent | ⚠️ | x_search额度阻断；读本地x_sent + web搜索替代，非X实时 |

## 不要保存为永久负面结论
不要在 skill 或 memory 中写“x_search不可用”。额度/订阅可能随时恢复；只记录这类错误的处理路径。