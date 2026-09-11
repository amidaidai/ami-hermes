---
name: discord-gateway-configuration
description: "Use when configuring a Discord bot gateway."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [discord, gateway, bot, configuration, allowlist, verification]
---

# Discord Gateway Configuration

Class-level workflow for connecting a Discord bot to Hermes Gateway. This skill covers native gateway configuration, least-privilege routing, restart behavior, and post-change verification. It is intentionally separate from Discord content automation or moderation: the goal here is a reliable connection and narrowly scoped access.

## Safety and secret handling

- Treat `DISCORD_BOT_TOKEN` as a credential. Never print it, place it in a report, commit it, or echo it during verification.
- Store the token only in the active Hermes profile `.env`; keep IDs and non-secret settings in configuration where appropriate.
- If the token was pasted into chat, logs, shell history, or a ticket, recommend rotating it in Discord Developer Portal after connectivity is established.
- Preserve identifiers literally. Do not “repair” or normalize Discord snowflake IDs or token text.

## Standard setup

1. Load the Hermes configuration guidance and discover the active profile paths with `hermes config path` and `hermes config env-path`.
2. Confirm the Discord gateway adapter and relevant environment variable names from the installed source/docs before editing. The native variables are:
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_ALLOWED_USERS` (comma-separated user IDs)
   - `DISCORD_ALLOWED_CHANNELS` (comma-separated channel IDs)
   - `DISCORD_HOME_CHANNEL` and optional `DISCORD_HOME_CHANNEL_NAME`
   - optional `DISCORD_ALLOWED_ROLES`, `DISCORD_REPLY_TO_MODE`, and proxy settings
3. Write or update only the required keys in the active profile `.env`, preserving unrelated entries. Prefer one authorized user and one authorized channel instead of `DISCORD_ALLOW_ALL_USERS`.
4. Keep `discord.require_mention: true` unless the user explicitly requests free-response behavior. If channel-level settings are in YAML, ensure they do not contradict the intended allowlist.
5. Restart the gateway (`hermes gateway restart`) because gateway config and environment changes are not hot-reloaded reliably.

## Verification gate

Do not claim success from a running gateway process alone. Verify all of the following:

- `hermes gateway status` reports a running gateway.
- The gateway log contains a successful Discord connection, ideally the bot username, and no later disconnect/failure.
- Read-only Discord API checks with the bot credential return HTTP 200 for `/users/@me`, the target `/guilds/{guild_id}`, and `/channels/{channel_id}`. Print only non-secret fields (IDs, names, type, bot flag).
- Confirm the returned channel belongs to the requested guild and that the returned bot ID matches the expected ID when one was provided.
- Report the platform’s actual returned guild/channel names; user-facing labels may differ from Discord’s current names.

A transient first connection error must not be treated as final if the adapter retries. Re-read the latest log after a short wait and validate the final state. Conversely, a process that is merely “running” while Discord remains disconnected is not connected.

## Discord-specific prerequisites

- The bot must be installed in the target guild with permission to view the channel and send messages.
- Enable Message Content Intent in Discord Developer Portal if Hermes must read ordinary message content; enable other privileged intents only when the chosen features need them.
- Keep bot responses mention-gated by default to avoid accidental replies in public channels.
- A channel allowlist is not a substitute for Discord permissions, and a successful API lookup does not prove send permission; if message delivery is requested, perform a narrowly scoped test only with explicit authorization.

## Troubleshooting order

1. Check the active profile path and confirm the token key is non-empty without displaying the value.
2. Check gateway logs for the adapter’s final state, not only the first error.
3. If Discord returns 401 / improper token, treat the credential as invalid or revoked; do not alter IDs or add permissions as a guess. Rotate the token and retry.
4. If identity and guild/channel GETs succeed but messages do not, inspect Message Content Intent, mention requirement, allowlists, and bot channel permissions.
5. If the gateway is running manually and persistence across login is required, use the platform-supported `hermes gateway install` only after the connection is verified.

## Session detail

See `references/discord-hermes-verification.md` for the concrete environment variable mapping, verification checklist, and the distinction between an initial retryable failure and the final connected state.
