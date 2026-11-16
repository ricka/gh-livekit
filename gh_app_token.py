#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyjwt[crypto]"]
# ///
"""Mint a GitHub App installation token.

Env vars:
    GITHUB_APP_ID                  App ID (the Client ID also works)
    GITHUB_APP_PRIVATE_KEY_PATH    path to the app's .pem file
      or GITHUB_APP_PRIVATE_KEY_B64    base64-encoded PEM (what the Dagster asset uses)
    GITHUB_APP_INSTALLATION_ID     optional; looked up automatically when the app
                                   has exactly one installation

Usage (see README.md for the full setup):
    # Print a token
    uv run -q --env-file .env gh_app_token.py

    # Clone with this script as the repo's only credential helper
    # (fresh token per git operation, nothing stored; other repos unaffected)
    git clone \
        -c credential.helper= \
        -c "credential.helper=!uv run -q --env-file /abs/path/.env --script /abs/path/gh_app_token.py" \
        https://github.com/ndr-data/ndr-ai-core.git

    # Run gh as the app for one command
    GH_TOKEN=$(uv run -q --env-file /abs/path/.env --script /abs/path/gh_app_token.py) gh pr create --draft
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import jwt

API = "https://api.github.com"


def env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        sys.exit(f"Missing env var: {name}")
    return value


def normalize_pem(text: str) -> str:
    """Rebuild a PEM whose newlines were lost (e.g. stored in 1Password as one line)."""
    text = text.replace("\\n", "\n")
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", text, re.S)
    if not m:
        return text
    label, body = m.group(1), re.sub(r"\s+", "", m.group(2))
    lines = [body[i : i + 64] for i in range(0, len(body), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def private_key() -> str:
    path = env("GITHUB_APP_PRIVATE_KEY_PATH", required=False)
    if path:
        with open(os.path.expanduser(path)) as f:
            return normalize_pem(f.read())
    b64 = env("GITHUB_APP_PRIVATE_KEY_B64", required=False)
    if b64:
        return normalize_pem(base64.b64decode(b64).decode())
    sys.exit("Missing env var: GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY_B64")


def api(method: str, path: str, bearer: str):
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {bearer}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API {method} {path} -> {e.code}: {e.read().decode(errors='replace')}")


def installation_id(app_jwt: str) -> str:
    explicit = env("GITHUB_APP_INSTALLATION_ID", required=False)
    if explicit:
        return explicit
    installs = api("GET", "/app/installations", app_jwt)
    if len(installs) == 1:
        return str(installs[0]["id"])
    found = ", ".join(
        f"{i['id']} ({(i.get('account') or {}).get('login', '?')})" for i in installs
    )
    sys.exit(f"Set GITHUB_APP_INSTALLATION_ID. Installations found: {found or 'none'}")


def mint_token() -> str:
    app_id = env("GITHUB_APP_ID")
    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        private_key(),
        algorithm="RS256",
    )
    inst = installation_id(app_jwt)
    return api("POST", f"/app/installations/{inst}/access_tokens", app_jwt)["token"]


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else None

    if action is None:
        print(mint_token())
    elif action == "get":
        # Git credential helper protocol: drain the request from stdin, reply with creds.
        for line in sys.stdin:
            if not line.strip():
                break
        print("username=x-access-token")
        print(f"password={mint_token()}")
    # "store" / "erase": nothing to do; tokens are minted fresh each time.


if __name__ == "__main__":
    main()
