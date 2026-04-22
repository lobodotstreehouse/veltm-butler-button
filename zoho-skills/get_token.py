"""
One-click Zoho token refresh.
Run it, click Accept in the browser, done.
"""
import http.server, threading, webbrowser, urllib.parse, requests, json, sys
from pathlib import Path

CLIENT_ID     = "1000.J7EWP6M6H1BB9FQNKNA6ZFRM271E9Y"
CLIENT_SECRET = "56fa1e7007381113f58b06c351e71b501add649f5f"
REDIRECT_URI  = "http://localhost:9000/callback"
ENV_FILE      = Path(__file__).parent / ".env"
SECRETS_FILE  = Path.home() / ".openclaw/secrets/zoho-oauth.json"

SCOPES = ",".join([
    "ZohoCRM.modules.ALL", "ZohoCRM.bulk.ALL", "ZohoCRM.settings.ALL",
    "ZohoCampaigns.campaign.ALL", "ZohoCampaigns.contact.ALL",
    "ZohoMail.messages.ALL", "ZohoMail.folders.ALL",
    "ZohoCliq.channels.ALL", "ZohoCliq.messages.ALL",
    "ZohoSocial.profiles.ALL", "ZohoSocial.content.ALL",
    "ZohoFlow.flows.ALL",
])

_code = None
_done = threading.Event()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        global _code
        # Only handle /callback
        if not self.path.startswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _code = (qs.get("code") or [None])[0]
        body = b"<h2 style='font-family:sans-serif;color:green'>Authorized. Close this tab.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
        _done.set()

def update_env(key, value):
    if not ENV_FILE.exists(): return
    lines = ENV_FILE.read_text().split("\n")
    found = False
    for i, l in enumerate(lines):
        if l.startswith(f"{key}=") or l.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"; found = True; break
    if not found: lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines))

print("  Starting local callback server on port 9000...", flush=True)
server = http.server.HTTPServer(("localhost", 9000), Handler)
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()

auth_url = (
    "https://accounts.zoho.in/oauth/v2/auth"
    f"?response_type=code&client_id={CLIENT_ID}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    "&access_type=offline&prompt=consent"
)

print("  Opening Zoho authorization in browser...", flush=True)
print(f"  URL: {auth_url[:80]}...", flush=True)
webbrowser.open(auth_url)
print("  Waiting for you to click Accept in the browser (5 min timeout)...", flush=True)

_done.wait(timeout=300)
server.shutdown()

if not _code:
    print("  Timed out. Run again.")
    sys.exit(1)

print(f"  Code received ({_code[:20]}...). Exchanging for tokens...", flush=True)

r = requests.post("https://accounts.zoho.in/oauth/v2/token", data={
    "code": _code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code",
})
data = r.json()

if "error" in data:
    print(f"  Error: {json.dumps(data)}")
    sys.exit(1)

refresh = data.get("refresh_token", "")
access  = data.get("access_token", "")
scope   = data.get("scope", "")

if not refresh:
    print("  No refresh token. Response:", json.dumps(data, indent=2))
    sys.exit(1)

# Discover mail from-address
from_email = ""
try:
    mr = requests.get("https://mail.zoho.in/api/accounts",
                      headers={"Authorization": f"Zoho-oauthtoken {access}"})
    accts = mr.json().get("data", [])
    if accts:
        from_email = accts[0].get("primaryEmailAddress", "")
except Exception:
    pass

update_env("ZOHO_REFRESH_TOKEN", refresh)
update_env("ZOHO_ACCESS_TOKEN",  access)
if from_email:
    update_env("ZOHO_MAIL_FROM", from_email)

if SECRETS_FILE.exists():
    s = json.loads(SECRETS_FILE.read_text())
    s.update({"refresh_token": refresh, "access_token": access, "scopes": scope})
    SECRETS_FILE.write_text(json.dumps(s, indent=2))

print(f"\n  DONE.")
print(f"  Refresh token : {refresh[:40]}...")
print(f"  Mail from     : {from_email or '(not detected)'}")
print(f"  Scopes active : {len(scope.split(','))} scopes\n")
