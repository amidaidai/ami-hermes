#!/usr/bin/env python3
"""xAI OAuth PKCE flow - two step: 1) generate URL, 2) exchange code."""

import base64, hashlib, json, os, sys, uuid
import urllib.request, urllib.parse

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
REDIRECT_URI = "http://127.0.0.1:56121/callback"
SCOPE = "openid profile email offline_access grok-cli:access api:access"
DISCOVERY_URL = "https://auth.x.ai/.well-known/openid-configuration"


def pkce_verifier():
    token = uuid.uuid4().bytes + uuid.uuid4().bytes + uuid.uuid4().bytes
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode("ascii")


def pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def get_discovery():
    with urllib.request.urlopen(DISCOVERY_URL) as r:
        return json.loads(r.read())


def build_auth_url(auth_endpoint, challenge, state, nonce):
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "nonce": nonce,
        "plan": "generic",
        "referrer": "hermes-agent",
    }
    return auth_endpoint + "?" + urllib.parse.urlencode(params)


def exchange_code(token_endpoint, code, verifier, challenge):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        token_endpoint,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def mode_gen():
    """Generate authorization URL and save PKCE state to temp file."""
    discovery = get_discovery()
    auth_endpoint = discovery["authorization_endpoint"]
    token_endpoint = discovery["token_endpoint"]

    verifier = pkce_verifier()
    challenge = pkce_challenge(verifier)
    state_val = uuid.uuid4().hex
    nonce = uuid.uuid4().hex

    auth_url = build_auth_url(auth_endpoint, challenge, state_val, nonce)

    # Save state to temp file so step 2 can use it
    state_data = {
        "verifier": verifier,
        "challenge": challenge,
        "token_endpoint": token_endpoint,
    }
    with open("D:\\Hermes agent\\hermes\\secrets\\xai_oauth_state.json", "w") as f:
        json.dump(state_data, f)

    print(auth_url)


def mode_exchange(code):
    """Exchange authorization code for tokens using saved state."""
    with open("D:\\Hermes agent\\hermes\\secrets\\xai_oauth_state.json") as f:
        state = json.load(f)
    os.remove("D:\\Hermes agent\\hermes\\secrets\\xai_oauth_state.json")

    tokens = exchange_code(
        state["token_endpoint"],
        code,
        state["verifier"],
        state["challenge"],
    )

    # Save to auth.json
    hermes_home = os.environ.get(
        "HERMES_HOME",
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes"),
    )
    auth_file = os.path.join(hermes_home, "auth.json")

    os.makedirs(os.path.dirname(auth_file), exist_ok=True)
    existing = {}
    if os.path.exists(auth_file):
        with open(auth_file) as f:
            existing = json.load(f)

    if "providers" not in existing:
        existing["providers"] = {}

    existing["providers"]["xai-oauth"] = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_in": tokens.get("expires_in", 21600),
        "scope": tokens.get("scope", SCOPE),
        "issuer": "https://auth.x.ai",
        "client_id": CLIENT_ID,
    }

    with open(auth_file, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"OK: tokens saved to {auth_file}")
    print(f"AT: {tokens['access_token'][:30]}...")
    print(f"RT: {'yes' if tokens.get('refresh_token') else 'no'}")
    print(f"Exp: {tokens.get('expires_in', '?')}s")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        mode_gen()
    elif len(sys.argv) == 2:
        mode_exchange(sys.argv[1])
    else:
        print("Usage: xai_oauth.py           # generate URL")
        print("       xai_oauth.py CODE       # exchange code")
        sys.exit(1)
