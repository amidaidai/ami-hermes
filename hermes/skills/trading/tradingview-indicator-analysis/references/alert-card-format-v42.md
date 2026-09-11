# 告警/决策卡格式铁律 v4.2（2026-06-22 锁定）

棠溪在 v4.0→v4.2 迭代中两次纠正格式偏好。以下铁律适用于所有输出。

## 格式铁律

### 首行
方向标注在最前：`↑做多/↓做空/○等待/×禁做 {grade} {price} · VWAP {vwap} · {BJT时间}`

### 时区（2026-06-28 用户纠正 P0）
**始终使用北京时间（BJT, UTC+8）**。TV截图显示的是UTC时间，必须在文字描述中转换为BJT。
告警首行、分析卡时间戳、截图说明中的时间全部为BJT。不得再出现UTC标注或"UTC"字眼。

### 正文
- ①②③ 中文编号 · 冒号对齐
- 一行一条 · 每行 ≤ 38 字
- 价格反引号 `65,000`
- 多部分 ` · ` 分隔

### 禁止项
- ❌ 表格 / `|` / emoji（仅 ↑↓○× 箭头例外）
- ❌ Markdown 加粗
- ❌ `═══` 分隔线
- ❌ 说明文字/标题前缀
- ❌ 英文术语（Taker→主动买卖, OI→持仓, LS→多空比, KillZone中文）
- ✅ 保留英文：VWAP/CVD/EMA/ADX/Funding/Spot/ATR

### 截图
- `capture_screenshot(region="full")` — 含价格轴+CVD
- `MEDIA:` 路径发首行

### 输出
- 只卡片正文，不要说明文字
- 自然收尾不加决策提示行

## 示例

```
↑做多 A 65,042 · VWAP 64,550 · 23:15 BJT
① 方向：偏多 · 处理：回踩做多
   趋势 7/1 · 反转 5/2
② DMI ADX 34 · CVD +11,696 · 顺空确认
③ VWAP 64,550 — VAH 65,043 — VAL 63,841
④ 位置：VA内 · VWAP上方 · 主动买卖 1.30 · 持仓 101K
⑤ 回踩做多 · EMA 65,084/64,893 · 多头排列
守VWAP上方做多，目标VAH
```

## 实现

- `btc_alert_watch_v3.py::build_decision_card()` — Python决策卡
- `btc_push_cron.py` — 异步推送

## 历史

- v3.x: `══ BTC · price · VWAP ══` + emoji
- v4.0: `↑做多 A price · VWAP` + 🟢🟡色标
- v4.2: `↑做多 A price · VWAP` + ①②③ + 禁emoji/表格
