# TV 实时数据注入架构 v9.6

## 问题

`tv_dmi_cache.json` 由 cron 的 `tv_data_bridge.py`（Node.js CLI）写入，但 Node CLI 输出的数据格式不包含 `poc`/`vah`/`val`/`action_grid` 字段。cron 每次运行会覆盖 agent 上下文写入的结构化数据。

## 双缓存架构

```
agent 上下文（TV MCP 直连）写入  →  data/tv_live.json       ← 优先级最高
cron tv_data_bridge.py 写入      →  data/tv_dmi_cache.json  ← 回退
```

### tv_live.json 格式（agent 手工 dump）

```json
{
  "timestamp": "2026-06-29T22:55:00+08:00",
  "symbol": "BINANCE:BTCUSDT.P",
  "fresh": true,
  "action_grid": {
    "结论": "B空 轻仓",
    "方向": "偏空 · 走弱 · 折价",
    "进场": "反抽DO 59550.2",
    "止损": "—",
    "目标": "↓上周 低 58030.0",
    "核对": "HTF✓ EMA✓ CVD✓ 位置✓ 位移✓",
    "磁吸↑": "--",
    "磁吸↓": "上周 低 58030.0"
  },
  "poc": 59656.53,
  "vah": 60164.95,
  "val": 59360.94,
  "week_high": 60543.3,
  "week_low": 58888,
  "prev_week_low": 58030,
  "lines": [60758.3, 60543.3, 60325, 60164.95, ...]
}
```

### auto_card 读取逻辑

```python
# 优先 tv_live.json（agent 现场），回退 tv_dmi_cache.json（cron）
for p in [live_path, cache_path2]:
    c2 = json.loads(p.read_text())
    if c2.get("fresh") and c2.get("poc"):
        break  # 找到了有效数据
```

## 注入效果

读取到有效 TV 数据后，auto_card 会：
1. 填充 `klines["D"]` 日线周期（之前显示"待刷新"）
2. 将 `poc`/`vah`/`val` 注入到 4h/1h/15m/5m 各周期
3. 用 `action_grid["方向"]` 标明结构方向

结果：D 周期从 `| D | 待刷新 | 待刷新 | 缺现场数据，降级参考 |` 变为 `| D | TV现场 POC 59657 | VAH 60165 VAL 59361 | 偏空·走弱·折价 |`

## 脚本

- `scripts/tv_live_dump.py` — agent 上下文手工 dump TV 数据到 `tv_live.json`
- `scripts/tv_data_bridge.py` — cron 调 Node CLI 写 `tv_dmi_cache.json`（v9.6 扩展了 poc/vah/val/action_grid 提取）
- `hermes/scripts/auto_card.py` — 注入逻辑在 TV DMI 段之后、Protections 段之前

## 已知限制

- tv_live.json 仅由 agent 上下文写入（需 TV MCP 连接），cron 无法自动刷新
- tv_data_bridge.py 的 poc/vah/val 提取依赖 Node CLI 输出的 label 格式（需含 "POC:" "VAH:" "VAL:" 标签），非所有品种都有
- XAUUSD 的 TV SVP 数据完全不返回（独立架构限制，见 xau-tv-svp-limitation.md）
