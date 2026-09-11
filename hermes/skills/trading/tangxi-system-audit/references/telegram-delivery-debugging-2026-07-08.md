# Telegram 投递调试修正 · 2026-07-08

## 背景
2026-07-07 旧 Pitfall 假设「用户没收到 TG = TELEGRAM_BOT_TOKEN 缺失 → Hermes 静默丢弃」。
2026-07-08 本会话推翻此单一假设：用户说「7个推TG的cron一条都没见到」，但实测
token **已配置**、投递链路**真实可用**（`hermes send --json` 返回 `message_id` 连续
递增 5452→5456）。「用户没收到」另有四种独立原因，必须分离验证。

## 四因分离诊断树（用户说「没见到」时按顺序排除）

### ① 配置路径找错（最常见误判来源）
- 错误：盲目 `grep telegram "$APPDATA/hermes/.env"`（Roaming 路径常为空）→ 误判「token缺失」。
- 正确：用 `hermes config env-path` 取真实 .env 路径（本机 = `AppData/Local/hermes/.env`），
  `hermes config path` 取 config.yaml。以这两个为准，不要硬编码 Roaming/Local 猜测。
- token 是否加载：`hermes send --list telegram` 能列出 target 即证明 token 已生效。

### ② 投递是否真到服务端（用 --json 拿真实回执）
- 错误：`hermes send ... "x"` 回 `sent` 就报「投递成功」。`sent` 仅为 CLI 回显，不代表
  真实送达，更不代表用户可见。
- 正确：`hermes send --to telegram:CHAT:THREAD "x" --json` → 看 `success:true` +
  **`message_id` 连续递增**（如 5452→5453→5454）。`message_id` 递增 = Telegram 服务端
  真实接收，这是唯一可靠证据。
- 连发 3 条看 message_id 是否连续递增，验证链路真实通。

### ③ cron 本身有无产出（silent output 陷阱）
- 即便 token 对、topic 对，若脚本无 stdout，cron 显示 `Status: silent (empty output)`
  → 无内容可推。
- 检查：`cat "$LOCALAPPDATA/hermes/cron/output/<job_id>/<latest>.md"` 看是 `silent` 还是
  有内容。silent = 脚本没产出，与 token/topic 无关，属独立故障类（P2/P3 取决于该 cron
  是否本应有产出）。

### ④ 用户看的是哪个 topic（发错地方）
- `hermes send --list telegram` 列出所有 forum topic：如 `阿弥黛黛 / topic 846`、
  `阿弥黛黛 / topic 386`、`Tang Xi / topic 15390` 等。
- cron 配的 `:846` 可能与用户实际在看的 `:386`（BTC信号源）不同 → 消息到了但用户没在看
  那个话题。
- 解决：确认用户常看 topic 后，把相关 cron 的 `deliver` 改到对应 thread_id；或用
  `hermes send --to telegram:-1003733144325:386` 重发验证。

### ⑤ 用户静音/退话题（已发未看）
- 排除 ①②③④ 后，让用户直接确认「去该话题看有没有 message_id XXXX」。用户说有 = 投递通，
  只是之前没注意；说没有 = 回到 ①②③④ 重查。

## 铁律（本次修正核心）
1. **bare `sent` 不是交付证明** —— 报「TG投递已验证」前必须 `--json` 拿到 `message_id`
   且确认用户可见。
2. **配置路径用 `hermes config env-path` 取，不要猜 Roaming/Local**。
3. **「用户没见到」≠「系统没发」** —— 四因（配置路径/真实回执/cron产出/topic对错）必须
   分开验证，先查 `hermes send --list` + `--json message_id` 再下结论。
4. **cron `silent (empty output)` 是独立故障类** —— 意味脚本无产出，与 token/topic 无关，
   审计时要单独标出。
