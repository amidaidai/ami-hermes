# Runtime Connectivity Recovery Patterns

Use this when a trading-system audit finds that core services look partly alive but account endpoints, TradingView CDP, or monitor runtime are degraded.

## Binance MCP: price works, account fails

Symptom:
- Public price endpoints respond, but signed account/position calls intermittently fail with connection reset / WinError 10054 / remote host closed connection.

Correct interpretation:
- Do not mark Binance fully healthy from public price calls alone.
- Treat signed account endpoints as the health gate because they validate auth, timestamp, proxy routing, and request reliability.

Fix pattern:
1. Prefer plain REST for the Binance MCP server when dependency conflicts around websockets appear.
2. Wrap every `urllib.request.urlopen` call in one shared helper with:
   - short timeout
   - retry count around 3
   - exponential or linear backoff around 0.6s base
   - JSON parsing in the helper so callers do not duplicate fragile handling
3. Replace GET, POST, DELETE, and futures-signed helper paths with that helper.
4. Verify with signed calls, not public price only:
   - account summary returns futures wallet
   - futures positions returns a valid empty-or-populated structure

Pitfall:
- If the MCP server file lives under `tools/` and is ignored or outside normal tracked status, explicitly check backup/commit coverage. A working local fix can be lost even while `git status` looks clean.

## TradingView Desktop CDP on Windows MSIX

Symptom:
- TradingView MCP reports CDP disconnected or `127.0.0.1:9222` not listening.
- Normal process launch does not expose the debugging port for the installed Desktop/MSIX app.

Fix pattern:
1. Launch TradingView Desktop via Windows MSIX COM activation, passing `--remote-debugging-port=9222`.
2. Then verify the port is listening before calling TradingView MCP health checks.
3. Confirm `tv_health_check` returns symbol, timeframe, and indicators.

Do not conclude chart automation is broken until the MSIX COM launch path has been tried.

## Monitor code restoration after accidental regression

Symptom:
- Monitor is running, but focused tests show missing async push / queue drain / setup trace functions.
- `git diff --stat` shows a large unexpected diff in `scripts/行情守望.py`.

Fix pattern:
1. Restore the monitor core from the known-good tracked version rather than manually re-adding scattered functions.
2. Re-run focused regression tests for async push and setup trace before broader tests.
3. Restart the running monitor process; source changes alone do not update the resident process.
4. Verify heartbeat freshness and absence of old log errors.

## Closure verification bundle

Before claiming fixed after a runtime connectivity repair:
- Compile changed Python files.
- Run focused tests that cover the damaged paths.
- Run the full available pytest suite if the repo has one.
- Verify signed Binance account/positions.
- Verify TradingView CDP health.
- Verify monitor heartbeat and current PID.
