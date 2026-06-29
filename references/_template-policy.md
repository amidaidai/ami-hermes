# 棠溪统一模板策略 v1 — 2026-06-23 锁定

## 核心原则

**只有一个权威模板。** 所有其他模板文件已归档或废弃。

## 权威模板

| 文件 | 用途 | 状态 |
|------|------|------|
| `references/master-template-v68.md` | **完整分析卡** — 叙事风格·5段 | ✅ 权威 |
| `references/btc-analysis-compact-template.md` | **BTC精简卡** — 6段·30秒决策 | ✅ 补充 |
| `references/monitor-template.md` | **监控警报卡** — ≤8行·触发时 | ✅ 补充 |

## 已归档/废弃

| 文件 | 状态 | 去向 |
|------|------|------|
| `references/master-analysis-template.md` | ❌ 废弃 | 已删除 |
| `references/template-v69-execution-protocol.md` | ❌ 废弃 | 不存在 |
| `references/template-v69-machine-fields.md` | ❌ 废弃 | 不存在 |

## 出卡铁律

1. **方向首行：** `↑做多/↓做空/○等待/×禁做`
2. **编号格式：** `①②③` 冒号对齐 · 每行 ≤38字 · 价格反引号
3. **禁：** 表格/`｜`/emoji(仅↑↓○×例外) · 分隔线 · 粗体 · 说明前缀
4. **术语：** 英文保留 VWAP/CVD/EMA/ADX/Funding/ATR · 其余中文
5. **截图：** region=full 含价格轴+CVD · MEDIA 直发首行
6. **自然收尾：** 不加提示行（如 `—— 你来选方向 ——`）
7. **脚本纪律：** cron stdout 纯 ASCII · 中文只走 Telegram API

## 格式速查

### 完整卡（master-template-v68.md）
```
`{SYMBOL}` 日内分析 · {STATUS} · {BIAS}
现价 `{PRICE}` · 高 `{HIGH}` 低 `{LOW}`

① 今日结构  ② 关键位  ③ 量价分析  ④ 交易方案  ⑤ 综合评分
```

### 精简卡（btc-analysis-compact-template.md）
```
**① 品种 · 方向**   **② 关键位**   **③ 现价 · 数据· 量能**
**④ 入场条件**   **⑤ 核对清单**   **⑥ 预案**
```

### 警报卡（monitor-template.md）
```
🚨 {SYMBOL} · {STATUS} · `{PRICE}`
{TRIGGER_LEVEL}  距 {DIST}%
CVD {CVD} · Taker {TAKER} · 引擎 {MODEL}
—— A {DIR} ——   —— B {DIR} ——
风控 {RISK}U
```
