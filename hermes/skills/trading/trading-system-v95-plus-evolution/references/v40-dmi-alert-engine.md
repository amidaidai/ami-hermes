# v4.0 DMI Decision Engine — Alert Pipeline Upgrade (2026-06-22)

## Summary

Replaced the old weighted-sum Confluence scoring in `btc_alert_watch_v3.py` with a full DMI Decision Engine that replicates the user's Pine Script `SVP+ICT+VWAP+EMA+CVD` indicator logic.

## What Changed

| Aspect | Old (v3.x) | New (v4.0) |
|--------|-----------|------------|
| Scoring | Weighted sum of signal counts | Trend score + Reversal score (dual-track 0-10) |
| DMI | Not used | ADX/DI+/DI- computed in Python (Wilder's RMA) |
| CVD | Simple slope check | 6-state: bull/bear confirm, bull/bear div, absorb, distribute |
| HTF filter | None | Weekly VWAP + EMA direction check |
| Key level gate | None | A grade requires price within 0.6 ATR of key level |
| Risk flag | D grade only | X grade: hot/extended/conflict/HTF conflict |
| Push threshold | A+ or A (old scoring) | A only (trend ≥ 8, gap ≥ 2, CVD confirm, acceptance OK) |

## New Files

- `scripts/dmi_decision.py` — DMI computation + scoring engine + grade determination (16 KB)
- Modified: `scripts/btc_alert_watch_v3.py` — v4.0 with DMI engine integration

## Architecture Note

Dual-path: TV MCP path for analysis cards (auto_card.py reads TV DMI table via MCP) vs Python path for cron alerts (btc_alert_watch_v3.py uses dmi_decision.py independently). This is necessary because cron jobs can't access MCP tools.

## Verification

- Script runs successfully (exit 0)
- Current market: grade X (ADX 41.1 hot) — correctly silenced
- detector_state.json shows full scores: trend 5/2, reversal 6/4, ADX 41.1
- Only A grade triggers push to Telegram
