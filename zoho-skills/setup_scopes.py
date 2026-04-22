"""
Butler Button — Zoho Scope Expander
Adds Mail, Cliq, Social, and Flow scopes to your existing Zoho credentials.

STEP 1 — run with no args:
    python setup_scopes.py

STEP 2 — paste the code from api-console.zoho.in back here:
    python setup_scopes.py 1000.abc123...
"""

import sys
import webbrowser
import requests
import json
from pathlib import Path

CLIENT_ID     = "1000.J7EWP6M6H1BB9FQNKNA6ZFRM271E9Y"
CLIENT_SECRET = "56fa1e7007381113f58b06c351e71b501add649f5f"
ENV_FILE      = Path(__file__).parent / ".env"
SECRETS_FILE  = Path.home() / ".openclaw/secrets/zoho-oauth.json"

SCOPES = ",".join([
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


def show_instructions():
    webbrowser.open("https://api-console.zoho.in")
    print("""
╔══════════════════════════════════════════════════════════════╗
║         STEP 1 — Get your authorization code                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Browser just opened to api-console.zoho.in                 ║
║                                                              ║
║  1. Click your existing Self Client (or create one)          ║
║  2. Click the "Generate Code" tab                            ║
║  3. Paste this entire block into the Scope field:            ║
║                                                              ║""")
    for s in SCOPES.split(","):
        print(f"║    {s:<56} ║")
    print("""║                                                              ║
║  4. Set Time Duration → 10 minutes                           ║
║  5. Click "Create"  — copy the code it shows you            ║
║                                                              ║
║  STEP 2 — run:                                               ║
║    python setup_scopes.py  PASTE_CODE_HERE                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def exchange_code(code: str):
    print(f"\nExchanging code for tokens...")
    r = requests.post(
        "https://accounts.zoho.in/oauth/v2/token",
        params={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
        }
    )
    data = r.json()

    if "error" in data:
        err = data["error"]
        if err == "invalid_code":
            print("ERROR: Code expired or already used (valid 10 min).")
            print("       Run 'python setup_scopes.py' again to get a fresh one.")
        else:
            print(f"ERROR from Zoho: {json.dumps(data, indent=2)}")
        sys.exit(1)

    refresh_token = data.get("refresh_token", "")
    access_token  = data.get("access_token", "")
    scope_str     = data.get("scope", "")

    if not refresh_token:
        print("No refresh token returned.")
        print(json.dumps(data, indent=2))
        sys.exit(1)

    # Discover Zoho Mail from-address
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
    _update_env("ZOHO_REFRESH_TOKEN", refresh_token)
    _update_env("ZOHO_ACCESS_TOKEN",  access_token)
    if from_email:
        _update_env("ZOHO_MAIL_FROM", from_email)

    # Update secrets file
    if SECRETS_FILE.exists():
        secrets = json.loads(SECRETS_FILE.read_text())
        secrets["refresh_token"] = refresh_token
        secrets["access_token"]  = access_token
        secrets["scopes"]        = scope_str
        SECRETS_FILE.write_text(json.dumps(secrets, indent=2))

    print("─" * 60)
    print("  DONE. Credentials updated.")
    print(f"  Refresh token : {refresh_token[:35]}...")
    print(f"  Mail from     : {from_email or '(not found — add manually to .env)'}")
    n = len(scope_str.split(",")) if scope_str else 0
    print(f"  Scopes active : {n}")
    print("─" * 60)
    print("\n  Test: python agents/agent_morning_brief.py\n")


def _update_env(key: str, value: str):
    if not ENV_FILE.exists():
        return
    lines = ENV_FILE.read_text().split("\n")
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_instructions()
    else:
        exchange_code(sys.argv[1].strip())
