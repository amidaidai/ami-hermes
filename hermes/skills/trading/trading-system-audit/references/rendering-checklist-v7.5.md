# Rendering Checklist v7.5

Mandatory before any alert/monitor change. Tests user-visible output.

## Alert (行情守望.py render_message)

- [ ] `display_name` used, not `name` (internal IDs like R1_reclaim_accept never leak)
- [ ] No double prefix ("引擎引擎" → just "引擎判...")
- [ ] Taker direction: buy→买, sell→卖
- [ ] Labels spaced: `CVD {val}` not `CVD{val}`, `Taker {text}` not `Taker{text}`
- [ ] Kill Zone: Chinese (亚洲盘/伦敦盘/纽约上午盘/纽约下午盘)
- [ ] Funding/Spot: kept in English per user preference
- [ ] Panorama levels: display_name + double-space separator
- [ ] Risk line: `·` separator, not space

## Analysis Card (auto_card.py)

- [ ] `_find_nearest_key_level`: VAH→价值上沿, VAL→价值下沿, POC→控制点, VWAP→量价均值
- [ ] `_sr_level`: returns 待确认 not N/A
- [ ] `_exec_line`: returns 待确认 not N/A
- [ ] `_chase_ok`: returns — not N/A
- [ ] `_tf_verdict`: dynamic (EMA21-based), not hardcoded
- [ ] `_compact_card`: taker_dir dual-compatible (buy/买, sell/卖)
- [ ] No machine fields (setup_id, model_id, entry_tag etc.) in card body
- [ ] Plans A/B fully symmetric (direction, entry, stop, target, position, failure, review)

## Labels — English vs Chinese

| Keep English | Use Chinese |
|-------------|-------------|
| Funding | 资金费率 ✗ |
| Spot/美元 | 现货/美元 ✗ |
| Taker (prefix) | 买/卖 (direction) |
| CVD (prefix) | 买/卖 (direction) |
| Kill Zone ✗ | 亚洲盘/伦敦盘 ✓ |
| VAH/VAL ✗ | 价值上沿/下沿 ✓ |
| N/A ✗ | 待确认 ✓ |
