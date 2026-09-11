# 视觉质量路由复盘（2026-07-11）

## 触发背景

用户要求整体模型路由优先 Ollama Pro，但随后明确纠正：视觉模型必须使用质量好的模型，不能为了供应商统一而降级。

## 关键发现

- 把 `nvidia/nemotron-3-ultra-550b-a55b:free` 放进视觉槽位是错误的；真实图像调用返回 `404 No endpoints found that support image input`。
- 文本请求“只回复 OK”成功，不能证明图像输入可用。
- catalog 中应检查 `modalities.input` 是否包含 `image`；模型参数量、上下文长度、工具调用能力均不能替代此检查。
- OpenRouter 上的高质量 Gemini Pro 可能因通道额度/支付状态暂时不可用；这是通道问题，不是模型能力问题。
- Nous 托管通道可解析到 `google/gemini-3.1-pro-preview`，适合作高质量主视觉；Ollama Cloud 的 Gemini Flash、Qwen VL 可作为备用。

## 推荐配置形态

```yaml
auxiliary:
  vision:
    provider: nous
    model: google/gemini-3.1-pro-preview
    timeout: 180
    download_timeout: 30
```

模型名随 catalog 更新时可以变化，长期不变的是选择原则：主视觉质量优先，备用再考虑 Ollama 成本。

## 必做验证

1. 调用 `resolve_vision_provider_client()`，核对最终 provider、model、client。
2. 用已知答案的真实图表发送 `image_url` 多模态请求。
3. 提示词要求输出至少三个可核对字段，例如：品种、现价、CVD方向。
4. HTTP 200 但字段识别错误，仍判失败。
5. 修改配置后重启 gateway 或开启新会话，避免旧进程继续使用旧视觉模型。

## 错误判读

| 现象 | 正确解释 |
|---|---|
| 文本 OK、图像 404 | 模型/端点不支持该图像请求格式，不能作视觉后端 |
| payment/credit error | 当前提供者通道不可用；不等于模型无视觉能力 |
| resolver 返回 client=False | 配置、凭证或健康熔断导致当前不可路由 |
| 图像调用成功但只识别模糊品种 | 质量不达标，应继续比较更强视觉模型 |
