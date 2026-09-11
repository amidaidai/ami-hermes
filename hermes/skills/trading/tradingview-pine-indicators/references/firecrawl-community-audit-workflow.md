# Firecrawl Community Audit Workflow

## Use Case
When the user asks for community-driven optimization of a TradingView/Pine dashboard and mentions Firecrawl, use Firecrawl as the primary web research source, then convert the best community critiques into guardrails and lightweight diagnostics.

## Search Themes
Run separate queries for:
- CVD absorption / divergence / order-flow confirmation
- Volume profile / microstructure / calibrated sweeps
- Reddit criticism of TradingView delta/CVD/footprint quality
- GitHub Pine order-flow / volume profile examples
- Multi-factor calibration / forward hit-rate / signal half-life

## Practical Pattern
1. Treat TradingView CVD/Delta as a lower-timeframe estimate, not true bid/ask order flow.
2. Gate CVD by data quality, key-level proximity, and freshness.
3. Add a short signal half-life so stale absorption/divergence does not keep upgrading grade.
4. Add lightweight forward calibration outputs instead of turning the dashboard into a strategy.
5. Keep visuals low-noise for this user: right-top panel and Data Window first; avoid FVG/OB/plotshape/bgcolor unless explicitly requested.

## Firecrawl Request Shape
If no dedicated MCP tool is available, use:

- `POST https://api.firecrawl.dev/v2/search`
- JSON body with at least:
  - `query`
  - `limit: 4`
  - `sources: ["web"]`
  - `scrapeOptions.formats: [{"type":"markdown"}]`

## Good Outputs To Preserve
Capture:
- Specific critique text from Reddit / TradingView scripts
- Concrete formulas or thresholds worth porting
- Evidence that a feature should be a confirmation layer rather than a standalone signal
- Any reuse candidates for calibration or dashboard readability

## Do Not Preserve
Do not turn one-off market opinions into permanent rules. Only keep the durable pattern: community criticism → guardrail or diagnostic in the indicator.
