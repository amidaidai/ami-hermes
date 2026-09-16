---
name: external-claim-verification
description: Use when citing outside causes for a market move.
category: research
---

# 外部叙事断言核验（防“数字时间窗错配”）

## 触发场景
把行情波动归因给外部事件时（宏观数据、美联储、ETF 资金、爆仓、政策投票、地缘），
即：句子里出现「因为/由于/受…影响/原因是」。

## 硬规则
1. **一句一源**：每条归因句写成「断言 = 数字 + 单位 + 时间窗 + 来源URL + 发布/事件日期」。缺任一字段 → 改写成「未验证」，不得用陈述句语气。
2. **窗口必须匹配**：数字所属窗口（例如「假期缩短周的周二+周三」）必须与本次波动窗口重叠；不重叠只能当“背景/趋势”，不得当这次的原因。
3. **URL 里就有日期**：中文站点常见 `/a/202608313859578146`（=2026-08-31）、`/2026/07/03/...`。读 URL 日期优先于搜索结果的 “N days ago”。
4. **摘要不是证据**：检索标题+摘要只能用来找线索，不能下断言。要引用数字就去开原文（web_extract）并在原文里搜到那句话。
5. **量级标来源**：爆仓/ETF 资金各家口径不同（CoinGlass/SoSoValue/Farside 窗口不同），必须写「据 X，窗口 Y」。
6. **点名 GitHub/工具前先验存**：`gh api repos/<owner>/<repo>`。实测踩坑：`google-deepmind/facts-grounding`、`gaia-benchmark/GAIA` 均 **404 不存在**；`Giskard-AI/giskard` 实为 `giskard-oss`，`SodaData/soda-core` 实为 `sodadata/soda-core`。
7. **实拉数据不受此限**：自己 API 拉到并标了 live/cache 的数字（价格/OI/费率/宏观指数）可直接用；本技能只管**外部叙事层**。
8. **因果链要两个独立来源**（2026-09-15 加）：把行情归因给某个事件时，**单独一家**的二手摘要不足以支撑整条因果链——这正是本技能诞生的那个幻觉的形态（一条 Wu Blockchain 摘要撑起「ETF 流出→价格跌」全链）。
   同一家的不同写法（`Reuters`／`路透`／`reuters.com`）只算 1 家；闸门用 `sources_in()` 归一。
   自己仪器取的值要写清上游才算两家：写「据 `macro_probe`（现场实拉·上游 Yahoo/FRED）」，
   而不是只写「据 macro_probe」——否则闸门会（正确地）标成单一来源。
   发关键结论前用 `--strict` 跑一遍。
9. **代码/文件引用不算外部数字（2026-09-16 加）**：`scripts/card_reformat.py:311-331,388-396`
   这类 `路径:行号/行号范围`（含带日期的文件名如 `test_x_20260916.py`）已在 `claim_lint` 里
   抽数前屏蔽——写审计/修复回复时带行号不会再产生 incident。屏蔽的是**引用本身**：
   同一句里的真实外部数字（例：「清算 4.73 亿美元」）仍旧照抓，不要靠“整句像代码”蒙过关。


## 已验证可用工具（2026-09-15 /repos 实测，stars 为当时值）
| 层 | 仓库 | 星 | 用途 |
|:--|:--|--:|:--|
| 引用接地评分 | confident-ai/deepeval | 18,270 | faithfulness/hallucination 指标 |
| 引用接地评分 | explodinggradients/ragas | 15,729 | faithfulness，需 context |
| 引用接地评分 | truera/trulens | 3,550 | RAG triad |
| 本地小模型打分 | vectara/hallucination-leaderboard | 3,312 | HHEM groundedness 分（离线） |
| CI 闸门 | promptfoo/promptfoo | 25,101 | context-faithfulness/factuality 断言 |
| 输出约束 | guardrails-ai/guardrails | 7,412 | schema/事实约束 |
| 数据口径校验 | great-expectations / unionai-oss/pandera | 11,794 / 4,454 | 列/行级断言 |
| 数据口径校验 | awslabs/deequ · sodadata/soda-core | 3,646 / 2,427 | 数据质量 SLA |
| 契约/血缘 | datacontract/datacontract-cli · OpenLineage/OpenLineage | 1,066 / 2,656 | freshness/质量契约、血缘 |
| 事实链审计 | superwesleyhys-ux/factcircuit | 118 | claim→evidence→archive 可回放 |
| 论文索引 | EdinburghNLP/awesome-hallucination-detection | 1,128 | 检索入口 |

## 自动闸门（已上线，不只靠自觉）
- 看门狗：`scripts/claim_watchdog.py`（读 Hermes `state.db` 里**最近的行情归因类回复**，自动跑本闸门）
- cron：`叙事断言闸门`（`4,14,24,34,44,54 * * * *`，no-agent，deliver=local，workdir=`D:\Hermes agent`）
- 输出分两档：**硬违规** → `data/claim_lint_alerts.jsonl` + 本地告警；**单一来源** → `data/claim_lint_weak.jsonl`（只落档、不报警、不阻断）
- 生命体征：`data/claim_watchdog_heartbeat.json`（`db_ok/checked/hits/weak/local_vals/local_files`），
  已被 `data_freshness_watchdog.py` 监控（阈值 0.7h）；**DB 读不到时 exit 2 并出声**，不再“看起来干净”
- 状态/幂等：`data/claim_watchdog_state.json` 的 `last_id`，重跑不会重复报
- 精度约束（防刷屏）：只检查含**市场标记**（BTC/黄金/现价/加息/ETF/爆仓…）且含**归因标记**（因为/据/流出…）的消息；
  数字只放行带金融单位（亿/万/美元/%…）或 ≥ 10,000 的；行号/版本号/vX.Y 一律跳过。
  **但**：含代码词的消息只有在**没有价格**（`\d{2},\d{3}`）时才跳过——否则行情回复里顺口提了 `tests/xxx.py` 就会整条漏检
- 已知取舍：闸门偏保守——“9/14”这种简写日期**不算日期**，必须写 `2026-09-14` 或 `9月14日`；宁可误报，不漏报

## 自审发现（2026-09-15 两轮审计实测，已修 + 已加回归）
闸门本身犯过的错，每次都靠“拿真实语料量误报率/召回”才暴露：
1. **单位不参与比对（P0）** — `1.668亿` 的撞子被拿去和本地的 `1.668` 比，加宽可核集合后**真幻觉反而漏掉**。
   修：`norm_token()` 单位归一 + token 精确命中 + 数值回退容差 0.5%→0.05%；
   再加一层：**亿/万 只认 token 精确命中**（量级容差是撞车温床，数值路径直接跳过）。
2. **表格行借用邻行出处（P0）** — 一张表里只要有一行写了 `Reuters 9/14`，同一段的其它行也“看起来有源”→ `1.668亿` 漏检。
   修：**出处继承只在正文句之间成立；表格行必须自带出处**（`prev_row`/`cur_row` 判定）。
3. **闸门范围过宽（P1）** — 把卡面价位/百分比（自己实拉或推算）也当“外部断言”要出处：
   24h 语料实测误报 **19/21 = 90%**。修：`scope_only=True` 只查“外部事件类”句子，卡面数字标 `out_of_scope`。
   修后硬违规 **9/29 = 31%**，召回完整（1.202亿/1.668亿/2.7亿/3.8亿/4660万 全抓到）。
4. **CLI 与看门狗口径不一致（P0）** — 同一份草稿：CLI 报 52 条、看门狗 0 条（CLI 没传 fin_only/scope_only）。
   修：CLI 默认口径**必须与看门狗同源**（`fin_only=True, scope_only=True`），放宽用 `--all-numbers` / `--no-scope`；加回归锁死。
5. **含代码词就整条跳过（P1，漏检）** — 行情回复提到 `tests/xxx.py` 即被 SKIP，实测把本人 11:03 的行情回复整条漏掉。
   修：只有「命中代码词 **且** 不含千分位价格」才跳过。
6. **舍入与符号被当编造（P1，误报）** — 写作把实拉 `0.134%` 写成 `+0.13%`、把 `-1.041%` 写成 `−1.04%`，
   被当成“外部无源”。修：`rounds_match()` 按断言精度四舍五入比对 + 比对取绝对值（负号由正文方向词承载）。
7. **CLI 的默认语料实际是空的（P0，假绿灯）** — `--data` 默认值写成目录名，`load_local_numbers()` 读目录静默跳过 →
   CLI 的可核集合为空，比看门狗弱一档，`exit 0` 含金量不足。修：`default_corpus()` 把目录展开成 JSON 文件并同步建 token 集合；
   另有 `--with-tools` 可拉到与看门狗完全同口径。
8. **语料自我背书（P0，召回风险）** — 本地语料曾包含我自己的 `outputs/audit_*.json`／`draft_*.md`，
   等于把“我写过的错数字”变成“本地已实拉证据”，幻觉会自己给自己背书。
   修：`is_narrative_artifact()` 排除叙述稿/审计存档，只让**实拉数据产物**进语料（`data/auto_card_*` / `binance_*` / `tv_*` 等）；
   同时 `build_token_set` 的字符串解析补上亿/万单位（原先只认 `%`，单位会丢）。加回归锁死：「真幻觉数字必须仍被拦」。
**写作代价（主动接受的）**：引宏观指数仍要写「据 macro_probe（现场实拉·上游 Yahoo/FRED）」，否则会落进 weak 档（不阻断，但看着确实该补）。

## 机器闸门（发出前手动跑）
```bash
python scripts/claim_lint.py --file <草稿.md> --asof 2026-09-15 \
    --data outputs/binance_BTCUSDT_<ts>.json     # 实拉数据文件越多越准
# exit 0 = 通过；1 = 有外部数字缺出处/日期 或 时间窗错配；2 = 闸门没跑起来（输入空）
python scripts/claim_lint.py --file <草稿.md> --strict        # 单一来源也算违规（重要结论用）
python scripts/claim_lint.py --file <草稿.md> --all-numbers --no-scope   # 放宽：查所有数字/所有句子
python -m pytest tests/test_claim_lint.py -q                 # 23 用例契约回归
```
闸门规则：R1 本地可核（token 精确命中，或数值容差 0.05%；**亿/万 只认 token 精确命中**，且按断言精度舍入、取绝对值）→ 免出处；
R2 外部数字必须同句带 URL/具名来源 **且**日期；R3 相对时间词（昨日/刚刚/隔夜…）+ URL 日期距今 >2 天 → `window_mismatch` 拦截；
R4 同一段落可继承上一句出处（标 `OK-sourced*`），换段必须重给；表格行必须自带出处；
R5 归因类断言若该段只有 <2 个**独立**来源 → 默认进 `weak_source` 弱提示（不阻断），`--strict` 才拦。
实测：把本人 2026-09-15 那段带幻觉的话喂进去，**6 条被拦（exit 1）**；按契约改写后 0 拦截（exit 0）。

## 自检（发出前 30 秒）
把答复里所有数字扫一遍：① 是不是我自己实拉的？② 若不是，它有没有 URL+日期+窗口？
③ 有没有把两个不同时期的事件拼成一条因果链？——任一答不上，就把那句降级成「疑似」或删掉。

## 已知失败案例（本人 2026-09-15 实犯）
- 把「假期缩短周（周二 4,660 万 + 周三 1.202 亿 = 1.668 亿）」当成「昨日两日合计」，挂在 9/13–14 行情上；实际 9/11 单日仅净流出 **$1,329 万**，上周合计 **-4.63 亿**。
- 把 2026-08-31 的「沃什放鹰 35%→60%」文章与 9/11 的 CPI 事件拼成一条无日期的因果链；可核的只有 Reuters 9/11「rate futures price about 85% chance of hike」。
