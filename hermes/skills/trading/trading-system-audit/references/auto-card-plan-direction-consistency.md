# Auto-card B等待预案方向一致性

## Trigger

Use this reference when auditing or modifying `hermes/scripts/auto_card.py` operation sections, especially when the user asks to review BTC/XAU templates or generate a simulation.

## Problem Pattern

In B等待 mode, the rendered card can look complete while A/B plans are semantically inconsistent:

- A plan title says 多头/空头 but `① 方向` says 观望.
- B plan says 多头 but stop/targets still use the original 空头 bias.
- XAU/BTC asset-specific risk text is correct, but price geometry is reversed.

This is a P1 template correctness issue because it can mislead execution even if the template passes machine-field leak scans.

## Fix Pattern

Inside the B等待 operation renderer:

1. Normalize the main tactical bias before rendering:
   - `偏空/空头` → `偏空`
   - `偏多/多头` → `偏多`
   - neutral/观望 fallback → pick a concrete primary plan bias for simulation, usually `偏多` unless strategy state says otherwise.
2. Derive explicit plan directions from bias:
   - `偏空` → `空头`
   - `偏多` → `多头`
3. Render A plan with `plan_a_bias`.
4. Render B plan with `_opposite_bias(plan_a_bias)` for stop, targets, failure text, and trajectory.
5. Never use display direction (`dir_cn`) as the source of stop/target math.

## Required Helpers

Recommended helper shape:

```python
def _primary_plan_bias(bias_cn: str) -> str:
    if bias_cn in ("偏空", "空头"):
        return "偏空"
    if bias_cn in ("偏多", "多头"):
        return "偏多"
    return "偏多"


def _opposite_bias(bias_cn: str) -> str:
    return {"偏空": "偏多", "偏多": "偏空", "空头": "偏多", "多头": "偏空"}.get(bias_cn, "观望")


def _dir_from_bias(bias_cn: str) -> str:
    return {"偏空": "空头", "偏多": "多头"}.get(bias_cn, "观望")
```

## Verification Bundle

After any change to operation rendering:

```bash
python scripts/auto_card.py BTCUSDT >/tmp/sim_btc.out 2>/tmp/sim_btc.err
python scripts/auto_card.py XAUUSD >/tmp/sim_xau.out 2>/tmp/sim_xau.err
python -m pytest -q
```

Then inspect `data/auto_card_BTCUSDT.md` and `data/auto_card_XAUUSD.md` operation sections:

- BTC 空头 A：stop above entry, targets below entry.
- BTC 多头 B：stop below entry, targets above entry.
- XAU 多头 A：stop below entry, targets above entry, unit `oz`, risk text says Exness/1000x as account cap.
- XAU 空头 B：stop above entry, targets below entry.
- No `setup_id/model_id/entry_tag/exit_tag/critical/warning/info` leaks in user-visible card text.

## B等待 Entry Price Must Be an Offset, Not Naked Current Price (2026-06-20)

In B等待 mode the renderer previously printed the raw current price as the A-plan
entry and labeled it `限价`. That is wrong on two counts:

1. **Naked current price is not a real entry.** A B等待 plan is waiting for a
   confirmation trigger (a bounce off / reclaim of a level), so the entry must be
   the **trigger-offset price**, not spot. Use a per-asset offset applied in the
   plan's direction (primary bias offsets one way, the opposite-bias B plan offsets
   the other).
2. **Label must be `等待触发`, not `限价`.** A B等待 entry is a *conditional/stop*
   order pending confirmation, not a resting limit order. Calling it `限价` implies
   a passive resting order at spot, which misleads execution.

### Offset reference (per asset class)

```
crypto  ±200 点
gold    ±8 美元
forex   ±0.0015
stock   ±2 点
option  ±0.2 点
```

Helper shape that unifies A/B offset direction:

```python
def _plan_entry_offset(asset_class: str) -> float: ...      # magnitude by asset
def _fmt_entry(price: float, asset_class: str) -> str: ...  # consistent formatting
def _plan_a_entry(price, bias_cn, asset_class) -> float:    # spot ± offset by bias
    off = _plan_entry_offset(asset_class)
    return price - off if bias_cn in ("偏多","多头") else price + off
```

Apply `_plan_a_entry` for the primary plan and the opposite offset for the B plan.

### R:R note (known acceptable deviation)

Targets/stops are still anchored to spot while the entry is offset, so the *displayed*
plan has a slightly off-nominal R:R (e.g. BTC A-plan ~2.21 / ~3.28 instead of exactly
2.0 / 3.0). The deviation is **favorable** (more reward per unit risk) and the card
does not render an R:R number, so it is accepted as-is. To make it exact you must pass
the offset entry price into `_plan_targets`/`_plan_stop` so they compute distance from
the actual entry, not spot — a small change but it requires re-running the full bundle.

## Two Silent-Failure Traps Found in This Pipeline (2026-06-20)

These are reusable audit lessons, not one-offs:

1. **Broad `except` hiding a `NameError` → dead validation.** `scripts/智能更新结构.py`
   referenced an undefined `DATA_DIR` (the real name is `DATA`). A surrounding
   `try/except` swallowed the `NameError`, so the snapshot quality cross-validation
   block had been **silently dead since deployment** — no error, no output, just
   nothing happening. Audit move: grep for variable-name drift inside try/except
   blocks; never trust "no error in log" as proof a block runs. Add an explicit
   log line at the end of validation blocks so absence is visible.

2. **Dead function passing empty data → wrong math if ever revived.** `auto_card.py`
   carried `_tp_reason` / `_tp_reason_b` that received empty `klines` and therefore
   computed an R:R inflated ~3x. They had no callers. Leaving them in place is a
   latent landmine (someone wires them up later, gets garbage). Deleted both. Audit
   move: when reviewing a renderer, list functions with zero callers and either wire
   them correctly or delete them — do not leave half-built helpers that compute on
   empty inputs.

## Presentation to User

When user asks “给一个模拟我看看”, show actual generated operation sections, not a hand-written mock. Keep other commentary short; operation section may be long because that is the intentionally detailed part.
