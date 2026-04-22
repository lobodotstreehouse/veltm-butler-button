"""
Butler Button — LinkedIn Personal Posting Skill
-------------------------------------------------
Posts directly to Carl Remi Beauregard's personal LinkedIn profile
(3,334 followers) via the LinkedIn UGC Posts API.

This module is intentionally separate from skills_social.py (Ayrshare)
because it uses a personal OAuth token, not an organisation-level key.

ENV VARS (add to zoho-skills/.env):
    LINKEDIN_CLIENT_ID              — App client ID from LinkedIn Developer Portal
    LINKEDIN_CLIENT_SECRET          — App client secret
    LINKEDIN_PERSONAL_ACCESS_TOKEN  — 3-legged OAuth Bearer token (60-day max)
    LINKEDIN_PERSON_ID              — urn:li:person:XXXX (auto-populated on first run)

OAUTH SCOPES REQUIRED:
    w_member_social   — create, update, delete posts
    r_liteprofile     — read person URN
    openid + profile  — needed by /v2/userinfo endpoint

Skills:
    get_profile_id          — Fetch & cache the authenticated person URN
    post_text               — Post a plain-text update to personal profile
    post_with_article       — Post with a linked article / URL share
    get_recent_posts        — Fetch recent personal UGC posts
    setup_instructions      — Print exact OAuth app setup steps
"""

import os
import json
import requests
from dotenv import load_dotenv, set_key

# ── Credential loading ────────────────────────────────────────────────────────

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH, override=True)

LI_BASE = "https://api.linkedin.com/v2"

# Resolved at call time so a freshly written .env value is picked up mid-session.
def _token() -> str:
    return os.environ.get("LINKEDIN_PERSONAL_ACCESS_TOKEN", "")

def _person_id() -> str:
    return os.environ.get("LINKEDIN_PERSON_ID", "")

def _headers() -> dict:
    tok = _token()
    if not tok:
        raise EnvironmentError(
            "LINKEDIN_PERSONAL_ACCESS_TOKEN is not set. "
            "Run setup_instructions() for steps."
        )
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


# ── Core helpers ──────────────────────────────────────────────────────────────

def _handle_response(r: requests.Response, ok_statuses=(200, 201)) -> dict:
    """Parse a LinkedIn API response into a normalised dict."""
    if r.status_code in ok_statuses:
        body = {}
        if r.text:
            try:
                body = r.json()
            except ValueError:
                body = {"raw": r.text}
        # UGC post creation returns the post ID in the X-RestLi-Id header
        post_id = r.headers.get("X-RestLi-Id") or r.headers.get("x-restli-id") or body.get("id", "")
        return {"status": "ok", "http": r.status_code, "post_id": post_id, **body}
    try:
        err = r.json()
    except ValueError:
        err = {"raw": r.text}
    return {"status": "error", "http": r.status_code, "error": err}


# ── Public Skills ─────────────────────────────────────────────────────────────

def get_profile_id() -> str:
    """Fetch the authenticated user's person URN and cache it in .env.

    Calls GET /v2/userinfo (OpenID Connect endpoint).
    Sets LINKEDIN_PERSON_ID in process env and writes it back to .env so
    subsequent calls skip the network round-trip.

    Returns:
        Person URN string, e.g. "urn:li:person:AbCdEfGhIj"
        Returns "" and prints a warning on error.
    """
    cached = _person_id()
    if cached:
        return cached

    try:
        r = requests.get(f"{LI_BASE}/userinfo", headers=_headers(), timeout=10)
    except requests.RequestException as exc:
        print(f"[linkedin_personal] get_profile_id network error: {exc}")
        return ""

    if r.status_code != 200:
        print(f"[linkedin_personal] get_profile_id failed: {r.status_code} {r.text}")
        return ""

    data = r.json()
    # /v2/userinfo returns the sub as the person's numeric ID
    sub = data.get("sub", "")
    if not sub:
        print(f"[linkedin_personal] get_profile_id: unexpected response shape: {data}")
        return ""

    urn = f"urn:li:person:{sub}"
    # Cache in process and persist to .env
    os.environ["LINKEDIN_PERSON_ID"] = urn
    try:
        set_key(_ENV_PATH, "LINKEDIN_PERSON_ID", urn)
    except Exception:
        pass  # Non-fatal — env var is still set for this session
    print(f"[linkedin_personal] Person URN cached: {urn}")
    return urn


def post_text(content: str) -> dict:
    """Post a plain-text update to Carl Remi Beauregard's LinkedIn profile.

    Uses the UGC Posts API with shareMediaCategory NONE.
    The post is published immediately (lifecycleState PUBLISHED) and visible
    to all connections and followers (MemberNetworkVisibility PUBLIC).

    Args:
        content: The post body text. LinkedIn recommends under 3,000 characters
                 for feed posts; the API accepts up to 700 chars for most users.
    Returns:
        dict — {"status": "posted"|"error", "post_id": str, ...}
    """
    if not content or not content.strip():
        return {"status": "error", "error": "content must not be empty"}

    author = get_profile_id() if not _person_id() else _person_id()
    if not author:
        return {"status": "error", "error": "Could not resolve LINKEDIN_PERSON_ID"}

    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content.strip()},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    try:
        r = requests.post(
            f"{LI_BASE}/ugcPosts",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        return {"status": "error", "error": str(exc)}

    result = _handle_response(r)
    if result["status"] == "ok":
        result["status"] = "posted"
        result["char_count"] = len(content)
    return result


def post_with_article(
    content: str,
    article_url: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Post a LinkedIn update that includes an article / URL share.

    LinkedIn will attempt to scrape OG tags from article_url if title and
    description are not supplied, but providing them prevents inconsistent
    previews.

    Args:
        content:     Commentary text above the link preview (the post body).
        article_url: Fully qualified URL to share (must start with https://).
        title:       Optional article headline for the link preview card.
        description: Optional article description for the link preview card.
    Returns:
        dict — {"status": "posted"|"error", "post_id": str, ...}
    """
    if not content or not content.strip():
        return {"status": "error", "error": "content must not be empty"}
    if not article_url or not article_url.startswith("http"):
        return {"status": "error", "error": "article_url must be a valid https:// URL"}

    author = get_profile_id() if not _person_id() else _person_id()
    if not author:
        return {"status": "error", "error": "Could not resolve LINKEDIN_PERSON_ID"}

    media_entry: dict = {
        "status": "READY",
        "originalUrl": article_url,
    }
    if title:
        media_entry["title"] = {"text": title}
    if description:
        media_entry["description"] = {"text": description}

    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content.strip()},
                "shareMediaCategory": "ARTICLE",
                "media": [media_entry],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    try:
        r = requests.post(
            f"{LI_BASE}/ugcPosts",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        return {"status": "error", "error": str(exc)}

    result = _handle_response(r)
    if result["status"] == "ok":
        result["status"] = "posted"
        result["article_url"] = article_url
    return result


def get_recent_posts(count: int = 10) -> list:
    """Fetch the most recent UGC posts authored by the authenticated user.

    Uses GET /v2/ugcPosts filtered by author URN.
    Requires r_member_social scope (see note in setup_instructions()).

    Args:
        count: Number of posts to return (max 100 per LinkedIn page).
    Returns:
        List of post dicts from the LinkedIn API, or a single-item list
        with an error dict on failure.
    """
    author = get_profile_id() if not _person_id() else _person_id()
    if not author:
        return [{"status": "error", "error": "Could not resolve LINKEDIN_PERSON_ID"}]

    params = {
        "q": "authors",
        "authors": f"List({author})",
        "count": min(int(count), 100),
    }

    try:
        r = requests.get(
            f"{LI_BASE}/ugcPosts",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    except requests.RequestException as exc:
        return [{"status": "error", "error": str(exc)}]

    if r.status_code != 200:
        try:
            err = r.json()
        except ValueError:
            err = r.text
        return [{"status": "error", "http": r.status_code, "error": err}]

    data = r.json()
    return data.get("elements", [])


def setup_instructions() -> str:
    """Return step-by-step instructions for creating a LinkedIn app and access token.

    The LinkedIn UGC Posts API requires a 3-legged OAuth flow — there is no
    long-lived service account token. You must re-authorise every 60 days.

    Returns:
        Multi-line string with the exact setup steps.
    """
    return """
LinkedIn Personal Posting — One-Time Setup
==========================================

Step 1 — Create a LinkedIn App
  1. Go to https://www.linkedin.com/developers/apps/new
  2. App name: "Butler Button CSMO" (or any internal name)
  3. LinkedIn Page: link to the VELTM Tours company page (or create one)
  4. App Logo: upload any image
  5. Click "Create app"

Step 2 — Configure OAuth Scopes
  1. In your new app, open the "Products" tab
  2. Request access to "Share on LinkedIn"  (grants w_member_social, r_liteprofile)
  3. Request access to "Sign In with LinkedIn using OpenID Connect"  (grants openid, profile)
     — This is needed for the /v2/userinfo call that resolves your person URN.
  4. Wait for LinkedIn to approve (usually instant for w_member_social / openid)

Step 3 — Get your Client ID and Secret
  1. "Auth" tab → copy "Client ID"  → add to .env as LINKEDIN_CLIENT_ID
  2. "Auth" tab → copy "Client Secret" → add to .env as LINKEDIN_CLIENT_SECRET

Step 4 — Authorise and Get a 60-Day Access Token
  Option A — LinkedIn Token Generator (fastest, valid 60 days)
    1. In your app → "Auth" tab → scroll to "OAuth 2.0 tools" section
    2. Click "OAuth Token Tools" or go to:
       https://www.linkedin.com/developers/tools/oauth/token-generator
    3. Select scopes: openid, profile, w_member_social, r_liteprofile
    4. Click "Request access token"
    5. Authorise as Carl Remi Beauregard when prompted
    6. Copy the generated token → add to .env as LINKEDIN_PERSONAL_ACCESS_TOKEN

  Option B — Manual 3-legged OAuth (if Token Generator is unavailable)
    1. Add a redirect URI in Auth tab: https://localhost:8000/callback
    2. Build the authorisation URL:
         https://www.linkedin.com/oauth/v2/authorization
           ?response_type=code
           &client_id=YOUR_CLIENT_ID
           &redirect_uri=https://localhost:8000/callback
           &scope=openid%20profile%20w_member_social%20r_liteprofile
    3. Visit the URL in a browser logged in as Carl Remi Beauregard
    4. Copy the "code" parameter from the redirect URL
    5. Exchange it:
         curl -X POST https://www.linkedin.com/oauth/v2/accessToken \\
           -d "grant_type=authorization_code" \\
           -d "code=CODE_FROM_STEP_4" \\
           -d "redirect_uri=https://localhost:8000/callback" \\
           -d "client_id=YOUR_CLIENT_ID" \\
           -d "client_secret=YOUR_CLIENT_SECRET"
    6. Copy access_token → add to .env as LINKEDIN_PERSONAL_ACCESS_TOKEN

Step 5 — Get your Person URN (auto-populated)
  LINKEDIN_PERSON_ID is written to .env automatically the first time
  get_profile_id() or any post function runs successfully.
  You can also set it manually: urn:li:person:YOUR_NUMERIC_ID
  (Find your numeric ID at: https://www.linkedin.com/in/YOUR_SLUG?trk=contacts-contacts)

Step 6 — Verify
  python skills_linkedin_personal.py
  (The __main__ block will print a config status check without touching the network.)

TOKEN RENEWAL
  Access tokens expire after 60 days. LinkedIn does not issue refresh tokens for
  the Member Authorization (3-legged) flow used here. You must re-run Step 4
  every 60 days to get a new token and update LINKEDIN_PERSONAL_ACCESS_TOKEN in .env.
  Set a 55-day calendar reminder.

TROUBLESHOOTING
  403 on POST /ugcPosts  → scope w_member_social is missing or app not approved
  401 Unauthorized       → token expired; re-run Step 4
  404 on /v2/userinfo    → openid/profile product not added to the app (Step 2)
"""


# ── Module-level __main__ (syntax / import check only) ───────────────────────

if __name__ == "__main__":
    print("skills_linkedin_personal — import OK")
    print()

    # Report env var status without making any network calls
    checks = {
        "LINKEDIN_CLIENT_ID":             os.environ.get("LINKEDIN_CLIENT_ID", ""),
        "LINKEDIN_CLIENT_SECRET":         os.environ.get("LINKEDIN_CLIENT_SECRET", ""),
        "LINKEDIN_PERSONAL_ACCESS_TOKEN": os.environ.get("LINKEDIN_PERSONAL_ACCESS_TOKEN", ""),
        "LINKEDIN_PERSON_ID":             os.environ.get("LINKEDIN_PERSON_ID", ""),
    }

    all_set = True
    for key, val in checks.items():
        status = "SET" if val else "MISSING"
        if not val:
            all_set = False
        print(f"  {key:<35} {status}")

    print()
    if all_set:
        print("All credentials present. Ready to post.")
    else:
        print("Some credentials are missing. Run setup_instructions() for steps.")
        print()
        print(setup_instructions())
