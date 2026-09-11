# Windows Telegram Cron Output

Use this reference when a no_agent cron script runs on Windows and the user wants Chinese Telegram alerts.

## Problem Pattern

A no_agent cron delivers whatever the script writes to `stdout`. On Windows, console/stdout handling can turn Chinese text into mojibake or send noisy status lines such as:

```text
[19:38] watch price=64673 nearest=$440
```

This is not a market-analysis problem; it is an output-channel design problem.

## Preferred Architecture

```text
detector cron/daemon (silent) -> UTF-8 pending.txt -> push cron -> Telegram API/topic
```

- Detector cron: `deliver='local'`; no event means empty stdout.
- Detector script: write Chinese alert cards to `pending.txt` with `encoding='utf-8'`.
- Push cron: read pending, clean separators/Markdown, send via Telegram API or `telegram_direct.py`.
- Push cron success: empty stdout. Failure: ASCII-only error and non-zero exit.

## Detector Script Rules

- Do not print heartbeats like `watch price=...`.
- Do not print Chinese status lines.
- If a fetch fails, either stay silent for expected/transient failures or print ASCII-only diagnostics.
- For dynamic market levels, read shared TV/collector caches; do not keep stale hard-coded prices as active triggers. If a dynamic level is missing or `<= 0`, skip it.
- For trading alerts, include a direction in the pending text: `↑做多`, `↓做空`, or `○等待`, plus the invalidation line.

## Push Script Rules

- Open pending with `encoding='utf-8', errors='replace'`.
- Filter internal separators such as `---` before sending.
- Split messages below Telegram's payload limit.
- Send through API, not stdout, when formatting or topic routing matters.
- Keep stdout empty on success so cron does not emit a second duplicate/noisy response.

## Verification Checklist

Run these before saying the monitor is fixed:

```bash
python -m py_compile detector.py push.py
out=$(python detector.py 2>&1); printf 'detector_stdout_len=%s\n' "${#out}"
out=$(python push.py 2>&1); printf 'push_stdout_len=%s\n' "${#out}"
```

Expected:

- No-event detector stdout length is `0`.
- Push stdout length is `0` on success.
- Pending file is cleared after successful push.
- Cron list shows detector `deliver='local'` and push cron delivering to the target Telegram topic.
