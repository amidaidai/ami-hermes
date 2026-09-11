# 推送告警格式 (btc_push_cron.py v6)

## v6: Simplified relay (2026-06-22)

v3.3 alert detector (`btc_alert_watch_v3.py` → `write_pending()`) produces a self-contained,
hierarchical card. The pusher reads → chunks → sends. No post-processing needed.

**What was removed from v5:**
- `---` separator filtering (no longer used)
- Direction annotation (`_infer_direction`, `_add_direction`) — format uses `+`/`-`/`~` markers
- Alert header regex splitting (`_split_blocks`, `_is_alert_header`) — card is one cohesive block
- Markdown balance fixing — format uses no `**` or backticks

**v6 code:** reads file → splits into Telegram-safe chunks → sends via `telegram_direct`.

## v3.3 Alert Card Format

```
══ BTC · 65,306 · VWAP 64,201 · 22:11 ══
综合: B 中性 (多1 vs 空1)

  + VWAP+B2突破 → 价格65306>+B264474·>VWAP64201 · 78%
  - Taker碾压卖 → Taker0.69·卖方碾压 · 60%
  ~ KillZone → Silver Bullet窗·波高·待突破
  ~ ★SilverBullet窗 → 14-15UTC银弹·待位移确认

关键位: VWAP 64,201 · VAH 64,460 · VAL 63,894 · B2上 64,474 · B2下 63,928
指标: CVD -3,368 · Taker 0.69 · OI 0M
```

**Design principles:**
- `+` = long signal, `-` = short signal, `~` = neutral/window signal
- `综合` line gives instant direction + grade + signal count ratio
- Signals grouped by direction for instant visual scan
- `关键位` and `指标` sections at bottom for reference
- No separators, no direction prefix duplication
- Confidence shown as `· 78%` instead of `(conf:0.78)`
- Confluence replaced "权重3/2" with human-readable "综合: B 偏多 (多3 vs 空2)"

## Encoding (unchanged from v5)

Windows no_agent cron stdout is GBK(cp936). Chinese must never go through stdout.
Only use UTF-8 files or direct Telegram API payloads.
