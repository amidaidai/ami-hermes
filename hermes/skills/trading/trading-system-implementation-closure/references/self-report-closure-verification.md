# Self-report closure verification

Use when a user or prior agent pastes “全面审计已完成 / P0 已修”. Treat the paste as claims. Do not restamp it.

## Probe order

1. Beijing time + `git status --short --branch` (untracked archives and unpushed commits are not “fixed”).
2. Interpreter: which `python`, venv vs uv cpython on disk. Deps present in the *current* shell is environment state, not a code fix unless git shows the pin.
3. `data/keylevels_config.json`: `approval_renewal.valid_until` vs each level `source` and price. TTL renew ≠ price update.
4. `data/keylevels_candidates.json`: `ts`, `status` (`candidate_pool_only`), `timeframes_complete`, count. Fresh candidates do not become approved levels.
5. Card artifacts: `data/auto_card_<SYMBOL>.md` and `_full.md`. Grep claimed numbers (`rr2=`, VAL/VAH/POC). Pipeline footer `11/15` stays `11/15`.
6. GO/NO-GO table vs `【裁决】` vs hard-gate ids. A green R:R row does not explain NO-GO; name `haldro_state_conflict` / `advanced_confluence` when those are the ids.
7. TV: CDP 9222, `tv_health_check` symbol/resolution, debug-port PID. Extra `TradingView.exe` processes are noise unless identity is wrong.
8. Current guard: `.keylevel_guard_heartbeat.json` + `.keylevel_guard_health.json` (`active_approved_levels`). Ignore weeks-old `monitor_heartbeat.json` / `.btc_daemon_heartbeat.json` as the live chain.
9. Lease: `python scripts/tv_analysis_lease.py status`. Dead PID or past `expires_at` → `end` → `status` until `无分析租约`.

## Report shape

Lead `已完善 / 部分完善 / 未完善`. One claim table (said vs live). Do not copy unverified `rr2` or “15步齐全” from the narrative.
