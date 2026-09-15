# 中转能力矩阵第二轮：reasoning×tools 的「非 none/medium」分支 + 视觉槽解耦（2026-09-15 BJT 实证）

用户问「GLM 5.3 Flash 和 DeepSeek V4.1 Flash 哪一个好（在我们这个系统）」。
**默认只读**：全程未改 `config.yaml`；推荐用的验证在沙箱 `HERMES_HOME=$LOCALAPPDATA/Temp/h2h_home`（复制 config/.env/auth.json）里做。

## 1. 结论形状（先给槽位，再给证据）

| 槽位 | 选谁 | 判据 |
|---|---|---|
| 主模型 | `custom:b.ai` / `deepseek-v4.1-flash` | 工具 1.2–1.7s、reasoning 参数全兼容、会话实测 n=3541 均值 7.4s |
| 视觉槽 | `glm-5.3-flash`（要读图细节/解耦时）或保持 deepseek（要快） | glm 真图 4/4 全对且 71–153s/次；deepseek 2/4 对但 3–63s/次 |
| 非中转交叉验证 | `xai-oauth` / `grok-4.6` | 唯一不经过中转的判断源 |
| 免费池 | 仍只做兜底，不进视觉槽 | 见主 SKILL 免费池章节 |

## 2. b.ai 的 reasoning 矩阵（2026-09-15 现场，带 tools 打两次）

`POST /v1/chat/completions`，`tools=[read_file]`，逐值探：

| 模型 | 省略 | none | minimal | low | medium | high | max |
|---|---|---|---|---|---|---|---|
| `glm-5.3-flash` | 200 | **400** | 未测 | 200 | **400** | 200 | 200 |
| `deepseek-v4.1-flash` | 200 | 200 | 未测 | 200 | 200 | 200 | 200 |

glm 的 400 文案（none 与 medium 同一句，**不要读成「关闭思考」才报错**）：

```
HTTP 400 The request is invalid: 该模型始终思考，不支持关闭思考；请使用 low、high 或 max。
```

**本机全局 `agent.reasoning_effort: medium`** → 一旦把 glm 设成主模型，主路径每条消息先 400（`logs/errors.log` 实测两条 08:32），Hermes 重试后才成功：白付一轮延迟，正是 gpt-6-astra 那一类「能力矩阵冲突」，不是路由写错、也不是模型不存在。

### 修法（沙箱实测，仅主路径有效）

```yaml
agent:
  reasoning_overrides:
    glm-5.3-flash: low      # 或 high / max；none|medium 会被 b.ai 400
```

- 该 override 只对**主对话路径**生效（`resolve_reasoning_config(cfg, model)`，`/model` 切换与 fallback 激活都会重解析；已实测主调用 400 消失）。
- **辅助槽 `auto` 不读它**：主模型设成 glm 时，`auxiliary.title_generation`（auto→主模型）依旧 400，且给它加 `auxiliary.title_generation.reasoning_effort: low` **也无效**——`agent/title_generator.py` 硬编码 `reasoning_config={"enabled": False}`，永远是「关闭思考」，而 glm 这类 always-think 模型必然拒。给 title 槽**钉一个非 always-think 模型**（如 deepseek）才消除 400：实测 errors.log 归零。
- 视觉槽不受影响：`auxiliary.vision = custom:b.ai / glm-5.3-flash` + 全局 medium + **无** reasoning_overrides → 视觉调用零 400（视觉路径不送那个参数）。

## 3. 真图夹具（含外部真值）

- 夹具：`tools/tradingview-mcp/screenshots/BTCUSDT_15m_20260915_081540.png`（1920×998，**浅色主题**）。
- 真值：`live chart_get_state` = `BINANCE:BTCUSDT.P` / `15` / studies = `SVP+ICT+VWAP+CVD`(主图叠加) + `Volume`(主图叠加，见图例「成交量 · BTC 17」) + `Volume Aggregated Spot & Futures`(独立副图)；价格 78,080.1（Binance 现货 08:15 1m 收 78,130，永续微差）。
- **副图真值 = 1 个（AggVol）**。三法交叉：左列图例裁剪（420px 全高 2x）、下半幅裁剪、100px 红网格标尺图（`grid100.png`）。
- 读图判分（同一张图）：`glm-5.3-flash` 4/4 全对并且正确指出「主图底部红绿量柱=叠加的 Volume，不算独立副图」；`deepseek-v4.1-flash` 2/4 对的副图数（另 2 次报「2 个：成交量、AggVol」），并 1 次连接错误。
- **浅色主题会把「找分隔线」的暗色启发式全部作废**：`rows brighter than median` 返回 0 行。浅色图要改为找「比邻行更暗」的局部极小值，或干脆用图例块计数，别用暗色主题的假设下结论。

## 4. 同题横评（房规 + 证据包 + 裁决陷阱；`--runs 3`）

预算：`max_tokens=1200` 时两个模型都 3/6 空 content（reasoning 吃光），**必须 ≥4000** 才拿得到卡面。

| 项 | deepseek-v4.1-flash | glm-5.3-flash |
|---|---|---|
| 延迟（均值/次） | 10.8s | 25.2s |
| 裁决正确（WAIT） | 3/3 | 3/3 |
| 三件套清空「无」 | 3/3 | 3/3 |
| 单一 ⭐ 语义 | 3/3（但两次把品种写成「观察候选」） | 3/3（观察候选编号，不占 ⭐） |
| 引用证据包外数字 | 无 | 无 |
| 点出数据缺口 | ATR/S0 缺失 | ATR/S0 缺失 **+ 发现证据包自相矛盾**（「收盘 78008.1 却在 78,000 下方」）|

教训：夹具里塞一个**内部矛盾**（收盘价与所述关键位方向相反）比只塞 S3 冲突更能分层——deepseek 照抄，glm 当场指出。做夹具时留这种可判分的小陷阱。

## 5. 现场其余事实

- b.ai 目录 47 个模型，两个 id 均在册；`/pricing`、`/v1/pricing`、`GET /v1/models/<id>` 全部 403 `HTTP node only allows access to inference API paths`，`/v1/models` 无价格字段 → **单价只能向用户要后台价目页，不许推断**。
- 上下文探测：`deepseek-v4.1-flash` 1,000,000；`glm-5.3-flash` 1,312,720（`custom_providers[].models` 里只登记了 deepseek 两个，glm 未登记但能被探测出来）。
- 会话日志延迟：deepseek n=3541 均值 7.4s / p50 5.4s；glm n=4 均值 9.1s（样本太小，只作参考）。探针延迟与真实会话分开报。
- 本机 `fapi` 域（`fapi.binance.com`）**403 Forbidden**（`/fapi/v1/premiumIndex`、`/futures/data/*` 全 403），而 `api.binance.com` 现货直连正常（0.25s）→ 夹具里的资金费率/OI/Taker 只能标为夹具常量，别写成实时值。

## 6. 可复跑脚本

- `outputs/probe_h2h_glm_ds.py`：目录 + 工具 shape + 横评 + 真图一次过（b.ai 直连，写 JSONL）。
- `outputs/probe_fixture_4000.py`：只跑横评，可传 `runs` 与 `max_tokens`。
- `outputs/probe_vision_repeat.py`：同图 N 次读图，自动判 symbol/tf/price/副图数。
