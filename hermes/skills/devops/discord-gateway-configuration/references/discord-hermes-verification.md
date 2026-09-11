# Hermes Discord verification reference

## Configuration mapping

For a single-user, single-channel setup, use:

```dotenv
DISCORD_BOT_TOKEN=<secret; never print>
DISCORD_ALLOWED_USERS=<user snowflake>
DISCORD_ALLOWED_CHANNELS=<channel snowflake>
DISCORD_HOME_CHANNEL=<channel snowflake>
DISCORD_HOME_CHANNEL_NAME=<human label>
```

The installed Hermes adapter reads `DISCORD_BOT_TOKEN` and enables Discord from it. `DISCORD_ALLOWED_USERS` gates authorized users; `DISCORD_ALLOWED_CHANNELS` narrows response locations; `DISCORD_HOME_CHANNEL` is the default cron delivery target.

## Verification checklist

1. Restart: `hermes gateway restart`.
2. Wait briefly for adapter retry/backoff, then inspect the latest gateway log lines containing `discord`, `connected`, `failed`, `unauthorized`, or `intent`.
3. Check: `hermes gateway status`.
4. With the token loaded from the profile `.env` (not copied into output), query Discord API v10:
   - `GET /users/@me`
   - `GET /guilds/{guild_id}`
   - `GET /channels/{channel_id}`
5. Output only HTTP status and safe fields such as bot ID, username, guild ID/name, channel ID/name/guild_id/type.
6. Require HTTP 200 for all three and require the channel’s `guild_id` to equal the requested guild ID.

## Retry pitfall

A first `401 Unauthorized` can appear during a gateway restart while the adapter is still cycling through connection attempts. Do not stop at the first error. Re-read the tail of the log after the retry window. Only the final state determines success. If the final state remains `Improper token has been passed`, the token must be rotated; do not guess at token formatting or permissions.

## Security note

If a token was exposed in chat, rotate it in Discord Developer Portal even if the current connection succeeds. Never include it in screenshots, logs, skill files, or final responses.
