"""
Butler Button — Zoho Scope Expander
Adds Mail, Cliq, Social, and Flow scopes to your existing Zoho credentials.
Takes 3 minutes. Run once, never again.

Usage:  python setup_scopes.py
"""

import webbrowser
import requests
import json
import os
import time
from pathlib import Path

CLIENT_ID = "1000.J7EWP6M6H1BB9FQNKNA6ZFRM271E9Y"
CLIENT_SECRET = "56fa1e7007381113f58b06c351e71b501add649f5f"
ENV_FILE = Path(__file__).parent / ".env"
SECRETS_FILE = Path.home() / ".openclaw/secrets/zoho-oauth.json"

NEW_SCOPES = ",".join([
    "ZohoCRM.modules.ALL",
    "ZohoCRM.bulk.ALL",
    "ZohoCRM.settings.ALL",
    "ZohoCampaigns.campaign.ALL",
    "ZohoCampaigns.contact.ALL",
    "ZohoMail.messages.ALL",
    "ZohoMail.folders.ALL",
    "ZohoCliq.channels.ALL",
    "ZohoCliq.messages.ALL",
    "ZohoSocial.profiles.ALL",
    "ZohoSocial.content.ALL",
    "ZohoFlow.flows.ALL",
])

STEPS = """
┌─────────────────────────────────────────────────────────────────┐
│           ZOHO SCOPE SETUP — 3 minutes, do it once             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  I'm opening api-console.zoho.in in your browser.             │
│                                                                 │
│  DO THIS:                                                       │
│  1. You should see your existing Self Client                    │
│     (named something like "openclaw" or "VELTM")               │
│  2. Click on it                                                 │
│  3. Click the "Generate Code" tab                               │
│  4. Paste ALL of this into the Scope box:                      │
│                                                                 │
{scopes}
│                                                                 │
│  5. Set "Time Duration" to the max (usually 10 minutes)        │
│  6. Click "Create"                                              │
│  7. Copy the code it shows you                                  │
│  8. Come back here and paste it                                 │
│                                                                 │
│  If you don't see a Self Client yet:                           │
│  "Add Client" → "Self Client" → create it first               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
"""


def update_env(key: str, value: str):
    if not ENV_FILE.exists():
        print(f"  Warning: {ENV_FILE} not found — skipping .env update")
        return
    content = ENV_FILE.read_text()
    lines = content.split("\n")
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines))


def main():
    print("\nButler Button — Zoho Scope Expander\n")

    # Open browser
    webbrowser.open("https://api-console.zoho.in")
    time.sleep(1)

    scope_display = "\n".join(f"│  {s}" for s in NEW_SCOPES.split(","))
    print(STEPS.format(scopes=scope_display))

    # Wait for code
    code = input("Paste your authorization code here: ").strip()
    if not code:
        print("No code entered. Exiting.")
        return

    print("\nExchanging code for tokens...")
    r = requests.post(
        "https://accounts.zoho.in/oauth/v2/token",
        params={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
        }
    )

    if r.status_code != 200:
        print(f"Error from Zoho: {r.text}")
        return

    data = r.json()
    if "error" in data:
        print(f"Zoho error: {data['error']}")
        if data.get("error") == "invalid_code":
            print("The code expired (only valid 10 minutes) or was already used.")
            print("Go back to api-console.zoho.in and generate a fresh code.")
        return

    refresh_token = data.get("refresh_token", "")
    access_token = data.get("access_token", "")
    scopes = data.get("scope", "")

    if not refresh_token:
        print("No refresh token returned. Make sure you checked 'offline_access' scope.")
        print(f"Response: {json.dumps(data, indent=2)}")
        return

    # Get user's email from Zoho accounts
    from_email = ""
    try:
        mail_r = requests.get(
            "https://mail.zoho.in/api/accounts",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
        )
        accounts = mail_r.json().get("data", [])
        if accounts:
            from_email = accounts[0].get("primaryEmailAddress", "")
    except Exception:
        pass

    # Update .env
    update_env("ZOHO_REFRESH_TOKEN", refresh_token)
    if from_email:
        update_env("ZOHO_MAIL_FROM", from_email)

    # Update secrets file
    if SECRETS_FILE.exists():
        secrets = json.loads(SECRETS_FILE.read_text())
        secrets["refresh_token"] = refresh_token
        secrets["access_token"] = access_token
        secrets["scopes"] = scopes
        SECRETS_FILE.write_text(json.dumps(secrets, indent=2))

    print("\n" + "─" * 60)
    print("  DONE. Credentials updated.")
    print(f"  Refresh token: {refresh_token[:30]}...")
    if from_email:
        print(f"  Mail from:     {from_email}")
    print(f"  Scopes active: {len(scopes.split())} scopes")
    print("─" * 60)
    print("\n  Test it: python agents/agent_morning_brief.py")
    print()


if __name__ == "__main__":
    main()
