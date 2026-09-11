# TradingView editor identity and deployment verification

The local tradingview-mcp `openScript` may fetch a saved source and call Monaco setValue without opening/binding that saved script in the native UI. Its returned script_id describes the fetched source, not necessarily the active editor document identity. Inspect the implementation and native editor title before any Save. An Untitled editor may bring up Save As even when the source matches a production indicator.

Smart compile may fall back to a Pine Save button; success/no markers does not establish completed compilation or chart update. A pending compile and an unsaved-version label are incomplete states, not acceptance.

Use the native editor menu > Open script > exact saved name and verify the editor title changes. Preserve the candidate on disk before discarding a temporary unsaved editor buffer. After replacement, read the exact saved script ID/version through the authenticated page fetch and compare normalized source to the candidate. Verify the active study's new output plots and transport contract separately. Do not add a second indicator or remove the old study simply to make the compile receipt look successful. Keep original inputs and source links intact.

Cloud readback that still equals the original means the candidate is not saved, even if Monaco matches it and the Save click succeeded. Record the blocker explicitly; do not claim deployment.
