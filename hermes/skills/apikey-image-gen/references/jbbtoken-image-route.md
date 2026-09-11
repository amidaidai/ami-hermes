# JBBToken 生图路由排查与修复

适用场景：用户说 JBB/JBBToken 生图不生效，或 Hermes `image_generate` 没有走 JBB 的 `gpt-image-2`。

## 关键判断

| 检查 | 结论含义 |
|---|---|
| `custom_providers` 里只有 `jbbtoken.cn生图` | Web UI media endpoint 仍可能找不到，因为该 endpoint 默认找 `fun-codex` |
| JBB `/v1/models` 能看到 `gpt-image-2` | JBB key 与模型权限正常 |
| 直接 `POST /v1/images/generations` 成功 | JBB 生图服务正常，问题在 Hermes 路由/环境 |
| `image_generate` 报 `OPENAI_API_KEY not set` | 当前 Agent 进程没有读取 `.env`，或原生 OpenAI image plugin 未配置 |
| 改完 `.env` 后仍失败 | 需要重启 Hermes Studio/Gateway/新会话，运行进程不会自动继承新环境 |

## 修复模式

1. 保留原 `jbbtoken.cn生图` custom provider。
2. 同步新增/更新 `custom_providers` 中的 `fun-codex`，指向同一个 JBB base_url 与 api_key，供 Web UI `/api/hermes/media/apikey-image-generate` 使用。
3. 配置原生 Hermes 生图：

```yaml
image_gen:
  provider: openai
  model: gpt-image-2-low
  openai:
    model: gpt-image-2-low
```

4. 写入 `.env`，让 OpenAI image plugin 实际走 JBB OpenAI-compatible endpoint：

```env
OPENAI_API_KEY=<JBB image key>
OPENAI_BASE_URL=https://jbbtoken.cn/v1
OPENAI_IMAGE_MODEL=gpt-image-2-low
```

5. 重启 Hermes Studio/Gateway 或开启新会话，再调用 `image_generate`。

## 验证

直接 provider 验证：

```python
POST https://jbbtoken.cn/v1/models
# 应返回 gpt-image-2

POST https://jbbtoken.cn/v1/images/generations
{
  "model": "gpt-image-2",
  "prompt": "A tiny simple icon on white background",
  "size": "1024x1024",
  "n": 1,
  "quality": "low"
}
# 应返回 data[0].b64_json
```

Hermes 路由验证：

```python
from agent.image_gen_registry import get_active_provider
# 重启/新进程后应为 openai，且 is_available() 为 True
```

## 注意

- 这是“路由没接上/环境没重载”，不要误判为 JBB 挂了。
- 不要把 redacted 的 key 从工具输出复制回配置；必要时用二进制/hex/字符码方式写入。
- Web UI 本地端口不可达时，不能依赖 media endpoint；优先检查原生 `image_generate` 路由。