# Auto-card → Monitor → Review Traceability Pattern

Use this reference when optimizing 棠溪 trading-system analysis cards, monitor triggers, or review/model-statistics pipelines.

## Durable lesson

A trading card is not complete if machine-readable setup fields only appear in the rendered Markdown. The fields must propagate through the full execution/review chain so model performance can be grouped by setup and tag.

Required chain:

1. `auto_card.py` generates setup metadata:
   - `setup_id`
   - `model_id`
   - `entry_tag`
   - `exit_tag`
   - `direction`
   - `status`
   - confidence/risk/data fields
2. Card appends a `机器字段` block after template sanitization.
3. Same metadata is appended to `data/trade_plans.jsonl`.
4. Same metadata is written to `data/monitor_levels.json -> symbols.<symbol>.latest_setup`.
5. `scripts/行情守望.py` enriches trigger events from `latest_setup` before writing/logging events.
6. `scripts/trading_system.py::log_review()` enriches review records from matching `trade_events.jsonl` / `trade_plans.jsonl` when the review did not explicitly provide trace fields.
7. Model statistics can then group by `model_id`, `entry_tag`, `exit_tag`, and `setup_id`, not only price levels.

## Event enrichment fields

Monitor events should carry:

- `setup_id`
- `model_id`
- `entry_tag`
- `exit_tag`
- `direction`
- `status`
- `data_grade`
- `level_confidence`
- `engine_confidence`
- `confidence_5`
- `trigger_kind`
- `trigger_price`
- `trigger_level`
- `trigger_level_name`
- `trigger_levels`
- `trigger_reason`
- `trigger_level_confidence`
- `setup_trace`

When enriched, monitor event schema should advance to a distinct version, e.g. `v2.4`, while legacy/manual plans without `latest_setup` stay compatible.

## Review enrichment fields

`log_review()` should preserve explicitly supplied review fields. Only fill missing fields from the latest matching event/plan by `setup_id` or `plan_id + symbol`.

Review records with trace metadata should use a distinct schema, e.g. `trade_review_v2`, and set `model` from `model_id` when `model` is missing so existing stats code still works.

## TDD guards

Add RED tests before modifying production code:

- Card metadata generation includes `setup_id/model_id/entry_tag/exit_tag`.
- Card render contains a machine-field block.
- Template guard rejects `B等待` cards with concrete entry prices.
- Template guard flags `R:R < 1:2`.
- Monitor event enrichment inherits `latest_setup` fields.
- Legacy monitor events without `latest_setup` remain compatible.
- Review enrichment inherits trace fields from a matching event.
- Explicit review trace fields are not overwritten by event/plan data.

Verification command pattern:

```bash
python -m py_compile hermes/scripts/auto_card.py scripts/行情守望.py scripts/trading_system.py
python -m pytest tests/test_auto_card_machine_fields.py tests/test_monitor_setup_trace.py tests/test_review_traceability.py -q
python -m pytest -q
```

## Pitfall

Do not stop after updating the template Markdown. If `monitor_levels.json`, trigger events, and review records do not inherit the same setup metadata, the system remains visually improved but statistically untraceable.
