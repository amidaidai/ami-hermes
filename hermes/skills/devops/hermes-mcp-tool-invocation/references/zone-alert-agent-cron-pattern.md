# 到价警报 cron（混合模式）— 零token前置 + 到价才分析

## 适用场景
用户要求"设置两个价位警报，到了之后分析并推给我"时。不是纯价格提醒（no_agent 单行），而是**到价后做完整分析再推送**。

## 为什么不用纯 no_agent 或纯 agent
- 纯 no_agent：只能推一行价格，不满足"到价后分析"。
- 纯 agent cron：每 2 分钟无脑跑全分析 → 烧 token，且大盘不动时浪费。
- **混合 = no_agent/零token 前置脚本(查价) + agent cron(到价才触发分析)**。前置脚本 stdout 注入 agent context，agent 只在 context 含 TRIGGER 才消费 token 做分析。

## 实现结构

### 1. 前置脚本（零token，用**穿越检测**而非窄带）
**⚠ 2026-08-28 实证修正：窄带触发会漏检。** `ZONE_LO <= price <= ZONE_HI`（落在 ±容差内才触发）在价格两轮巡检之间**直接跳过窄带**时会漏掉关键位。实案：BTC 从 79,260 跳到 79,735，跳过 79,633 却没触发。改用**穿越检测**——价格自上次巡检以来穿过关键位（任一方向）即触发。

```python
LEVEL = 79633.0                  # 关键位（不再是 ZONE_LO/HI 窄带）
COOLDOWN = 1800                  # 30min 防刷屏
STATE_FILE = Path.expanduser("~/AppData/Local/hermes/data/btc_alert_<key>_xstate.json")

prev = state.get("last_price")   # 上次巡检价，持久化到 state 文件
crossed = False
if prev is not None:
    if (prev < LEVEL <= price) or (prev >= LEVEL > price):   # 向上穿 或 向下穿
        crossed = True

if crossed:
    if not last_alerted or (now-last_time) > COOLDOWN:
        save_state({"last_alerted": True, "time": now, "price": price, "last_price": prev})
        print(f"TRIGGER price={price:,.0f} zone=<key> dir={'up' if price>prev else 'down'} desc=...")
    else:
        print(f"COOLDOWN price={price:,.0f} zone=<key>")
else:
    # 未穿越：仅更新 last_price，重新写 state（保留冷却时间）
    save_state({"last_alerted": False, "time": last_time, "price": price, "last_price": price})
    print(f"WAIT price={price:,.0f} zone=<key>")
```

关键点：
- **`last_price` 必须持久化**，否则首轮 `prev=None` 无法判断穿越，第二轮回才有意义。
- 穿越检测**同侧窄幅摆荡不误报**（`prev < LEVEL < price` 同侧不算穿），只有真穿线才触发。
- 警戒词只有 `TRIGGER` / `COOLDOWN` / `WAIT` 三种，agent 据此分支。

### 2. agent cron prompt（未触发必须零输出）
**⚠ 2026-08-28 实证修正：要 deliver=local + 未触发零输出。** 用户明确："没有到位置就不要推送给我。" agent cron 若 `deliver='telegram:...'`，会把 agent **每次**最终回复（含"未触发现价X"）都自动推送成噪音。因此：

```python
cronjob(action='create',
  name='<品种><关键位>警报',
  schedule='*/2 * * * *',        # 必须显式写 cron 表达式，不要写 '2m'
  repeat=-1,                      # 显式 -1 = forever（否则默认 once 只跑一次）
  script='<zone>_pre.py',
  deliver='local',                # 关键：不让 cron 自动投递 agent 回复
  workdir='D:\\\\Hermes agent',
  enabled_toolsets=['file','terminal','web'],
  prompt="""前置脚本输出含义:
- TRIGGER → 到价，做完整<品种>分析并推 386 话题(RichMarkdown 真表格)
- COOLDOWN/Wait → 未触发，**本次运行必须零输出**：不做分析、不调任何推送函数
  (send_telegram_reliable/telegram_direct 全都不许调)、不发"未触发"这句话。
  直接结束(deliver 已设 local，不会外发)。
⚠ 铁律：只有 TRIGGER 才允许推送。未触发时连"未触发"这句都不要发。
若触发: TV MCP(mcp__tradingview__) 读主指标+副指标行动格 → curl 衍生品方向票 →
判定等级(A/B/C/X) → send_telegram_reliable(parse_mode='RichMarkdown') 推表格, 回执含 rich_sent。
TV 不可用则 REST 降级并注明，绝不编造。只推 386 这一条完整卡。"""")
```

关键点：
- **`deliver='local'`**：cron 不再自动投递 agent 回复到 TG（避免"未触发"刷屏）。只有 agent 在 TRIGGER 分支里显式调 `send_telegram_reliable` 才推 386。
- **prompt 硬性命令"未触发零输出"**：agent 模型即使被投喂 token 也倾向产出文本，必须命令它"不调任何推送函数、不发未触发这句话"，才杜绝噪音。这是 agent cron 无法真正静默的解法。

## 实时性：到价提醒要"实时"用 daemon，不是分钟 cron
**⚠ 2026-08-28 实证修正：cron 最小粒度 1 分钟，用户说"不该是一分钟、应该是实时"时 cron 不满足。** 真正实时 = 常驻守护进程 + 亚秒轮询：

```
[守护进程 0.5s 零token] ──穿越──> 写 data/<key>_trigger.json
                                        │
[agent cron 每2min] ──读触发文件──> TRIGGER → 分析推 386；WAIT → 零输出
                                        │
[no_agent 看门狗 cron] ──心跳超90s──> 自动重启守护
```

- 守护探价源用 REST（`fapi/v1/ticker/price` 每次 ~0.35s 实测稳定）。WS 在部分环境被代理/DNS 卡死，别当默认假设。
- 看门狗用 `psutil` 判断守护进程活着（命令行含脚本名且不含 `watchdog`，过滤自身/子进程虚警）+ 心跳新鲜度（<90s 健康），守护健康时输出 `OK guard alive` 不误重启。
- 配置文件驱动：监测位从分析推荐（磁吸/POC/VAH/VAL/nPOC/CT会话位/FVG/OB，**不只磁吸位**），用户确认后写入 `data/keylevels.json`，守护热读（加位/删位零重启），一个守护统管多品种。

详见 `agentless-monitoring` skill 的 `references/crossing-detection-vs-zone-trigger.md`。

## 陷阱
- **`schedule='2m'` 会被读成一次性**：必须写 `*/2 * * * *` 才循环。
- **`repeat` 默认 once**：创建后马上 `update` repeat=-1，否则只跑一次就停。
- **enabled_toolsets 不要限制 MCP 工具**：MCP 不属 toolsets，限制会丢 TV/Binance。留 file/terminal/web 即可（terminal 跑 curl，file 读状态，web 兜底）。
- **deliver 用 `local` 而非 `telegram:...`**（agent 推送场景）：telegram 会让 cron 自动投递 agent 每轮回复造成"未触发"噪音；local 让 agent 只在 TRIGGER 时显式推。
- **冷却时间戳会拦新版本**：改脚本/改位后 `rm -f` 对应 `*_state.json` 和 `*_trigger.json`，否则残留 last_price/冷却时间干扰判断。
- **交付目标**：如确需 cron 直接交付，用 `deliver='telegram:<chat>:<topic>'`（如 386），不要 `origin`（话题里 origin 会静默丢消息）。
