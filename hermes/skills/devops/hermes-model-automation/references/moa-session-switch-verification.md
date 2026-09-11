# MoA 会话切换核验记录

## 适用场景

用户要求将当前 Hermes CLI/Telegram 会话切换到 MoA 时，核对“配置已修改”和“当前会话已生效”这两个不同状态。

## 可靠流程

1. 读取活跃配置，确认：
   - `moa.active_preset` = 目标预设
   - `moa.default_preset` = 目标预设（若希望新会话默认使用）
   - `moa.presets.<目标>.enabled` = `true`
2. 确认主模型路由同时指向 MoA：
   - `model.provider` = `moa`
   - `model.default` = 目标预设名
   - 当前平台工具集含 `moa`
3. 用 `hermes config check` 检查配置格式。
4. 明确告知：已经运行的会话不会中途重载这些配置；要求用户发送 `/reset`，或重启 CLI/gateway。
5. 新会话启动后，再检查运行时 provider/model 与 MoA 状态，并做一次真实请求验收。

## Windows 配置写入

Hermes 配置文件属于安全敏感文件，`patch` 工具可能拒绝直接写入。优先使用：

```bash
hermes config set moa.default_preset AMI
hermes config set moa.active_preset AMI
hermes config check
```

但这两项只切换预设选择，不会自动把 `model.provider` 改为 `moa`。如果目标是常驻 MoA，还必须按实际配置接口设置主模型路由，并在新会话验收。

## 表述规范

- 正确：配置已切到 AMI，等待 `/reset` 后新会话生效。
- 不正确：当前这条消息已经由 AMI-MOA 处理（若尚未重置或未验证运行时路由）。
