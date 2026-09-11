# 监控警报卡格式对齐分析卡 v6.8（行情守望 v7.4）

监控警报卡（`行情守望.py` 的 `render_message`）必须和分析卡 v6.8 模板
（`references/master-template-v68.md`）字段顺序、序号语义、风格完全一致。
本文件锁定该对齐标准 + 本次（2026-06-19）三处根因修复。

## 字段顺序与圈号语义（与分析卡 v6.8 严格对齐）

```
①品种 ②周期 ③现价 ④状态(A/B/X) ⑤模型 ⑥触发位(主体) ⑦订单流 ⑧衍生 ⑨引擎/冲突 ⑩风控
```

- ④状态、⑤模型 从 `block["latest_setup"]` 真实读取；`latest_setup` 缺失时
  ④降级为 `situation_text(tier)`（如"价格已贴近或触发关键位"），不强行显示 A/B/X。
- ⑥触发位下的多个位用 `▸` 前缀子项，**不占圈号编号**（避免子项与头部圈号撞车）。
- 头部字段（①-⑥）固定显示；衍生信号区（⑦-⑩，CVD/Taker/多空/衍生/引擎/冲突/风控）
  用 `extras` 列表 + `if val:` 判断——有数据才显示，无数据整段跳过，**不输出"无"或空行**。

## 圈号统一计数器（核心模式）

不要硬编码 ①②③ 或在衍生区写死 `n=7`。用统一计数器：

```python
_n = [0]
def _seq():
    _n[0] += 1
    return SEQ_NUMS[_n[0] - 1]   # SEQ_NUMS = ①②③④...
```

头部和衍生区共用同一个 `_seq()`，圈号全程连续不跳不撞。
`▸` 子项不调用 `_seq()`。
验证标准：XAU 卡 ①-④ + ▸ + ⑤-⑨ 连续；BTC 卡 ①-⑤ + ▸ + ⑥-⑫ 连续。

## 风格（与分析卡/电报富文本偏好一致）

- 头部**去掉装饰 emoji**（🔴🔵🟡），改纯文字标识紧急度：
  `{symbol} · 紧急关键位` / `{symbol} · 关键位触发` / `{symbol} · 接近计划位`。
- 价格用反引号；全局 `—` 分隔；禁 `|`；禁装饰 emoji。
- CVD `?` / None / 空 / "不适用" 四种情况统一兜底为可读文案
  （`_cvd_display` → "估算中 · {质量等级}"），不裸露符号。
- 失效规则英转中（`zh_invalid`）。

## 三处根因修复（2026-06-19）

### 1. 65/68 推送门槛死区（P0）
- **现象**：日志 `降噪不推送 XAUUSD warning: 位信66% · 数据A级`——66 分位被永久静默。
- **根因**：`push_allowed` 中 warning medium 分支和 info 分支硬编码 `score >= 68`，
  但函数入口的常量 `MIN_WARNING_LEVEL_SCORE = 65`。两个数字打架：
  位信 65-67 的位进得了 warning 池（≥65）却推不出去（<68），形成 65/68 死区。
- **修复**：两个分支的 `score >= 68` 全部改为 `score >= MIN_WARNING_LEVEL_SCORE`。
- **教训**：推送门槛只认一个常量 `MIN_WARNING_LEVEL_SCORE`，禁止任何分支另写裸数字。

### 2. 两套代码路径并存（架构债）
- `render_message`（监控实际调用·原本简陋）vs `monitor_display.py` 的 `format_level_block`
  （含完整位信/距离/失效信息·从未被监控调用）。
- 格式不统一的根因就是监控只走了简陋的那条路径。
- 本次直接在 `render_message` 重写实现对齐；长期可考虑两路合一，但短期优先级低。
- **排查启示**：监控显示异常时，先确认监控到底调用的是哪个格式化函数，别改错文件。

### 3. format_hit 子项撞圈号
- 原 `format_hit` 用 `seq_n = SEQ_NUMS[...]` 给每个触发位编圈号，与头部圈号计数器冲突。
- 改为 `▸` 前缀子项，彻底脱离圈号体系。

## 重启监控（环境陷阱·已在 memory）

改完代码必须重启才生效，且必须用 hermes venv 的 python：

```
C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
```

不可用 uv 的 python（`AppData\Roaming\uv\python\...`，缺 `requests` 会崩）。
流程：杀 `data/monitor.lock` 里的 pid → 删 lock → background 启动 → 查
`monitor_heartbeat.json` 确认新 pid 持锁 + 状态 running + 心跳新鲜。
git-bash 里 `tasklist` 过滤用 `//FI`（单 `/` 被 MSYS 当路径）。

## 验证清单

- [ ] 模块 import OK
- [ ] BTCUSDT + XAUUSD 两张卡圈号连续、`▸` 子项不占号
- [ ] CVD `?` 显示"估算中 · {等级}"
- [ ] 状态/模型从 latest_setup 正确填充，缺失时优雅降级
- [ ] 心跳 PID 变更 + 状态 running + monitor.log 出现新版本横幅（v7.4）
