# 棠溪分析卡 · 主模板 v8.0（叙事风格 · Telegram适配）

定位：叙事驱动，结构清晰，信息完整。每行不受38字符限制但保持紧凑。

## 权威铁律

① 每次出卡前必须先读取本文件。
② 价格反引号；状态仅 A做多/A做空/B等待/X禁做。
③ R:R 底线 1:2；不达标标 ⚠。
④ 单笔 ≤ 1%余额，10U 硬上限。
⑤ 完整卡 ≤ 35 行 · 极简卡沿用旧格式。
⑥ 分隔线 `━━━━━━━━━━`（Telegram 友好）。

---

## 完整卡（叙事风格）

```
`{SYMBOL}` 日内分析 · {STATUS}

━━━━━━━━━━

现价 `{PRICE}` ({CHG}%) ｜ 高 `{HIGH}` 低 `{LOW}`

━━━━━━━━━━

① 今日结构

{PREV_STRUCTURE}

关键路径：
{KEY_PATH}

{DISPLACEMENT_TEXT}

━━━━━━━━━━

② 关键位

— 阻力 —
R1: {R1_RANGE} — {R1_DESC}
R2: {R2_RANGE} — {R2_DESC}

— 支撑 —
S1: {S1_RANGE} — {S1_DESC}
S2: {S2_RANGE} — {S2_DESC}
S3: {S3_RANGE} — {S3_DESC}

━━━━━━━━━━

③ 量价分析

— {CVD_ABSORPTION}
— {TICKER_SUMMARY}
— {VOLUME_PATTERN}

━━━━━━━━━━

④ 交易方案

{PLAN_STATUS} {DIRECTION_EMOJI}

— A 方案（{PLAN_A_LABEL}）： {PLAN_A_DESC}
  入场 `{ENTRY_A}` 止损 `{STOP_A}` 止盈 `{TARGET_A}` R:R 1:{RR_A}
— B 方案（{PLAN_B_LABEL}）： {PLAN_B_DESC}
  入场 `{ENTRY_B}` 止损 `{STOP_B}` 止盈 `{TARGET_B}` R:R 1:{RR_B}

防守： {DEFENSE_LINE}
仓位： {POSITION} 风险 {RISK}U {LEVERAGE}

━━━━━━━━━━

⑤ 综合评分

流动性扫荡 · {SWEEP_STATUS}
CVD确认 · {CVD_STATUS}
动能位移 · {DISPLACEMENT_STATUS}
Kill Zone · {KILL_ZONE_STATUS}
多级共振 · {CONFLUENCE_STATUS}
风控门 · {RISK_GATE_STATUS}
数据质量 · {DATA_GRADE}

总结： {ONE_LINE_SUMMARY}
```

---

## 极简卡（沿用 ≤8行）

```
◷ {TIME} · {SYMBOL} · {STATUS} · {BIAS}

现价 `{PRICE}` 高 `{HI}` 低 `{LO}`
{NEAREST_LEVEL} 距 {DIST}%

—— A {DIR_A} ——
入场 `{ENTRY_A}` 止损 `{STOP_A}`
止盈 `{TARGET_A}` 1:{RR_A}

—— B {DIR_B} ——
入场 `{ENTRY_B}` 止损 `{STOP_B}`
止盈 `{TARGET_B}` 1:{RR_B}

风控 {RISK}U {LEVERAGE}
```

---

## 警报（≤8行 · 触发时）

```
🚨 {SYMBOL} · {STATUS} · `{PRICE}`

{TRIGGER_LEVEL} 距 {DIST}%
CVD {CVD} · Taker {TAKER} · 引擎 {MODEL}

—— A {DIR_A} ——
入场 `{ENTRY_A}` 止损 `{STOP_A}`
止盈 `{TARGET_A}` 1:{RR_A}

—— B {DIR_B} ——
入场 `{ENTRY_B}` 止损 `{STOP_B}`
止盈 `{TARGET_B}` 1:{RR_B}

风控 {RISK}U {LEVERAGE} · {PROT}
```

---

## 资产专属

| 品种 | 平台 | 杠杆 | 单位 | Kill Zone |
|------|------|------|------|-----------|
| BTC | BINANCE | 100x | 张 | 24/7 |
| XAU | EXNESS | 1000x | 手 | London+NY |
| 山寨 | BINANCE | 20x | 个 | 跟随BTC |
