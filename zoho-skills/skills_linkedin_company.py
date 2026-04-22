"""
Butler Button — LinkedIn Company Page Skill (VELTM Organization)
-----------------------------------------------------------------
Posts as the VELTM LinkedIn organization page using the UGC Posts API.
Shares the same LinkedIn app credentials (LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET)
as skills_linkedin_personal.py, but uses a separate access token and org ID.

ENV VARS REQUIRED (.env):
  LINKEDIN_CLIENT_ID          — shared with personal LinkedIn skill
  LINKEDIN_CLIENT_SECRET      — shared with personal LinkedIn skill
  LINKEDIN_COMPANY_ACCESS_TOKEN — OAuth2 bearer token with org scopes (see setup_instructions)
  LINKEDIN_ORG_ID             — numeric ID of the VELTM org page
                                  (linkedin.com/company/{ORG_ID} URL slug is NOT the numeric ID;
                                   use setup_instructions() for how to retrieve it)

REQUIRED OAUTH SCOPES (on the access token):
  w_organization_social       — post as org
  r_organization_social       — read org posts / analytics
  rw_organization_admin       — read follower counts

Skills:
  post_text               — Post plain text as VELTM company page
  post_with_article       — Post with a link/article share
  get_org_followers       — Fetch follower count
  get_recent_posts        — Fetch recent company posts
  setup_instructions      — Step-by-step guide to obtain tokens and org ID
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
_ORG_STATS_URL = "https://api.linkedin.com/v2/organizationalEntityFollowerStatistics"
_SHARES_URL    = "https://api.linkedin.com/v2/shares"


def _token() -> str:
    """Return the company access token, or raise clearly if missing."""
    tok = os.environ.get("LINKEDIN_COMPANY_ACCESS_TOKEN", "").strip()
    if not tok:
        raise EnvironmentError(
            "LINKEDIN_COMPANY_ACCESS_TOKEN is not set. "
            "Run setup_instructions() for steps to obtain it."
        )
    return tok


def _org_id() -> str:
    """Return the numeric org ID, or raise clearly if missing."""
    oid = os.environ.get("LINKEDIN_ORG_ID", "").strip()
    if not oid:
        raise EnvironmentError(
            "LINKEDIN_ORG_ID is not set. "
            "Run setup_instructions() for steps to find it."
        )
    return oid


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


# ── Core posting ──────────────────────────────────────────────────────────────

def post_text(content: str) -> dict:
    """Post plain text as the VELTM LinkedIn organization page.

    Args:
        content: The text body of the post (max ~3000 chars recommended by LinkedIn)
    Returns:
        dict with 'status' ('posted' | 'error'), 'post_id', and on error 'message'
    """
    if not content or not content.strip():
        return {"status": "error", "message": "content must not be empty"}

    try:
        org_urn = f"urn:li:organization:{_org_id()}"
        payload = {
            "author": org_urn,
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
        r = requests.post(_UGC_POSTS_URL, headers=_auth_headers(), json=payload, timeout=15)
        if r.status_code == 201:
            post_id = r.headers.get("x-restli-id", "")
            return {"status": "posted", "post_id": post_id, "author": org_urn, "http": 201}
        return {
            "status": "error",
            "http": r.status_code,
            "message": r.text[:400],
        }
    except EnvironmentError as exc:
        return {"status": "error", "message": str(exc)}
    except requests.RequestException as exc:
        return {"status": "error", "message": f"Network error: {exc}"}


def post_with_article(
    content: str,
    article_url: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Post with a link/article share as the VELTM company page.

    Args:
        content:     Commentary text shown above the link card
        article_url: The URL to share (must be publicly accessible for LinkedIn to card it)
        title:       Optional override for the link card title
        description: Optional override for the link card description
    Returns:
        dict with 'status' ('posted' | 'error'), 'post_id', and on error 'message'
    """
    if not content or not content.strip():
        return {"status": "error", "message": "content must not be empty"}
    if not article_url or not article_url.strip():
        return {"status": "error", "message": "article_url must not be empty"}

    try:
        org_urn = f"urn:li:organization:{_org_id()}"
        media_entry: dict = {
            "status": "READY",
            "originalUrl": article_url.strip(),
        }
        if title:
            media_entry["title"] = {"text": title.strip()}
        if description:
            media_entry["description"] = {"text": description.strip()}

        payload = {
            "author": org_urn,
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
        r = requests.post(_UGC_POSTS_URL, headers=_auth_headers(), json=payload, timeout=15)
        if r.status_code == 201:
            post_id = r.headers.get("x-restli-id", "")
            return {
                "status": "posted",
                "post_id": post_id,
                "author": org_urn,
                "article_url": article_url,
                "http": 201,
            }
        return {
            "status": "error",
            "http": r.status_code,
            "message": r.text[:400],
        }
    except EnvironmentError as exc:
        return {"status": "error", "message": str(exc)}
    except requests.RequestException as exc:
        return {"status": "error", "message": f"Network error: {exc}"}


# ── Analytics & reads ─────────────────────────────────────────────────────────

def get_org_followers() -> int:
    """Fetch the current follower count for the VELTM LinkedIn organization page.

    Returns:
        Follower count as int, or -1 on error (check stderr for detail).
    """
    try:
        org_urn = f"urn:li:organization:{_org_id()}"
        params = {"q": "organizationalEntity", "organizationalEntity": org_urn}
        r = requests.get(
            _ORG_STATS_URL,
            headers=_auth_headers(),
            params=params,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            elements = data.get("elements", [])
            if elements:
                # firstDegreeSize is the direct follower count
                return elements[0].get("followerCounts", {}).get("firstDegreeSize", 0)
        # Fallback: try the organization lookup endpoint for a simpler count
        org_url = f"https://api.linkedin.com/v2/organizations/{_org_id()}"
        r2 = requests.get(org_url, headers=_auth_headers(), timeout=15)
        if r2.status_code == 200:
            org_data = r2.json()
            return org_data.get("followersCount", 0)
        import sys
        print(
            f"[linkedin_company] get_org_followers HTTP {r.status_code}: {r.text[:200]}",
            file=sys.stderr,
        )
        return -1
    except EnvironmentError as exc:
        import sys
        print(f"[linkedin_company] {exc}", file=sys.stderr)
        return -1
    except requests.RequestException as exc:
        import sys
        print(f"[linkedin_company] Network error in get_org_followers: {exc}", file=sys.stderr)
        return -1


def get_recent_posts(count: int = 10) -> list:
    """Fetch recent posts made by the VELTM company page.

    Requires r_organization_social scope on the token.

    Args:
        count: Number of posts to retrieve (1-50; LinkedIn max per page is 50)
    Returns:
        List of dicts with 'post_id', 'text', 'created', 'lifecycle_state'.
        Returns empty list on error.
    """
    count = max(1, min(count, 50))
    try:
        org_urn = f"urn:li:organization:{_org_id()}"
        params = {
            "q": "authors",
            "authors": f"List({org_urn})",
            "count": count,
            "sortBy": "LAST_MODIFIED",
        }
        r = requests.get(
            _UGC_POSTS_URL,
            headers=_auth_headers(),
            params=params,
            timeout=15,
        )
        if r.status_code != 200:
            import sys
            print(
                f"[linkedin_company] get_recent_posts HTTP {r.status_code}: {r.text[:200]}",
                file=sys.stderr,
            )
            return []
        elements = r.json().get("elements", [])
        posts = []
        for el in elements:
            share_content = (
                el.get("specificContent", {})
                  .get("com.linkedin.ugc.ShareContent", {})
            )
            text = share_content.get("shareCommentary", {}).get("text", "")
            posts.append({
                "post_id": el.get("id", ""),
                "text": text,
                "created": el.get("created", {}).get("time", 0),
                "lifecycle_state": el.get("lifecycleState", ""),
            })
        return posts
    except EnvironmentError as exc:
        import sys
        print(f"[linkedin_company] {exc}", file=sys.stderr)
        return []
    except requests.RequestException as exc:
        import sys
        print(f"[linkedin_company] Network error in get_recent_posts: {exc}", file=sys.stderr)
        return []


# ── Setup guide ───────────────────────────────────────────────────────────────

def setup_instructions() -> str:
    """Return exact steps to configure the LinkedIn company posting skill.

    Returns:
        Multi-line string with numbered setup steps.
    """
    return """
LinkedIn Company Page (VELTM) — Setup Instructions
====================================================

SAME APP as personal LinkedIn skill. You only need ONE LinkedIn developer app.

STEP 1 — Find your numeric Org ID
  a. Go to: https://www.linkedin.com/company/[your-slug]/admin/
  b. Look at the URL in your browser — it will change to something like:
       https://www.linkedin.com/company/12345678/admin/
  c. That 8-digit number (e.g. 12345678) is your LINKEDIN_ORG_ID.
  d. Add to .env:  LINKEDIN_ORG_ID=12345678

STEP 2 — Ensure the LinkedIn app has the right products / scopes
  a. Go to https://www.linkedin.com/developers/apps → select your app
  b. Under the "Products" tab, request access to:
       - "Share on LinkedIn"                      (w_member_social)
       - "Sign In with LinkedIn using OpenID"     (openid, profile, email)
       - "Marketing Developer Platform"           (r_organization_social,
                                                   w_organization_social,
                                                   rw_organization_admin)
  c. Marketing Developer Platform may require a brief review (1-3 business days).
  d. Once approved, your app's OAuth scopes should include:
       r_organization_social, w_organization_social, rw_organization_admin

STEP 3 — Generate a company access token with org scopes
  This is a SEPARATE token from the personal token.

  Option A — OAuth 2.0 Authorization Code flow (recommended for production):
    1. Build the authorization URL:
         https://www.linkedin.com/oauth/v2/authorization
           ?response_type=code
           &client_id={LINKEDIN_CLIENT_ID}
           &redirect_uri={YOUR_REDIRECT_URI}
           &scope=w_organization_social%20r_organization_social%20rw_organization_admin
    2. Visit the URL while logged in as a Company Page admin.
    3. Exchange the returned code for a token:
         POST https://www.linkedin.com/oauth/v2/accessToken
           grant_type=authorization_code
           &code={CODE}
           &client_id={LINKEDIN_CLIENT_ID}
           &client_secret={LINKEDIN_CLIENT_SECRET}
           &redirect_uri={YOUR_REDIRECT_URI}
    4. Copy the access_token value.

  Option B — LinkedIn Token Inspector / quick test:
    Use https://www.linkedin.com/developers/tools/oauth/token-generator
    Select scopes: r_organization_social, w_organization_social, rw_organization_admin
    (Token expires in 60 days — fine for testing, not for production.)

STEP 4 — Add to .env
  LINKEDIN_CLIENT_ID=your_app_client_id
  LINKEDIN_CLIENT_SECRET=your_app_client_secret
  LINKEDIN_COMPANY_ACCESS_TOKEN=your_org_scoped_token_here
  LINKEDIN_ORG_ID=12345678

STEP 5 — Verify
  Run:  python skills_linkedin_company.py
  Expected output: syntax OK + env var check block (no live API calls).

NOTES:
  - The token owner must be a Super Admin or Content Admin of the VELTM page.
  - Access tokens expire in 60 days. Plan a refresh flow for production.
  - w_organization_social posts appear on the company page timeline immediately.
  - If you get 403 on post_text(), confirm the token was generated by a Page Admin.
""".strip()


# ── __main__ syntax / env check ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("skills_linkedin_company.py — syntax OK")

    missing = []
    for var in ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
                "LINKEDIN_COMPANY_ACCESS_TOKEN", "LINKEDIN_ORG_ID"):
        val = os.environ.get(var, "")
        status = "SET" if val else "MISSING"
        print(f"  {var}: {status}")
        if not val:
            missing.append(var)

    if missing:
        print(f"\n  {len(missing)} env var(s) not set — run setup_instructions() for steps.")
        print(setup_instructions())
        sys.exit(0)   # Not an error at syntax-check time

    print("\n  All env vars present. Import and call post_text() to test live posting.")
    print("  Example:\n    from skills_linkedin_company import post_text")
    print("    result = post_text('Test post from VELTM Butler Button')")
    print("    print(result)")
