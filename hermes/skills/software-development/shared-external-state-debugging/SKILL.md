---
name: shared-external-state-debugging
description: Use when concurrent jobs mutate shared external state.
category: software-development
---

# Shared External State Debugging

Use this class-level workflow for bugs where a foreground action and a scheduled/background worker mutate the same external UI, browser target, desktop session, cache, or account state. Typical symptoms include “my selected symbol changes back”, stale view restoration, one job overwriting another job’s context, or logs claiming success while the live external state is wrong.

## Core invariant

A background collector may temporarily mutate shared state only if it:

1. records the complete state it found on entry;
2. performs its work under the strongest available shared lock;
3. restores the exact entry state on success, failure, timeout, and validation error;
4. verifies the live external state after restoration;
5. never substitutes a default state when the entry state is unavailable.

A successful API call is not proof of final state. Read the target back.

## Investigation workflow

### 1. Build a red reproduction

Capture the user-visible state before starting the worker. Run the worker against a fixture or real safe read-only path, then read the external state back. Assert every relevant field, not only the primary identifier: resource/symbol, view, timeframe, tab, filters, pane, and selected account when applicable.

Test at least:

- foreground state A → worker temporarily uses B → final state is exactly A;
- worker raises after partial mutation → final state is exactly A;
- entry-state lookup fails → worker does not invent a default final state;
- two workers serialize or fail closed rather than interleave mutations.

### 2. Trace ownership and data flow

Search every caller that can mutate the shared state, including cron scripts, CLI wrappers, UI tools, subprocesses, and retry paths. Identify whether the lock is process-wide, thread-local, or only an advisory environment variable. A lock used by one path but not by the foreground path is not a complete serialization guarantee.

### 3. Implement the smallest root-cause fix

Snapshot state immediately after connecting and before the first mutation. Put restoration in a `finally` that encloses the entire mutation-and-validation region. Restore dependencies in a safe order: primary resource/identity first, then view/timeframe and secondary controls. Preserve the original value literally; do not normalize it into a guessed default.

If the state snapshot is invalid or missing, fail closed: publish no claim that the user’s state was preserved and do not switch to a fallback asset merely to finish the job. Where architecture permits, use an isolated tab/session/worker instead of sharing a mutable UI.

### 4. Verify the live target

After the worker returns, call the external state-read endpoint independently. Do not rely solely on worker logs, returned payloads, or cache files. For a foreground user action, perform a final readback immediately before rendering screenshots or reporting completion.

## Common failure patterns

- Restoring only on the happy path; exceptions leave the default asset selected.
- Restoring the symbol but not the timeframe, tab, pane, or filters.
- Capturing state in one process while another process changes it before restoration.
- Holding a lock around cache publication but not around the external UI mutation.
- Using “current chart” APIs without verifying the chart identity after a switch.
- Treating an empty or malformed state response as permission to select a default asset.
- Testing only return codes and not the final external state.

## Regression-test contract

Keep a component-boundary test that checks the source-level or mocked call sequence: snapshot → mutate → work → `finally` restore → readback. Add an integration probe where the external target is available. The acceptance criterion is the final live state, not just passing unit tests.

For the TradingView shared-chart case, see `references/tradingview-state-restore.md`.
