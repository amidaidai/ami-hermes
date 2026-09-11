# 模型切换失败 + 配置被改 — 诊断管线 (2026-08-29 observed)

用户原话："为什么我切换模型不成功，而且好多的东西都被改了。"

## 固定管线（按顺序执行，缺一不可）

### ① `hermes doctor` 先排除 venv 原生库损坏
医生会先崩还是正常，决定后续方向：
- doctor 在 `import pydantic` 处抛 `SystemError: The installed pydantic-core version (2.48.0)
  is incompatible with the current pydantic version, which requires 2.46.4` → **venv 原生库损坏**，
  这是最常见根因，不是配置问题。完整修复见 `hermes-windows-maintenance` 技能的
  "venv native-lib breakage" 章节 + `references/pydantic-core-version-conflict.md`。
- **关键判据**：旧会话（Web UI 常驻进程）正常、新进程全崩 = 模块已加载在内存里，
  磁盘上的 pydantic-core 被污染。此时任何"切换模型"操作都必然失败（切换要起新会话）。

### ② 查 errors.log 的 provider 级错误
```bash
grep "API call failed" ~/AppData/Local/hermes/logs/errors.log | tail -20
```
- `summary=HTTP 500: Internal server error` 且 `provider=opencode-go ... model=gpt-5.6-luna` →
  目标 provider 服务端坏，切换目标本身不可用。**不是本地配置错误**，换 provider 目标即可。
- 同时看 `MCP server 'binance' failed ... Connection closed` → 同一根因（MCP server.py 无法 import）。

### ③ diff config.yaml.bak.* 时间链还原改动
本机 config 每次写入都会留 `.bak` 或时间戳备份，按时间倒推谁改了什么：
```bash
cd "$(dirname "$(hermes config path)")"
ls -la config.yaml.bak*
diff <(grep -vE '^\s*(#|$)' config.yaml.bak.<旧>) <(grep -vE '^\s*(#|$)' config.yaml) | head -60
```
本会话抓到：`model.default` 从 DeepSeek 系被改成 `gpt-5.6-luna / opencode-go`，
`fallback_providers` 被塞入 4 个 openrouter 免费模型（与铁律"无自动fallback"冲突）。

### ④ 看 Web UI bridge 日志确认实际跑的模型
```bash
grep -E "model|provider" ~/.hermes-web-ui/logs/bridge.log | tail -25
```
bridge.log 逐会话记录 `model=... provider=...`，能确认 Web UI 会话实际用的模型，
与 config.yaml 里 `model.default` 对照，判断是会话级覆盖还是配置级改动。

### ⑤ 查 cron 是否有 restore 事件
```bash
ls ~/AppData/Local/hermes/cron/ | grep bak
```
`jobs.json.bak.pre-restore.<date>` 存在 = 今天有人对 cron 做过 restore 操作。
用 python 读 `jobs.json` 和备份，diff 每个 job 的 model/provider/enabled/script 字段。

## 恢复动作（合法通道）
- 标量用 CLI：`hermes config set model.default deepseek-v4-flash-vision-exp` +
  `hermes config set model.provider deepseek`（本会话验证有效）。
- `patch` 工具拒绝写 config.yaml（安全防护，返回 "Refusing to write to Hermes config file"），
  不要用它。
- `hermes config set fallback_providers "[]"` 会把空列表写成字符串 `'[]'`——对空 fallback
  无实际影响，但验证时 grep 确认。
- 修完必须重启 gateway（旧进程仍加载损坏环境）+ 开新会话才生效。

## 验证
```bash
hermes doctor              # 全绿
./venv/Scripts/python -c "import pydantic, pydantic_core, openai; print(pydantic.__version__, pydantic_core.__version__)"
```
