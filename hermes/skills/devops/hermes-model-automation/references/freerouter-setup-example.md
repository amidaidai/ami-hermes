# Freerouter 设置参考（2026-06-23 棠溪）

## 环境
- Hermes v0.17.0 (2026.6.19) on Windows
- 主模型: `deepseek-v4-flash` via `deepseek` provider（直连，不被 Freerouter 改动）
- OPENROUTER_API_KEY 在 .env
- 每日 06:00 cron: Freerouter 自动扫免费模型 → 只更新 auxiliary.vision + delegation
- Tool Search: `enabled: on`（强制开启），`threshold_pct: 3`

## 关键架构决策：Freerouter 不改主模型

**主模型 (`model.default`) 永远不被 Freerouter 触碰。** Freerouter 只管理：
- `auxiliary.vision.model` / `.provider` → 视觉走 OpenRouter 免费模型
- `delegation.model` / `.provider` → 子代理走 OpenRouter 免费模型

主模型（当前 `deepseek-v4-flash` via `deepseek`）是手动管理的，不参与 Freerouter 自动切换。

原因：主模型是直连 DeepSeek 的稳定推理通道，不应该因为免费模型的可用性波动而切换。

## patch_config() 正确行为

```python
def patch_config(main_model, vision_model, delegation_model):
    # 只改这两个 section：
    # 1. auxiliary.vision → model + provider + api_key
    # 2. delegation → model + provider
    # 不改 model.default 和 model.provider
```

如果 patch_config 误改了 model.default → 立即恢复：
```bash
hermes config set model.default "deepseek-v4-flash"
hermes config set model.provider "deepseek"
```

## 已修复的 Bugs

### Bug 1: DRY_RUN 默认 true → cron 永不生效
- **位置**: freerouter.py 第 39 行和第 768 行
- **修复**: `DRY_RUN = os.environ.get("DRY_RUN", "false")`（默认改为 false）
- **影响**: 之前所有 cron run 都只输出 DRY-RUN 通知，config 从未改变

### Bug 2: Windows Python `f'\\1{var}'` → 八进制转义
- **位置**: `patch_config()` 中的 `re.sub(pattern, f'\\1{var}', content)`
- **原因**: Windows MSVC Python 把 `\\1` 解释为 `\\x01`（八进制），不是 re.sub 反向引用
- **修复**: 用 lambda 形式：`re.sub(pattern, lambda m: m.group(1) + var, content)`
- **影响**: live run 后 `model.default` 等字段实际上没变（regex 匹配了但替换写入了 `\\x01`）

### Bug 3: delegation section 的 `break` 导致 provider 被跳过
- **位置**: `patch_config()` delegation patching 循环中 `if stripped.startswith("model:")` 后面的 `break`
- **现象**: delegation.model 被正确更新，但 delegation.provider 保持 deepseek 不变
- **修复**: 删除 `break`，让循环继续处理 `provider:`、`api_key:` 等字段

### Bug 4: HERMES_HOME fallback 指向 `~/.hermes`
- **位置**: freerouter.py 第 31 行
- **修复**: `os.path.expanduser("~/AppData/Local/hermes")`
- **影响**: 无 Hermes 进程时（独立运行/cron），会打到旧的 `~/.hermes/config.yaml`

## Web UI 免费模型同步

Freerouter `sync_webui_free_models()` 自动更新 Web UI config，详见 `references/webui-model-sync.md`。

## 双 config.yaml 问题

Windows 上两个 config 可能并存：
- `~/AppData/Local/hermes/config.yaml` ← **活跃配置**（Hermes 实际读取的）
- `~/.hermes/config.yaml` ← **残留旧配置**（可能被 Freerouter 误改）

审计时如果 `~/.hermes/config.yaml` 存在且内容比 `AppData/Local/hermes/config.yaml` 旧，应立即删除。

```bash
# 删除残留
rm ~/.hermes/config.yaml
```

## 最终 config 状态（2026-06-23 审计后）

Provider 策略：
- **主模型**: `model.provider: deepseek` — 直连 DeepSeek，不被 Freerouter 触碰
- **压缩**: `aux.compression.provider: deepseek` — 用直连提供稳定快速的压缩
- **视觉**: `aux.vision.provider: openrouter` — 免费模型 `openrouter/owl-alpha`
- **子代理**: `delegation.provider: openrouter` — 免费模型 `openrouter/owl-alpha`
- **后备**: `fallback_providers[0].provider: xiaomi` — 主/OpenRouter 都挂了时的兜底
- **其余所有 auxiliary**: `auto` — 让 Hermes 自动选最优

```yaml
model:
  default: deepseek-v4-flash     # 主模型直连，Freerouter 不改
  provider: deepseek

auxiliary:
  compression:
    model: deepseek-v4-flash
    provider: deepseek
  vision:
    model: openrouter/owl-alpha  # ← Freerouter 更新
    provider: openrouter

delegation:
  model: openrouter/owl-alpha    # ← Freerouter 更新
  provider: openrouter           # ← Freerouter 更新

fallback_providers:
  - model: mimo-v2.5-pro
    provider: xiaomi

tools:
  tool_search:
    enabled: on                  # 强制开启
    threshold_pct: 3             # 3% × 1M = 30K < ~36K MCP tools
```

Web UI 模型可见性：仅 OpenRouter 免费模型（自动同步 298+ 个 ≥128K 模型）

## 审计检查清单

```bash
# 1. DRY_RUN 默认值
grep "DRY_RUN" ~/.hermes/scripts/freerouter.py | head -1
# 期望: DRY_RUN = os.environ.get("DRY_RUN", "false")

# 2. HERMES_HOME fallback
grep "HERMES_HOME" ~/.hermes/scripts/freerouter.py | head -1
# 期望: os.path.expanduser("~/AppData/Local/hermes")

# 3. 双 config.yaml 残留
ls ~/.hermes/config.yaml 2>/dev/null && echo "STALE - DELETE" || echo "CLEAN"

# 4. model.default 未被 Freerouter 改动
python -c "
import yaml
c = yaml.safe_load(open('C:/Users/Administrator/AppData/Local/hermes/config.yaml'))
m = c['model']
d = c['delegation']
v = c['auxiliary']['vision']
ts = c['tools']['tool_search']
print(f'main: {m[\"default\"]} via {m[\"provider\"]}')
print(f'del:  {d[\"model\"]} via {d[\"provider\"]}')
print(f'vis:  {v[\"model\"]} via {v[\"provider\"]}')
print(f'tool_search: enabled={ts[\"enabled\"]}, threshold={ts[\"threshold_pct\"]}')
"
# 期望: main=deepseek-v4-flash/deepseek, del=openrouter/owl-alpha/openrouter, vis=openrouter/owl-alpha/openrouter, tool_search=on/3
```

## 已知限制
- Windows 上 gateway restart 的 `pkill` 会失败（无害，只是 log warning）。Config 变更下次新会话生效。
- Cron job id: `af1e04ce8fe1`，名称: Freerouter，每天 06:00，deliver: local（只写 config + 发 Telegram）
