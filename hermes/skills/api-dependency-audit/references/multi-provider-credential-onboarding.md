# Multi-provider credential onboarding

Use this reference when onboarding a batch of finance, exchange, on-chain, or prediction-market API credentials.

## Safe storage contract

- Credentials live in a repository-ignored directory, one file per provider unless the provider requires a structured bundle.
- Structured bundles may use JSON, but callers must never log the parsed object.
- Environment variables override local files.
- The reusable reader module itself must remain tracked; avoid filenames caught by broad ignore patterns such as `*secret*`.
- After writing, verify only file existence and byte length. Never print values.

## Source cleanup

Search the whole codebase for recognizable key fragments and patterns such as:

```text
env.get(...) or "literal"
API_KEY = "literal"
headers={...literal...}
```

Replace them with the shared reader. Re-run the scan and require zero literal matches.

## Probe result classes

| Class | Meaning |
|---|---|
| `authenticated` | Private/read-only endpoint accepted the credentials |
| `public-only` | Public API works, but private credentials were not required or not complete |
| `plan-restricted` | Credentials were recognized, but the requested endpoint is outside the subscription |
| `network-unverified` | Authentication could not be evaluated because transport failed |
| `invalid` | Provider explicitly rejected the credentials |

HTTP status alone is insufficient. Examples:

- HTTP 200 with provider `code=401` and `msg=Upgrade plan` → `plan-restricted`, not healthy and not necessarily an invalid key.
- HTTP 200 with an empty public positions list → public endpoint healthy; it does not prove private trading authentication.
- Transport error on a signed read-only endpoint → `network-unverified`, not invalid.

## Safe probe matrix

| Provider class | Preferred probe | Forbidden verification |
|---|---|---|
| Exchange | Signed account/balance read | Place, cancel, transfer, withdraw |
| Market-data vendor | Quote, key-info, supported-symbols | High-volume historical download |
| On-chain analytics | One cached query result | Launching costly query execution without approval |
| Prediction market | Public events/data/CLOB time; private auth only with complete credential bundle | Creating/cancelling orders merely to test a key |

## Multi-part authentication

Some trading APIs require more than one value. Treat private operations as disabled until the full bundle is available and matched:

- API key
- API secret
- passphrase, when applicable
- wallet/private-key signature identity, when applicable
- funding/proxy address, when applicable

A public market-data API succeeding does not validate this private bundle.

## Acceptance checklist

- Secret files exist and are ignored by Git.
- Shared credential reader is tracked by Git.
- Literal-key source scan returns zero matches.
- Every provider has a semantic result class.
- No state-changing endpoint was called.
- Compile checks pass.
- Full regression suite passes.
- Final report separates provider limits from code defects and network-unverified states from invalid credentials.
