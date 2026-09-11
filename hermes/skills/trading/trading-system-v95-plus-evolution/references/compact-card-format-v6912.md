# 极简决策卡格式规范 v6.9.12

## 触发条件

当 `status ∈ (B等待, X禁做)` 且 `_near_key_level(klines, price, threshold_pct=0.4)` 返回 True 时触发极简卡。
否则输出完整卡（78行）。

## 格式（10行固定）

```
◷ {MM-DD HH:MM} · {SYMBOL} · {平台} · {model_id} · 4h{方向} · {bias}
③ `{price}` · 高 `{high}` · 低 `{low}`
{KEY_NAME} {level} ← {距离描述}
CVD {方向} · Taker {方向} {ratio} · Funding {rate}
5m {sweep} · 15m {15m描述} — 低周期触发
→ {破/守}{level}：{多/空} 止损`{stop}` 止盈`{target}` R:R 1:{rr}{rr_note}
→ {反向}{level}：{反向} 止损`{stop_b}` 止盈`{target_b}` R:R 1:{rr_b}{rr_b_note}
风控：{weekend_tag}{risk}U上限 · {leverage} · {protections} · {community_tag}
—— 决策：你来选方向——
```

## 硬规则

### 止损止盈
- 统一使用 `_calc_stop_target_atr(price, direction, klines, symbol)` 
- ATR×2 夹层 + 结构位锚定（VAH/POC/VAL/VWAP/EMA）
- 0.3% 以内关键位视为噪音跳过
- 无结构位时兜底 0.8%（非旧版 3%）
- R:R ≥ 2.0 → 正常显示
- R:R < 2.0 → 标注 `⚠R:R不足`（不伪造数字）

### AB预案对称铁律（棠溪亲自纠正）
- Plan A 和 Plan B 必须字段完全一致
- 每条预案包含：方向/入场/止损/止盈/仓位/风险/失效/复查
- Telegram 推送也必须 AB 对称
- 不可缩写备选方案

### 4h 继承
- `_primary_plan_bias(bias_cn, k4h_direction)` 
- 4h 偏空 → 强制空头优先（引擎中性时也否决）
- 4h 偏多 → 强制多头优先
- Header 显示 `4h{方向}`

### 低周期触发
- 5m：`_sweep_state(k5m, merged)` → 扫荡状态
- 15m：`k15m.description` → 量价描述

### R:R 诚实标注
- 市场结构不给 1:2 时标注 `⚠R:R不足`
- 不伪造数字、不扩大止盈来凑 R:R
- R:R 不足是系统的保护信号，不是 bug

## 踩过的坑

1. **固定百分比止损**（v6.9.10）→ 3% 止盈=1,920点→波段目标，棠溪做日内 5m/15m 完全不适配。改为 ATR 锚定。
2. **预案B缩写** → Telegram 推送时偷懒缩写 Plan B→棠溪指出"备选为什么不是同一个格式"。AB必须完全对称。
3. **B等待留空** → "待确认后设定""待确认后计算"→棠溪要真实数字。改为 `_calc_stop_target_atr()` 始终计算。
4. **R:R 造假** → 旧版 `_plan_targets()` 用 `stop_dist × 2.0/3.0` 固定倍数，永远能凑出 1:2+。新系统诚实标注不足。
5. **Grok 定位错** → "Grok一致|置信+0.05"→暗示 Grok 是信号确认器。改为"Grok: 催化剂已验证"→市场热点验证器。
6. **搜索定位错** → "搜索情绪"→改"市场热点"。

## 相关代码

- `hermes/scripts/auto_card.py` → `_compact_card()`（极简卡渲染）
- `hermes/scripts/auto_card.py` → `_calc_stop_target_atr()`（止损止盈计算）
- `hermes/scripts/auto_card.py` → `_primary_plan_bias()`（4h方向继承）
- `references/master-template-v68.md`（v6.9.11 主模板）
