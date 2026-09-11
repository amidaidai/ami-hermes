# CE10117: full compiler acceptance

Official current reference: https://www.tradingview.com/pine-script-docs/errors/CE10117/ (retrieved successfully through Python requests when web_extract rejected DNS).

The full Pine compiler measures optimized intermediate-language size, with a documented limit of 100,256 tokens. `translate_light` syntax/type checking can pass while actual Save/Update fails CE10117. Never label a script client-compiled solely from translate_light or lack of Monaco markers.

Removing comments/whitespace, shortening variable names, and removing already-unused code does not reduce compiled IL. Identical expressions may already be optimized. Constant strings, including tooltips, contribute to IL: concise equivalent tooltips can reduce size without changing decision logic, inputs, plots or external bus contracts. Preserve user-relevant safety warnings and source/unit descriptions. User reported candidate failure: 100488 versus 100256, CE10117; source equality must be checked against the actual editor before repair.

Acceptance: capture the exact error before changing source; create a new candidate; prove decision code and input ordering unchanged if only tooltip edits; perform full native-client Save/Update; wait for terminal completion (not merely a clicked button), read back exact cloud ID/source/version, and verify active study outputs. A successful compiler does not expose its IL token count, so never invent the resulting count or remaining headroom. Report actual pass/fail instead.
