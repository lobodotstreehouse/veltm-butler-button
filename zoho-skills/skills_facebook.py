"""
Butler Button — Facebook Graph API Skill
------------------------------------------
Direct posting to the VELTM TOURS Facebook Page via Graph API v19.0.
No third-party publishing intermediary required.

Required env vars (add to zoho-skills/.env):
  FACEBOOK_APP_ID             — from developers.facebook.com
  FACEBOOK_APP_SECRET         — from the same app
  FACEBOOK_PAGE_ID            — numeric ID of the VELTM TOURS Facebook Page
  FACEBOOK_PAGE_ACCESS_TOKEN  — long-lived page token (60 days); see setup_instructions()

Skills:
  post_to_page        — publish or schedule a post on the VELTM TOURS page
  get_page_token      — exchange a user token for a long-lived page token
  get_recent_posts    — fetch recent posts with engagement metrics
  setup_instructions  — print step-by-step token setup guide
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

GRAPH_BASE = "https://graph.facebook.com/v19.0"

# Read credentials at import time so they reflect the loaded env
def _page_id() -> str:
    return os.environ.get("FACEBOOK_PAGE_ID", "")

def _page_token() -> str:
    return os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")

def _app_id() -> str:
    return os.environ.get("FACEBOOK_APP_ID", "")

def _app_secret() -> str:
    return os.environ.get("FACEBOOK_APP_SECRET", "")


# ── Core API helper ────────────────────────────────────────────────────────────

def _graph(method: str, path: str, **kwargs) -> dict:
    """Thin wrapper around requests for Graph API calls."""
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    try:
        r = getattr(requests, method)(url, timeout=15, **kwargs)
        data = r.json()
        if "error" in data:
            return {
                "status": "error",
                "http": r.status_code,
                "fb_error": data["error"].get("message", str(data["error"])),
                "fb_code": data["error"].get("code"),
                "raw": data,
            }
        return data
    except requests.exceptions.Timeout:
        return {"status": "error", "fb_error": "Request timed out after 15 s"}
    except requests.exceptions.RequestException as exc:
        return {"status": "error", "fb_error": str(exc)}


# ── Public Skills ──────────────────────────────────────────────────────────────

def post_to_page(content: str, link: str = None, scheduled_unix: int = None) -> dict:
    """Publish or schedule a post on the VELTM TOURS Facebook Page.

    Uses Facebook Graph API v19.0: POST /{page-id}/feed

    Args:
        content:        Post message text.
        link:           Optional URL to attach as a link preview.
        scheduled_unix: Unix timestamp (UTC) to schedule the post.
                        Must be between 10 minutes and 30 days in the future.
                        When provided the post is created in draft/scheduled state.
    Returns:
        dict with keys:
          status   — "posted" | "scheduled" | "error"
          post_id  — Facebook post ID on success
          message  — human-readable summary
          (on error) fb_error, fb_code
    """
    page_id = _page_id()
    token = _page_token()

    if not page_id:
        return {
            "status": "error",
            "message": "FACEBOOK_PAGE_ID not set in .env — run setup_instructions() for help.",
        }
    if not token:
        return {
            "status": "error",
            "message": "FACEBOOK_PAGE_ACCESS_TOKEN not set in .env — run setup_instructions() for help.",
        }

    payload: dict = {
        "message": content,
        "access_token": token,
    }
    if link:
        payload["link"] = link

    is_scheduled = False
    if scheduled_unix is not None:
        now = int(time.time())
        min_time = now + 10 * 60        # 10 minutes from now
        max_time = now + 30 * 24 * 3600  # 30 days from now
        if scheduled_unix < min_time:
            return {
                "status": "error",
                "message": (
                    f"scheduled_unix ({scheduled_unix}) must be at least 10 minutes in the "
                    f"future (minimum: {min_time})."
                ),
            }
        if scheduled_unix > max_time:
            return {
                "status": "error",
                "message": (
                    f"scheduled_unix ({scheduled_unix}) must be within 30 days "
                    f"(maximum: {max_time})."
                ),
            }
        payload["scheduled_publish_time"] = scheduled_unix
        payload["published"] = "false"
        is_scheduled = True

    data = _graph("post", f"{page_id}/feed", data=payload)

    if "status" in data and data["status"] == "error":
        return data

    post_id = data.get("id", "")
    status = "scheduled" if is_scheduled else "posted"
    return {
        "status": status,
        "post_id": post_id,
        "message": (
            f"Post {'scheduled' if is_scheduled else 'published'} successfully. "
            f"ID: {post_id}"
        ),
        "raw": data,
    }


def get_page_token(user_access_token: str = None) -> str:
    """Exchange a short-lived user token for a long-lived page access token.

    The long-lived page token is effectively permanent (does not expire for
    Page tokens generated from a long-lived user token, per Meta documentation).

    Args:
        user_access_token: A short-lived user token with pages_manage_posts,
                           pages_read_engagement scopes. If omitted the function
                           looks for FACEBOOK_PAGE_ACCESS_TOKEN in env (which may
                           already be a page token).
    Returns:
        The long-lived page access token string, or an error string prefixed
        with "ERROR:".
    """
    app_id = _app_id()
    app_secret = _app_secret()
    page_id = _page_id()

    if not app_id or not app_secret:
        return "ERROR: FACEBOOK_APP_ID and FACEBOOK_APP_SECRET must be set in .env"
    if not page_id:
        return "ERROR: FACEBOOK_PAGE_ID must be set in .env"

    # Step 1 — get long-lived user token
    if not user_access_token:
        user_access_token = _page_token()
    if not user_access_token:
        return "ERROR: Provide a user_access_token or set FACEBOOK_PAGE_ACCESS_TOKEN in .env"

    ll_data = _graph("get", "oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": user_access_token,
    })
    if "status" in ll_data and ll_data["status"] == "error":
        return f"ERROR: Failed to get long-lived user token — {ll_data.get('fb_error')}"

    ll_user_token = ll_data.get("access_token")
    if not ll_user_token:
        return f"ERROR: Unexpected token exchange response: {ll_data}"

    # Step 2 — get page token from /me/accounts
    accounts = _graph("get", "me/accounts", params={
        "access_token": ll_user_token,
        "fields": "id,name,access_token",
    })
    if "status" in accounts and accounts["status"] == "error":
        return f"ERROR: Failed to fetch page accounts — {accounts.get('fb_error')}"

    pages = accounts.get("data", [])
    for page in pages:
        if str(page.get("id")) == str(page_id):
            page_token = page.get("access_token", "")
            if page_token:
                print(
                    f"\nFound long-lived page token for page {page.get('name')} ({page_id}).\n"
                    f"Add this to your .env as FACEBOOK_PAGE_ACCESS_TOKEN:\n\n{page_token}\n"
                )
                return page_token

    available = ", ".join(f"{p.get('name')} ({p.get('id')})" for p in pages)
    return (
        f"ERROR: Page ID {page_id} not found in your managed pages. "
        f"Pages available: {available or 'none'}"
    )


def get_recent_posts(limit: int = 10) -> list:
    """Fetch recent posts from the VELTM TOURS Page with engagement metrics.

    Args:
        limit: Number of posts to return (default 10, max 100).
    Returns:
        List of dicts, each with:
          id, message (truncated), created_time,
          likes, comments, shares
        On error returns a single-item list containing an error dict.
    """
    page_id = _page_id()
    token = _page_token()

    if not page_id or not token:
        return [{
            "status": "error",
            "message": "FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN must be set in .env",
        }]

    limit = max(1, min(int(limit), 100))
    data = _graph("get", f"{page_id}/feed", params={
        "access_token": token,
        "fields": "id,message,created_time,likes.summary(true),comments.summary(true),shares",
        "limit": limit,
    })

    if "status" in data and data["status"] == "error":
        return [data]

    posts = []
    for p in data.get("data", []):
        posts.append({
            "id": p.get("id"),
            "message": (p.get("message") or "")[:120],
            "created_time": p.get("created_time"),
            "likes": p.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": p.get("comments", {}).get("summary", {}).get("total_count", 0),
            "shares": p.get("shares", {}).get("count", 0),
        })
    return posts


def setup_instructions() -> str:
    """Return step-by-step instructions to obtain Facebook Graph API credentials.

    Returns:
        Multi-line string with exact steps to configure skills_facebook.py.
    """
    instructions = """
=== Facebook Graph API Setup for VELTM TOURS ===

You need four values in zoho-skills/.env:
  FACEBOOK_APP_ID
  FACEBOOK_APP_SECRET
  FACEBOOK_PAGE_ID
  FACEBOOK_PAGE_ACCESS_TOKEN

--- Step 1: Create a Facebook App ---
1. Go to https://developers.facebook.com/apps/
2. Click "Create App" → choose "Business" type.
3. Give it any name (e.g. "VELTM Butler Button").
4. Under "Add products to your app" add "Facebook Login" and "Pages API".
5. In App Settings → Basic: copy App ID and App Secret into .env.

--- Step 2: Find your Page ID ---
1. Go to your VELTM TOURS Facebook Page.
2. Click "About" (desktop) — the Page ID appears at the bottom.
   OR go to https://www.facebook.com/pg/YOUR_PAGE_SLUG/about/
   OR use: https://graph.facebook.com/YOUR_PAGE_SLUG?fields=id&access_token=APP_ID|APP_SECRET
3. Copy the numeric ID into .env as FACEBOOK_PAGE_ID.

--- Step 3: Get a User Access Token ---
1. In your app's dashboard, go to Tools → Graph API Explorer.
   URL: https://developers.facebook.com/tools/explorer/
2. Select your app from the dropdown.
3. Click "Generate Access Token".
4. Add these permissions:
     pages_manage_posts
     pages_read_engagement
     pages_show_list
5. Click "Generate Access Token" and authorise.
6. Copy the token.

--- Step 4: Exchange for a Long-Lived Page Token ---
Run this from zoho-skills/:
  python -c "from skills_facebook import get_page_token; print(get_page_token('PASTE_USER_TOKEN_HERE'))"

This will print a long-lived page token. Paste it into .env as FACEBOOK_PAGE_ACCESS_TOKEN.
The token is effectively permanent for Page tokens derived from a long-lived user token.

--- Step 5: Verify ---
  python -c "from skills_facebook import get_recent_posts; import json; print(json.dumps(get_recent_posts(3), indent=2))"

--- Notes ---
- The token needs to be refreshed every 60 days if you use a short-lived user token as source.
- To avoid re-authorisation: use a System User token from Meta Business Manager
  (Business Settings → System Users → Generate New Token → select Pages permissions).
- Never commit .env or tokens to git.
"""
    return instructions.strip()


# ── Self-test (__main__) ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=== skills_facebook.py self-test ===\n")

    # Show setup instructions if any required credential is missing
    missing = [
        v for v in ("FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET",
                    "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN")
        if not os.environ.get(v)
    ]
    if missing:
        print(f"Missing credentials: {missing}")
        print("Run setup_instructions() for help:\n")
        print(setup_instructions())
        sys.exit(0)

    # Post a clearly-labelled test message
    ts = int(time.time())
    test_content = f"Butler Button test post [{ts}] — ignore, will be deleted immediately."
    print(f"Posting test message: {test_content!r}\n")

    result = post_to_page(test_content)
    print(f"post_to_page() result:\n{json.dumps(result, indent=2)}\n")

    if result.get("status") == "posted" and result.get("post_id"):
        post_id = result["post_id"]
        print(f"Deleting test post {post_id} ...")
        del_data = _graph("delete", post_id, params={
            "access_token": _page_token(),
        })
        print(f"Delete result:\n{json.dumps(del_data, indent=2)}\n")
    else:
        print("Post did not succeed — skipping delete step.")

    print("Self-test complete.")
