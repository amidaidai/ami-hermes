# Telegram 推送投递调试 Runbook

适用：审计「推TG的cron是否真出推送」时，发现 cron 显示 `ok` 但用户群收不到消息。

## 症状
- `hermes cron list` 显示推TG cron `Last run: ok`
- 但 TG 群 `-1003733144325` 话题里收不到任何卡片
- 用户误以为「系统假的 / cron 没跑」

## 根因（三层，逐层排查）

### 1. Token 未配置 → Hermes 静默丢弃
Hermes 的 TG 投递读 `TELEGRAM_BOT_TOKEN` 环境变量（cli.py: `get_env_value('TELEGRAM_BOT_TOKEN')`）。
未配置时 deliver 失败**不报错、不重试、不写 last_delivery_error**，cron 仍显示 ok。

验证：
```bash
env | grep -i TELEGRAM
grep -iE "bot_token|TELEGRAM_BOT" "C:/Users/Administrator/AppData/Local/hermes/config.yaml"
# 两者皆空 = token 缺失，推送必失败
```

### 2. 脚本在跑但产物只落本地
确认脚本真的执行了（有 output 产物）：
```bash
ls -lat "C:/Users/Administrator/AppData/Local/hermes/cron/output/<job_id>/" | head
# 有连续时间戳 .md = 脚本跑成功 + 有 stdout
```
这是「cron 在跑 ≠ 推送成功」的铁证：脚本成功，但 stdout 没推出去。

### 3. Forum topic 群需要 thread_id
群 `-1003733144325` 是超级群论坛（带话题）。直接发群整体 ID 报 `TOPIC_CLOSED` 400。
deliver 格式 `telegram:CHAT_ID:THREAD_ID` 里的 `:846` 就是 thread_id，Hermes send 支持 `platform:chat_id:thread_id`。

---

## 修复步骤

### Step A：配置 token（持久化）
```bash
# Windows 永久环境变量（下次会话也生效）
setx TELEGRAM_BOT_TOKEN "你的TOKEN"
# 当前会话立即生效
export TELEGRAM_BOT_TOKEN="你的TOKEN"
```
> 注意：`hermes config set telegram.bot_token "X"` 会被当成环境变量名 `TELEGRAM.BOT_TOKEN` 拒绝（点号非法）。用 `setx` / 系统环境变量，或设 `TELEGRAM_BOT_TOKEN`。

### Step B：验证 bot 身份 + 群可发
```python
import urllib.request, json
TOKEN="你的TOKEN"
CHAT="-1003733144325"
TID=846
# 1. token 有效？
print(json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/getMe",timeout=10).read()))
# 2. 带 thread_id 发测试（TOPIC_CLOSED 说明没带 thread）
data=json.dumps({"chat_id":CHAT,"text":"链路测试","message_thread_id":TID}).encode()
req=urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data=data,headers={"Content-Type":"application/json"})
print(json.loads(urllib.request.urlopen(req,timeout=10).read()))
```

### Step C：真表格渲染坑（高价值）
TG **官方无原生 table 实体**。`parse_mode=Markdown`（V1）下 `|` 表格语法不被解析，且文本里 `:` 等特殊字符会触发 `can't parse entities: Can't find end of the entity` 400 错误。

**正确做法（二选一）：**
1. **纯文本（无 parse_mode）** — TG 桌面/手机端对等宽字体下 `|` 对齐显示成表格外观（Hermes 默认投递即此模式，手机端可读）
2. **HTML `<pre>` 包裹** — `<pre>| 品种 | 价格 |\n|:----|:----|\n| BTC | 63300 |</pre>` + `parse_mode=HTML`

**不要**用 `parse_mode=Markdown` 发 `|` 表格 —— 必 400。

### Step D：用 Hermes 官方通道验证
配好 token 后，最权威验证是走 Hermes 自己的投递（确保 cron deliver 走同一路径）：
```bash
echo "| 测试 | 真表格 |
|:----|:----|
| BTC | 63300 |" | hermes send --to telegram:-1003733144325:846
# 返回 'sent' = 通道通
```

### Step E：手动触发一个推TG cron 确认
```bash
hermes cron run <推TG的job_id>
# 然后去 TG 群确认收到；若仍无 = token 未对当前 hermes 进程生效，重启 hermes 或重开终端
```

---

## 审计必查项（并入 tangxi-system-audit）
- `T1`：推TG cron 数 = 解析 `deliver` 含 `telegram` 的 job 数
- `T2`：`TELEGRAM_BOT_TOKEN` 非空？（`env | grep -i TELEGRAM`）
- `T3`：抽一个推TG cron 手动 `hermes cron run` → output 有内容但群无消息 = token 缺失铁证
- `T4`：forum topic 群必须带 `:thread_id`，否则 `TOPIC_CLOSED`

## 本会话实测数据
- bot: @anheauberon_bot（token 格式 `数字:字母串`）
- 群 `-1003733144325` + thread `846` 发送成功
- `hermes send --to telegram:-1003733144325:846` 返回 `sent` 确认通道恢复
- 7 个推TG cron（BTC关键位/Orion/X情绪LLM/2看门狗/复盘提醒/每日运维聚合）全部依赖此 token
