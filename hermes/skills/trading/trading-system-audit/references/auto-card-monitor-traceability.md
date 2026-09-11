# Auto-card to monitor setup traceability pattern

## When to use

Use this pattern when an analysis card pipeline generates a trade idea or setup and a separate monitor later emits trigger events. The goal is to preserve attribution from card → monitor → event → review → model statistics.

## Durable lesson

Do not stop at rendering human-readable cards. Add machine-readable setup metadata and carry it through every downstream event.

## Recommended fields

Card/setup metadata:
- `setup_id`
- `model_id`
- `entry_tag`
- `exit_tag`
- `direction`
- `status`
- `priority_plan`
- `data_grade`
- `level_confidence`
- `engine_confidence`
- `confidence_5`
- `risk_usd`
- `rr1`
- `rr2`
- `invalid_price`
- `expires_at`
- `monitor_write`

Monitor trigger event metadata:
- `setup_id`
- `model_id`
- `entry_tag`
- `exit_tag`
- `trigger_kind`
- `trigger_price`
- `trigger_level`
- `trigger_level_name`
- `trigger_levels`
- `trigger_reason`
- `trigger_level_confidence`
- `setup_trace`

## Implementation pattern

1. In the card generator, create `build_setup_metadata()` and `render_machine_fields()`.
2. Append the machine field block to the card after applying template formatting rules.
3. Write the same metadata to the monitor state, typically `monitor_levels.json -> symbols.<symbol>.latest_setup`.
4. Append a structured record to `trade_plans.jsonl` for audit/replay.
5. In the monitor, add a pure helper like `enrich_event_with_setup(event, block, hits, trigger_kind)`.
6. Call the helper before each event write path: expired, invalidated, near, breach.
7. Bump event schema only when setup metadata is actually attached; keep legacy/manual plans compatible.
8. Add tests before implementation:
   - setup metadata has traceable fields
   - card renders machine fields
   - template guard rejects `B等待` with concrete entry prices
   - template guard flags `R:R < 1:2`
   - trade plan writes machine fields
   - monitor event inherits latest setup fields
   - legacy event without latest setup stays compatible

## Template guardrails

For 棠溪 trading cards, enforce these automatically:
- `B等待` must not publish concrete entry/stop/take-profit prices.
- `R:R` below `1:2` must be flagged.
- Cards should not contain decorative emoji or square-bracket hotword formatting.
- Required machine fields are `setup_id`, `model_id`, `entry_tag`, `exit_tag`.

## Verification commands

Run syntax and focused tests first:

```bash
python -m py_compile hermes/scripts/auto_card.py scripts/行情守望.py
python -m pytest tests/test_auto_card_machine_fields.py tests/test_auto_card_format_sanitize.py tests/test_monitor_setup_trace.py -q
```

Then run full suite:

```bash
python -m pytest -q
```

## Why it matters

Without setup propagation, later reviews can only say that a price level triggered. With setup propagation, reviews can measure which model, entry tag, and exit tag actually produced useful alerts and should be up/down weighted.
