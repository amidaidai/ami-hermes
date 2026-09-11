# Telegram delivery hardening reference

## Failure patterns observed

- `sendMessage` rejected `parse_mode=RichMarkdown` with `unsupported parse_mode`.
- Rich delivery failure previously fell back to raw `| header | value |` text, which is not a table in ordinary Telegram messages.
- Four-column tables were difficult to read on mobile.
- Repeated HTTP 429 responses could be amplified by independent text, photo, watcher, and flush processes.
- Missing or mismatched automated targets could pollute the pending queue.

## Tested remediation

- Route RichMarkdown to `/sendRichMessage` with `rich_message.markdown`.
- Normalize table blocks before building the rich payload: stable blank boundaries, title removal, inline-markdown cleanup, and a maximum of three columns.
- On rich failure, send semantic label rows instead of raw pipes.
- Persist `{until, updated_at}` in a shared rate-limit JSON file; clamp cooldown to 1–900 seconds and read `parameters.retry_after` from Telegram's JSON error body.
- Gate automated sends with both `TANGXI_ENABLE_AUTOMATED_TG=1` and an exact `TANGXI_AUTOMATED_TG_TARGET`.
- Keep pending operations atomic and dead-letter permanent/exhausted items.

## Reproduction/verification matrix

Use monkeypatched `urlopen` fixtures; do not use a production bot token.

| Case | Expected assertion |
|:---|:---|
| Rich table | endpoint is `sendRichMessage`; payload contains `rich_message`; no `parse_mode=RichMarkdown` |
| Wide table | normalized payload has at most three cells per row |
| Rich 4xx | fallback endpoint is `sendMessage`; body contains no raw `|` table syntax |
| 429 text | `parameters.retry_after` is persisted; subsequent send is short-circuited during cooldown |
| 429 photo | same persistent cooldown is written and honored by photo path |
| Queue failure | permanent/configuration failures dead-letter; transient failures remain bounded in pending |

## Verification boundary

Local unit and integration-style mock tests validate routing, payloads, fallback semantics, queue behavior, and cooldown state. They do not prove Telegram client rendering or production topic delivery. Those require an explicitly authorized, non-test operational check.
