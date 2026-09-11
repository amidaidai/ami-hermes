# BTC push cron encoding pattern

Use this when a Windows no_agent cron or script-delivery path shows mojibake for Chinese alerts.

## Root cause

Hermes/no_agent stdout on Windows can pass through a GBK/cp936 path. Printing UTF-8 Chinese/emoji to stdout may display as mojibake. For alert systems this is especially easy to reintroduce if the pusher reads a UTF-8 pending file and then `print(cleaned)`.

## Stable rule

- `stdout`: ASCII-only; success should be silent.
- Chinese alert body: UTF-8 pending file or direct platform/API payload.
- Failure diagnostics: English ASCII + non-zero exit.
- Source comments and Chinese strings are okay if they are not printed to stdout.

## Minimal pusher shape

```python
from telegram_direct import send_telegram_direct

TARGET = "telegram:-1003733144325:386"

def log_ascii(message: str) -> None:
    print(message.encode("ascii", "replace").decode("ascii"), flush=True)

raw = pending_path.read_text(encoding="utf-8", errors="replace")
cleaned = clean_pending(raw)
for chunk in telegram_chunks(cleaned):
    ok, reason = send_telegram_direct(TARGET, chunk)
    if not ok:
        log_ascii(f"ERROR push failed: {reason}")
        raise SystemExit(1)
pending_path.write_text("", encoding="utf-8")
```

## Verification command shape

```bash
python - <<'PY'
from pathlib import Path
p=Path('/c/Users/Administrator/AppData/Local/hermes/data/btc_pending.txt')
p.write_text('测试中文推送：现价 `64400`，方向偏多等待VAH接受。\n', encoding='utf-8')
PY
out=$(python btc_push_cron.py 2>&1); rc=$?
printf 'rc=%s\nstdout=%s\n' "$rc" "$out"
printf 'pending_size='; wc -c < /c/Users/Administrator/AppData/Local/hermes/data/btc_pending.txt
```

Expected: `rc=0`, `stdout=` empty, `pending_size=0`.
