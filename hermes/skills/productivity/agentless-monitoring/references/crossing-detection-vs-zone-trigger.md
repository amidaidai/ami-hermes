# 穿越检测 vs 窄带触发 — 让关键位告警不漏检（2026-08 实证）

## 问题：窄带区间触发会漏检

旧做法是「价格落在关键位 ±0.07% 的窄带内才触发」。**致命缺陷**：价格可以在
两轮巡检之间**直接跳过窄带**。实案：BTC 从 79,260 跳到 79,735，中间越过 79,633
关键位，但两轮巡检都没采样到"落在窄带内"的时刻 → 到价了却没触发、没推送。

## 修正：穿越检测（crossing detection）

只要价格自上次巡检以来**穿过关键位**（任一方向），立即触发。不再要求"落在区间内"。

```python
LEVEL = 79633.0
prev = state.get("last_price")      # 上一次巡检的价格

crossed = False
if prev is not None:
    # 向上穿 或 向下穿
    if (prev < LEVEL <= price) or (prev >= LEVEL > price):
        crossed = True
```

验证用例（全部通过）：
| last_price | price | 判定 |
|:--|:--|:--|
| 79500 | 79700 | 79633 up ✓ |
| 79700 | 79500 | 79633 down ✓ |
| 78500 | 78350 | 78400 down ✓ |
| 78300 | 78550 | 78400 up ✓ |
| 79500 | 79550 | 无穿越（低于79633摆荡）✓ |
| 78500 | 78600 | 无穿越（高于78400摆荡）✓ |

关键：**窄幅摆荡不会误报**（同侧不触发），只有真穿线才触发。这比"落在窄带"稳健得多。

状态文件必须持久化 `last_price`，跨调用保留，否则 `prev=None` 无法判断穿越
（首轮只是锚定，第二轮起才有意义）。

## "实时"的定义与实现

- **cron 最小粒度是 1 分钟**（`* * * * *`）。用户说"不该是一分钟，应该是实时"时，
  分钟级 cron 无法满足。
- **真正实时 = 常驻守护进程 + 亚秒轮询**（`terminal(background=True)` 启动，
  `while True: 探价; sleep(0.5)`）。对"关键位到价提醒"，0.5s REST 轮询已足够"准实时"。
- 探价源用 REST（`fapi/v1/ticker/price`）实测稳定（每次 ~0.35s）。WS 在部分环境被
  代理/DNS 卡死（见下），WS 是否可用取决于环境，不要当作默认假设。

## 守护进程 + agent 搬运分层（只触发才烧 token）

```
[守护进程 0.5s 零token] ──穿位──> 写 data/xxx_trigger.json
                                        │
[agent cron 每2min] ──读触发文件──> 有 TRIGGER → agent 分析推话题；无 → 零输出
                                        │
[no_agent 看门狗 cron] ──心跳超90s──> 自动重启守护
```

- **守护**：零 token，只探价 + 判断穿越 + 写触发文件，不做分析。
- **搬运 cron**：读触发文件，`TRIGGER` 前缀才让 agent 分析推送；`WAIT/COOLDOWN` 零输出。
- **看门狗**：守护挂了自动拉起（psutil 查进程 + 心跳新鲜度）。

## 关键：未触发时不得推送（deliver=local）

agent cron 若 `deliver=telegram:...`，会把 agent **每次**最终回复（含"未触发，现价X"）
都自动推送 → 用户收到一堆"没到价"的噪音。用户明确："没有到位置就不要推送给我。"

**必须**：
1. cron `deliver=local`（不让 cron 自动投递 agent 回复）
2. prompt 硬性命令：`WAIT/COOLDOWN → 零输出，不调用任何推送函数`；只有 `TRIGGER`
   前缀才允许调 `send_telegram_reliable` 推话题。
3. 未触发时连"未触发"这句都不发。

## 看门狗脚本要点（Windows）

- 用 `psutil` 判断守护进程活着：命令行含脚本名且不含 `watchdog` 字样的进程
  （过滤自身/子进程虚警），同时校验心跳 `< STALE_SECONDS(90s)`。
- 心跳陈旧/缺失 → 杀旧进程（`process_iter` + `terminate`）+ `subprocess.Popen` 重启
  （detached，`start_new_session`/`CREATE_NEW_PROCESS_GROUP`）。
- 守护健康时输出 `OK guard alive ... hb_age=0s`，不误重启（否则边杀边启循环）。
- no_agent cron 跑看门狗，`deliver=local`，`repeat=-1` 循环。

## 状态清理

脚本改版/测试后，`rm -f` 对应的 `*_state.json` 和 `*_trigger.json`，否则旧状态
（残留 last_price / 冷却时间戳）会干扰新逻辑的判断。
