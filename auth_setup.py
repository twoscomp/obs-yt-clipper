#!/usr/bin/env python3
"""
One-time OAuth setup script for YouTube API authentication.
Run this once to authorize the application and save the refresh token.
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CONFIG_DIR = Path.home() / ".config" / "obs-yt-clipper"
DEFAULT_CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = CONFIG_DIR / "token.json"


def main():
    print("=== OBS YouTube Clip Uploader - OAuth Setup ===\n")

    credentials_path = DEFAULT_CREDENTIALS_PATH
    token_path = DEFAULT_TOKEN_PATH

    if not credentials_path.exists():
        print(f"ERROR: Credentials file not found at: {credentials_path}")
        print("\nTo set up YouTube API credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable 'YouTube Data API v3'")
        print("4. Go to 'Credentials' and create OAuth 2.0 Client ID")
        print("5. Choose 'Desktop app' as the application type")
        print("6. Download the JSON credentials file")
        print(f"7. Save it as: {credentials_path}")
        print("\nThen run this script again.")
        sys.exit(1)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using credentials from: {credentials_path}")
    print("\nThis will open a browser window for you to authorize the application.")
    print("After authorization, the refresh token will be saved locally.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

        print(f"\nSuccess! Token saved to: {token_path}")
        print("\nYou can now use the OBS clip uploader.")
        print("The token will automatically refresh when needed.")

    except Exception as e:
        print(f"\nError during authentication: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
