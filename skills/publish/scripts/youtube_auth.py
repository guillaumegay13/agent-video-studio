#!/usr/bin/env python3
"""One-time YouTube OAuth: authorize once, capture a refresh token into .env.

Run from the repo root:

    python3 skills/publish/scripts/youtube_auth.py

Opens a browser, asks you to pick the Google account that owns the target
YouTube channel, and grants upload access. The refresh token it returns is
written back into skills/publish/.env so later uploads run unattended.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SKILL_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = SKILL_ROOT / ".env"

# Single source of truth for scopes: upload (videos.insert + publishAt) plus
# readonly (verify/list scheduled videos).
from scripts.youtube_uploader import SCOPES
REDIRECT_PORT = 8080


def _load_env() -> dict:
    try:
        from dotenv import dotenv_values
    except ImportError:
        sys.exit("python-dotenv not installed. Run: pip install -r skills/publish/requirements.txt")
    return dotenv_values(ENV_PATH)


def _write_refresh_token(token: str) -> None:
    """Replace the YOUTUBE_REFRESH_TOKEN line in .env, preserving everything else."""
    lines = ENV_PATH.read_text().splitlines()
    out, replaced = [], False
    for line in lines:
        if line.startswith("YOUTUBE_REFRESH_TOKEN="):
            out.append(f"YOUTUBE_REFRESH_TOKEN={token}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"YOUTUBE_REFRESH_TOKEN={token}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> None:
    env = _load_env()
    client_id = env.get("YOUTUBE_CLIENT_ID")
    client_secret = env.get("YOUTUBE_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET missing from skills/publish/.env")

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh token is returned.
    creds = flow.run_local_server(
        port=REDIRECT_PORT,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Opening browser to authorize YouTube upload access...",
        success_message="Authorized. You can close this tab and return to the terminal.",
    )

    if not creds.refresh_token:
        sys.exit("No refresh token returned. Revoke prior access at "
                 "https://myaccount.google.com/permissions and re-run.")

    _write_refresh_token(creds.refresh_token)
    print(f"\n✅ Refresh token saved to {ENV_PATH}")
    print("   You're ready to publish. Re-run is unnecessary unless access is revoked.")


if __name__ == "__main__":
    main()
