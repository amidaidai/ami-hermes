# 坑与规避 (2026-06-18 v6.8.2)

## Patch 工具编码损坏 🔴

`patch` 工具在写入含中文引号、路径反斜杠、或 Unicode 的长行时，偶发编码损坏。表现：文件中出现 `***` 或 `o...TA\"` 乱码。Python `compile()` 可能通过但运行时静默失败。

**排查：** `grep` 目标行 → 如果显示异常立即怀疑。

**规避（按优先级）：**
1. `write_file` — 整文件覆写，无编码问题
2. `execute_code` — Python 读写文件字节，可 compile 验证
3. `patch` — 仅用短替换(<80字符·纯ASCII)，替换后必须 `compile()` 验证

## DDGS 不可靠 ⚠️

`duckduckgo_search` 库不稳定：有时返回 0 结果，有时正常。不要作为主搜索引擎。

## Firecrawl 彻底不可用 🔴 (2026-06-19 更新)

Firecrawl 搜索已完全不可用（Payment Required），所有 `web_search` 调用均失败。不是限速或超时，而是账号欠费。不要再重试同一方式。

**当前搜索链（Firecrawl 替代）：**
1. Brave Search API (2000次/月·Key在 secrets/brave_api_key.txt)
2. Exa API (1000次/月·Key在 secrets/exa_api_key.txt)
3. DDGS (备用)
4. 社区数据兜底（CoinGecko + CMC + alt.me）
5. XAU专用：金十MCP + Kitco web_extract + Investing.com web_extract 替代搜索
6. 宏观：Yahoo Finance web_extract (^SPX, ^TNX, GC=F)

## event_ban 阈值

- BTC/ETH：5% (24h波动) — 早期配置2%过严导致误触
- XAUUSD：1%
- 阈值定义在 `multi_model_engine.py:check_event_ban()`

## B等待状态不应出盲入场价

模板规则：🟡B等待时操作段不给出入场价格，只写触发条件。入场价写在 `—— 预案A/B · {方向}（{触发条件}·概率）——` 下方。

## 渲染完美·数据空洞 🔴 (2026-06-21)

**致命陷阱：** 模板渲染层排版完美，但数据管线可能已全线断裂。卡片看起来"完成了"但实际上被占位符填满——`N/A`、`数据待采`、`无数据`、`VAH '—' POC '—'`、`CVD ?`、`强位移 弱`。这种情况比崩溃更危险——用户看到精美排版就以为系统正常工作。

**每次改 auto_card 或管线后必须扫描占位符：**
```bash
grep -n "N/A\|数据待采\|无数据\|'—'\|CVD ?\|裸POC ?\|方向不明/震荡" data/auto_card_*.md
```
- P0 命中→立即修复管线，不 commit
- 0 P0→才可 commit

完整审计方法论见 `references/data-pipeline-health-audit.md`。

## 用户要求监控/提醒 — 先查记忆再动手 ⚠️ (2026-06-22)

**症状：** 用户说"提醒我"或"监控XX价位"，直接创建 cron 或启动守护，没先查 memory 中用户的监控偏好。用户可能已明确纠正过方式（如 "daemon 10s 轮询替代 5m cron"、"零token优先"）。

**正确流程：**
1. 先调 `memory` 工具查用户偏好的监控方式 — 用户可能在记忆里明确写过偏好
2. 如果记忆里有明确纠正，按记忆方式操作，不重新发明轮子
3. 如果价格已在触发区（距目标位 < $50），直接报给用户决策，不要去搭一个会立刻触发的监控
4. 守护进程启动后 poll 确认存活且静默初始化成功（无输出 = 正常）

## 单模型霸凌 (EMA趋势 0.9)

引擎 v2.0 之前 EMA趋势 单模型 0.9 可碾压 4 个多头信号。v2.1 修复：HHI 多样性惩罚 + 单模型贡献 cap 0.65 + 模型数驱动动态 bias 阈值。

## 分析卡产出检查清单

出完整分析卡前验证：
- [ ] risk_gate(rr=X) 不触发禁做
- [ ] 所有止盈 R:R ≥ 1:2
- [ ] CVD C级 → 订单流×0.6 + 仓位半仓
- [ ] DMI X → 不标 A做多/A做空
- [ ] Grok 分歧 → action 降级到 B等待
- [ ] B等待 → 操作段无盲入场价·只写触发条件
- [ ] MEDIA 截图含右侧价格栏+底部CVD
