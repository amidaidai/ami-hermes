# xAI Grok OAuth 设置（2026-06-29 实操记录）

## 命令
hermes auth add xai-oauth
浏览器弹出 → 登录 X 账号 → 确认授权 → 令牌保存。

## 验证
cat ~/AppData/Local/hermes/auth.json | python -c "import sys,json;d=json.load(sys.stdin);p=d.get('providers',{}).get('xai-oauth',{});print(f'Has token: {bool(p.get(\"access_token\"))}')"

## 模型列表
- grok-build-0.1: 默认
- grok-4.3: 推理
- grok-4.20-0309-reasoning: 深度推理
- grok-4.20-0309-non-reasoning: x_search 默认

## 切换模型
hermes config set model.default grok-4.3
hermes config set model.provider xai-oauth
## 恢复
hermes config set model.default deepseek-v4-flash
hermes config set model.provider opencode-go

## 问题
- Token 自动刷新，invalid_grant 需重跑 hermes auth add xai-oauth
- Loopback 180s 超时
- 远程需 SSH 端口转发