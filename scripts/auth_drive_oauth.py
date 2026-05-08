"""
One-time script to generate OAuth token for Google Drive.

Steps:
  1. Download OAuth client JSON from GCP Console and save as oauth-client.json
  2. Run: python scripts/auth_drive_oauth.py
  3. Browser opens → sign in with chiuno150@gmail.com → grant Drive access
  4. Token saved to oauth-token.json
  5. Add contents of oauth-token.json as GitHub Secret GOOGLE_OAUTH_TOKEN_JSON

Run only once locally. oauth-token.json is auto-refreshed by drive_api.py.
"""
import json
import sys
from pathlib import Path

CLIENT_FILE = "oauth-client.json"
TOKEN_FILE = "oauth-token.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def main():
    if not Path(CLIENT_FILE).exists():
        print(f"ERROR: {CLIENT_FILE} not found.")
        print("Download it from GCP Console → APIs & Services → Credentials → "
              "your OAuth 2.0 Client → Download JSON")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib")
        sys.exit(1)

    print("Opening browser for OAuth consent...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✅ Token saved to {TOKEN_FILE}")
    print("\nNext: add the token as a GitHub Secret named GOOGLE_OAUTH_TOKEN_JSON")
    print(f"  Copy this command (PowerShell):")
    print(f'  Get-Content {TOKEN_FILE} | gh secret set GOOGLE_OAUTH_TOKEN_JSON')


if __name__ == "__main__":
    main()
