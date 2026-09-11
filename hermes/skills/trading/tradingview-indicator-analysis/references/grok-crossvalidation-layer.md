# Grok 交叉验证层 & xAI OAuth 配置

## 实现状态 ✅ 已上线 (2026-06-18)

**`call_grok_validation()` 已集成到 `multi_model_engine.py` (v1.3)**。不再是文档-only 的可选层——引擎每次运行自动调用 Grok 做交叉验证。

### 代码入口

- **文件**: `D:/Hermes agent/hermes/scripts/multi_model_engine.py`
- **函数**: `call_grok_validation(symbol, merged, model_results, price, data)` (L420-L500)
- **Token 源**: `_read_grok_token()` → 从 `%LOCALAPPDATA%/hermes/auth.json` 读取 `xai-oauth.access_token`
- **触发条件**: 仅 `global_conf > 0.5` 时调用（避免低置信场景浪费 token）
- **超时**: 8s
- **输出格式**: `{agree, divergence, blindspot, grok_direction, grok_confidence}`

### 集成流

```
multi_model_engine.py __main__:
  ① check_event_ban()
  ② run_all_models() → merge_directions()
  ③ call_grok_validation()  ← 新增
     → agree=True: merged.global_confidence += 0.05
     → agree=False: merged.action = "⚠Grok分歧 · {action}"
  ④ log_prediction() → 预测追踪
```

### 实测验证

```
XAUUSD @ $4324.68 (2026-06-18):
  引擎: 偏空 · 0.900 (EMA趋势单模型0.9带偏)
  Grok: 偏多 · 0.720 ← 正确指出4长1空信号失衡
  Divergence: "多模型信号严重分歧（4长1空），引擎却给出0.900极端空头置信度"
  Blindspot: "DXY仅100.25处于低位，黄金易形成流动性回收后的多头趋势"
  最终: ⚠Grok分歧 · 可交易 · 常规仓
```

### 错误处理

- Token 缺失 → `{error: "无token"}`，不阻塞
- API 超时/网络错误 → `{error: str(e)}`，不阻塞
- Grok 返回非 JSON → 解析失败 → `{error: str(e)}`，不阻塞
- global_conf ≤ 0.5 → `{skipped: "置信过低"}`，跳过调用

## xAI OAuth 配置（一劳永逸）

xAI Grok API 支持通过 X 账号 OAuth 授权使用，无需单独申请 API Key。

### 配置步骤

1. 运行自定义脚本生成授权链接：
   ```bash
   cd "D:/Hermes agent"
   python hermes/scripts/xai_oauth.py
   ```
2. 打开输出的 URL → 登录 X → 授权
3. 把授权页面显示的代码粘贴给 agent
4. 脚本自动交换 token 并写入 `auth.json` (`providers.xai-oauth`)

### 已知问题

- **`hermes auth add xai-oauth --manual-paste` 在非交互式终端不可用**：每次运行生成新 PKCE 对，无法跨命令匹配。替代方案：用 `D:/Hermes agent/hermes/scripts/xai_oauth.py` 两阶段脚本（gen mode + exchange mode），PKCE 状态存文件。
- **OAuth token 有效期 ~6h**：Hermes 内置 refresh token 自动续期，正常使用无需关心。
- **403 tier denied**：部分 X 账号没有 SuperGrok 权限，OAuth 返回 403。此时需要 XAI_API_KEY 降级。

### 配置确认

```bash
# 查看 token 状态
python -c "import json; d=json.load(open('/c/Users/Administrator/AppData/Local/hermes/auth.json')); x=d['providers']['xai-oauth']; print('AT:',bool(x['access_token']),'RT:',bool(x['refresh_token']))"

# 测试调用
curl -s https://api.x.ai/v1/models -H "Authorization: Bearer $(python -c "import json; print(json.load(open('/c/Users/Administrator/AppData/Local/hermes/auth.json'))['providers']['xai-oauth']['access_token'])")"
```

## Grok 模型选择

### 可用模型（xAI API）

| 模型 | 速度 | 推荐场景 |
|------|------|----------|
| `grok-4.20-0309-non-reasoning` | ⚡ 0.9s | 🏆 交易分析首选——快速响应，质量稳定 |
| `grok-4.20-0309-reasoning` | 7.5s | 深度推理、复杂结构判断、复盘 |
| `grok-4.3` | 5.9s | 备选，老版本 |
| `grok-4.20-multi-agent-0309` | — | 多智能体协作 |
| `grok-build-0.1` | 11.5s | 开发构建用，不推荐用于分析 |
| `grok-imagine-image/image-quality` | — | 图片生成 |
| `grok-imagine-video/video-1.5` | — | 视频生成 |

### 调用方式

```python
import json, urllib.request

# 读 token
with open(auth_json_path) as f:
    token = json.load(f)["providers"]["xai-oauth"]["access_token"]

# 调用 API
data = json.dumps({
    "model": "grok-4.20-0309-non-reasoning",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.3,
}).encode()

req = urllib.request.Request(
    "https://api.x.ai/v1/chat/completions",
    data=data,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
)
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())
```

## Grok 验证层工作流

在标准分析管线（Step 1-5）完成后，可选执行 Step 6 Grok 验证：

```
输入：Step 5 输出的分析卡 + 原始数据
输出：置信修正 + 分歧标记 + 补充见解

流程：
  1. 从 auth.json 读 xai-oauth token
  2. 构建 prompt：包含 TV 指标值 + 决策表 + 引擎结论
  3. 调 grok-4.20-0309-non-reasoning
  4. 对比 Grok 结论 vs 引擎结论：
     → 一致：置信 +5%，正常出卡
     → 分歧：打标记「Grok分歧⚠」，人为关注后再出卡
  5. Grok 的叙事/补充见解写入「Grok 补充视角」段落（可选项）
```

### Prompt 模板

```
你是 Grok，交易分析专家。分析 {品种} {周期} 图表数据：

TradingView 指标：
- VWAP: {value} | EMA9: {value} | EMA21: {value} | EMA34: {value} | EMA55: {value}
- CVD: {value} (斜率 {value}) | POC: {value}
- VAH: {value} | VAL: {value} | DO: {value}

决策表: {等级} | {处理} | {背景} | {位置} | {量能} | {CVD} | {执行} | {风控}

OHLCV: 现价 {price} | 区间 {low}→{high} | 变化 {change}% | 均量 {vol}

引擎结论: {方向} | 置信 {confidence}/5 | 原因 {reason}

输出:
① 环境分析
② 关键位(支撑/阻力)
③ 博弈判断(三源一致性)
④ 操作建议(方向/入场/止损/仓位)
⑤ 风控要点

额外：【Grok 补充视角】你对引擎结论是否认同？有什么补充见解？
```

### 注意事项

- 只在出完整分析卡时运行，不要每张 mini 卡或骨架卡都跑
- 批量扫描场景不跑 Grok 验证（token 成本 vs 收益不划算）
- 重点关注分歧场景：Grok 与引擎方向相反→必须人工过目
- 不替换原有分析流程，只作上层验证
