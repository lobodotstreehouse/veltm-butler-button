"""
Butler Button — Instagram Graph API Skill
------------------------------------------
Direct posting to @veltmtours (Instagram Business account) via the
Facebook/Instagram Graph API v19.0.  No third-party middleware required —
only the facebook-python-business-sdk is NOT used here; plain requests only.

The @veltmtours account is an Instagram Business account connected to the
VELTM TOURS Facebook Page.  All calls share the same long-lived Page Access
Token used by skills_facebook.py.

ENV VARS (add to zoho-skills/.env):
  FACEBOOK_APP_ID              — shared with skills_facebook.py
  FACEBOOK_APP_SECRET          — shared with skills_facebook.py
  INSTAGRAM_PAGE_ACCESS_TOKEN  — long-lived Page Token with scopes:
                                   instagram_basic
                                   instagram_content_publish
                                   pages_read_engagement
  INSTAGRAM_USER_ID            — numeric IG Business account ID (NOT @username)
                                   Find it: GET /me/accounts then
                                   GET /{page-id}?fields=instagram_business_account

Skills:
  post_image           — Publish a feed photo (two-step container + publish)
  post_reel            — Publish a Reel/video (two-step, media_type=REELS)
  post_caption_only    — No image URL available? Save caption as CRM Task "Ready to post"
  get_account_insights — Reach, impressions, follower_count for the account
  get_recent_media     — Recent posts with engagement metrics
  setup_instructions   — Human-readable setup guide (returns string)
"""

import os
from datetime import date
from typing import Optional
import requests
from zoho_client import zoho

# ── Credentials (loaded by zoho_client.load_dotenv at import time) ─────────────
_APP_ID     = os.environ.get("FACEBOOK_APP_ID", "")
_APP_SECRET = os.environ.get("FACEBOOK_APP_SECRET", "")
_TOKEN      = os.environ.get("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
_IG_USER_ID = os.environ.get("INSTAGRAM_USER_ID", "")

GRAPH_BASE  = "https://graph.facebook.com/v19.0"

# ── Internal helpers ───────────────────────────────────────────────────────────

def _check_config() -> Optional[str]:
    """Return an error string if required env vars are missing, else None."""
    missing = [k for k, v in {
        "INSTAGRAM_PAGE_ACCESS_TOKEN": _TOKEN,
        "INSTAGRAM_USER_ID": _IG_USER_ID,
    }.items() if not v]
    if missing:
        return (
            f"Missing env vars: {', '.join(missing)}. "
            "Run setup_instructions() for the setup guide."
        )
    return None


def _graph_post(path: str, payload: dict) -> dict:
    """POST to the Graph API; raises on HTTP error; returns parsed JSON."""
    url = f"{GRAPH_BASE}/{path}"
    r = requests.post(url, json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if not r.ok:
        error_msg = data.get("error", {}).get("message", r.text) if isinstance(data, dict) else r.text
        return {"status": "error", "http": r.status_code, "message": error_msg}
    return data


def _graph_get(path: str, params: dict = None) -> dict:
    """GET from the Graph API; returns parsed JSON."""
    url = f"{GRAPH_BASE}/{path}"
    p = {"access_token": _TOKEN, **(params or {})}
    r = requests.get(url, params=p, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if not r.ok:
        error_msg = data.get("error", {}).get("message", r.text) if isinstance(data, dict) else r.text
        return {"status": "error", "http": r.status_code, "message": error_msg}
    return data


# ── Public skills ──────────────────────────────────────────────────────────────

def post_image(image_url: str, caption: str) -> dict:
    """Post a feed image to @veltmtours via the two-step Graph API container flow.

    Instagram requires the image to be at a publicly accessible HTTPS URL.
    If you do not have a public URL, call post_caption_only() instead.

    Step 1: Create a media container  → returns creation_id
    Step 2: Publish the container     → returns post_id

    Args:
        image_url: Publicly accessible HTTPS URL of the image (JPEG or PNG)
        caption:   Post caption including hashtags

    Returns:
        dict with 'status' ("posted" | "error"), 'post_id', and debug fields
    """
    err = _check_config()
    if err:
        return {"status": "error", "message": err}

    if not image_url or not image_url.startswith("http"):
        return post_caption_only(caption)

    # Step 1 — create container
    container = _graph_post(f"{_IG_USER_ID}/media", {
        "image_url": image_url,
        "caption": caption,
        "access_token": _TOKEN,
    })
    if container.get("status") == "error":
        return {**container, "step": "create_container"}

    creation_id = container.get("id")
    if not creation_id:
        return {"status": "error", "step": "create_container",
                "message": "No creation_id returned", "response": container}

    # Step 2 — publish container
    publish = _graph_post(f"{_IG_USER_ID}/media_publish", {
        "creation_id": creation_id,
        "access_token": _TOKEN,
    })
    if publish.get("status") == "error":
        return {**publish, "step": "media_publish", "creation_id": creation_id}

    post_id = publish.get("id", "")
    return {
        "status": "posted",
        "post_id": post_id,
        "creation_id": creation_id,
        "platform": "instagram",
        "account": "@veltmtours",
        "url": f"https://www.instagram.com/p/{post_id}/" if post_id else None,
    }


def post_reel(video_url: str, caption: str) -> dict:
    """Post a Reel (video) to @veltmtours via the two-step Graph API container flow.

    The video must be at a publicly accessible HTTPS URL.  Instagram processes
    Reels asynchronously — the publish step may return immediately but the
    video will continue encoding on Instagram's servers.

    Supported formats: MP4 (H.264 video, AAC audio). Min 3s, max 15min,
    min resolution 500x888px (9:16 aspect ratio recommended).

    Args:
        video_url: Publicly accessible HTTPS URL of the video file
        caption:   Reel caption including hashtags

    Returns:
        dict with 'status' ("posted" | "error"), 'post_id', and debug fields
    """
    err = _check_config()
    if err:
        return {"status": "error", "message": err}

    if not video_url or not video_url.startswith("http"):
        return {"status": "error",
                "message": "video_url must be a public HTTPS URL. Reels cannot fall back to caption-only."}

    # Step 1 — create container (REELS type)
    container = _graph_post(f"{_IG_USER_ID}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": _TOKEN,
    })
    if container.get("status") == "error":
        return {**container, "step": "create_container"}

    creation_id = container.get("id")
    if not creation_id:
        return {"status": "error", "step": "create_container",
                "message": "No creation_id returned", "response": container}

    # Step 2 — publish container
    publish = _graph_post(f"{_IG_USER_ID}/media_publish", {
        "creation_id": creation_id,
        "access_token": _TOKEN,
    })
    if publish.get("status") == "error":
        return {**publish, "step": "media_publish", "creation_id": creation_id}

    post_id = publish.get("id", "")
    return {
        "status": "posted",
        "post_id": post_id,
        "creation_id": creation_id,
        "media_type": "REELS",
        "platform": "instagram",
        "account": "@veltmtours",
        "note": "Video encoding continues async on Instagram's servers.",
    }


def post_caption_only(caption: str) -> dict:
    """Save an Instagram caption as a CRM Task when no image URL is available.

    Creates a Zoho CRM Task with status "Ready to post" so the caption can be
    copy-pasted when the image is uploaded manually via the Instagram app.

    Args:
        caption: The full post caption (with hashtags) to save

    Returns:
        dict with 'status' ("saved" | "error"), 'task_subject', and CRM response
    """
    subject = f"[Instagram] Ready to post — {date.today().isoformat()}"
    description = (
        f"Caption ready to copy-paste into Instagram:\n\n"
        f"{caption}\n\n"
        f"--- Steps ---\n"
        f"1. Open Instagram app on mobile\n"
        f"2. Tap + to create a new post\n"
        f"3. Select your image\n"
        f"4. Paste the caption above\n"
        f"5. Tap Share"
    )
    try:
        resp = zoho.crm_post("Tasks", {"data": [{
            "Subject": subject,
            "Due_Date": date.today().isoformat(),
            "Status": "Ready to post",
            "Priority": "High",
            "Description": description,
        }]})
        task_id = resp.get("data", [{}])[0].get("details", {}).get("id", "")
        return {
            "status": "saved",
            "platform": "instagram",
            "fallback": "caption_only",
            "task_subject": subject,
            "task_id": task_id,
            "note": "Caption saved as CRM Task. Upload your image via the Instagram app and paste the caption.",
            "caption_preview": caption[:120] + ("..." if len(caption) > 120 else ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "caption": caption}


def get_account_insights(period: str = "day") -> dict:
    """Fetch reach, impressions, and follower_count for @veltmtours.

    Args:
        period: "day" | "week" | "days_28" | "month" | "lifetime"
                (Instagram Graph API period values)

    Returns:
        dict with insight metrics keyed by metric name, plus raw API response
    """
    err = _check_config()
    if err:
        return {"status": "error", "message": err}

    metrics = "reach,impressions,follower_count"
    data = _graph_get(f"{_IG_USER_ID}/insights", {
        "metric": metrics,
        "period": period,
    })
    if data.get("status") == "error":
        return data

    parsed = {"period": period, "account": "@veltmtours", "metrics": {}}
    for item in data.get("data", []):
        name = item.get("name", "")
        values = item.get("values", [])
        latest = values[-1].get("value") if values else None
        parsed["metrics"][name] = latest
    parsed["raw"] = data
    return parsed


def get_recent_media(limit: int = 10) -> list:
    """Return recent @veltmtours posts with engagement metrics.

    Args:
        limit: Number of recent posts to return (default 10, max 100)

    Returns:
        list of dicts, each with: id, caption (truncated), like_count,
        comments_count, timestamp, media_type, permalink
    """
    err = _check_config()
    if err:
        return [{"status": "error", "message": err}]

    limit = max(1, min(limit, 100))
    data = _graph_get(f"{_IG_USER_ID}/media", {
        "fields": "id,caption,like_count,comments_count,timestamp,media_type,permalink",
        "limit": limit,
    })
    if data.get("status") == "error":
        return [data]

    posts = []
    for item in data.get("data", []):
        caption_raw = item.get("caption", "") or ""
        posts.append({
            "id": item.get("id"),
            "caption": caption_raw[:100] + ("..." if len(caption_raw) > 100 else ""),
            "like_count": item.get("like_count", 0),
            "comments_count": item.get("comments_count", 0),
            "timestamp": item.get("timestamp"),
            "media_type": item.get("media_type"),
            "permalink": item.get("permalink"),
        })
    return posts


def setup_instructions() -> str:
    """Return step-by-step instructions for connecting @veltmtours to this skill.

    Returns:
        Multi-line string with exact setup steps.
    """
    return """
Instagram Graph API Setup — @veltmtours
========================================

PREREQUISITES
  - @veltmtours must be an Instagram BUSINESS or CREATOR account (not personal)
  - It must be connected to the VELTM TOURS Facebook Page
    (Instagram Settings → Account → Switch to Professional Account → connect Page)

STEP 1 — Create / reuse a Facebook App
  1. Go to https://developers.facebook.com/apps/
  2. If you already have an app for skills_facebook.py, use that same App ID.
     Otherwise: Create App → Business → give it a name → Create.
  3. Note: FACEBOOK_APP_ID and FACEBOOK_APP_SECRET (App Settings → Basic)

STEP 2 — Add Instagram Graph API product
  1. In your app dashboard → Add Product → Instagram Graph API → Set Up
  2. No extra config needed here; permissions are granted via the token.

STEP 3 — Generate a long-lived Page Access Token with Instagram scopes
  1. Go to https://developers.facebook.com/tools/explorer/
  2. Select your App in the top-right dropdown
  3. Click "Generate Access Token"
  4. Grant these permissions:
       - instagram_basic
       - instagram_content_publish
       - pages_read_engagement
       - pages_manage_posts  (needed if sharing the token with skills_facebook.py)
  5. Click "Generate Token" — this is a short-lived User Token.
  6. Exchange it for a long-lived token (valid ~60 days):
       GET https://graph.facebook.com/v19.0/oauth/access_token
           ?grant_type=fb_exchange_token
           &client_id={FACEBOOK_APP_ID}
           &client_secret={FACEBOOK_APP_SECRET}
           &fb_exchange_token={SHORT_LIVED_TOKEN}
  7. From the long-lived User Token, get a never-expiring Page Token:
       GET https://graph.facebook.com/v19.0/me/accounts
           ?access_token={LONG_LIVED_USER_TOKEN}
     Find the VELTM TOURS page entry — copy its "access_token" value.
     That is your INSTAGRAM_PAGE_ACCESS_TOKEN.

STEP 4 — Find the Instagram Business Account numeric ID
  1. Using the Page Token from Step 3:
       GET https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}
           ?fields=instagram_business_account
           &access_token={INSTAGRAM_PAGE_ACCESS_TOKEN}
  2. The response contains: {"instagram_business_account": {"id": "XXXXXXXXXXXXXXX"}}
  3. That number is your INSTAGRAM_USER_ID.

STEP 5 — Add to zoho-skills/.env
  FACEBOOK_APP_ID=<from Step 1>
  FACEBOOK_APP_SECRET=<from Step 1>
  INSTAGRAM_PAGE_ACCESS_TOKEN=<Page Token from Step 3>
  INSTAGRAM_USER_ID=<numeric ID from Step 4>

STEP 6 — Verify
  Run: python skills_instagram.py
  Expected output: "Setup OK" + recent media list (or "no posts yet")

IMPORTANT NOTES
  - INSTAGRAM_PAGE_ACCESS_TOKEN is the same Page Token used by skills_facebook.py.
    You can share a single FACEBOOK_PAGE_ACCESS_TOKEN value across both skills
    by also setting INSTAGRAM_PAGE_ACCESS_TOKEN to the same value.
  - The Graph API requires a PUBLICLY accessible image/video URL for posting.
    Images hosted on localhost or behind auth will fail.
    Use a CDN, S3 presigned URL, or Cloudinary public URL.
  - Token renewal: Page Tokens obtained this way do not expire as long as the
    user's password and 2FA settings remain unchanged. Rotate if you see
    "Error validating access token" responses.
  - App Review: For posting to a LIVE account (not in dev mode), the app needs
    to pass Instagram's App Review for instagram_content_publish.
    During development, add @veltmtours as a test user in the app dashboard.
""".strip()


# ── Self-test / setup verification ────────────────────────────────────────────

if __name__ == "__main__":
    print("skills_instagram.py — import and syntax check OK\n")
    print(setup_instructions())
    print("\n--- Config check ---")
    err = _check_config()
    if err:
        print(f"NOT CONFIGURED: {err}")
        print("Add INSTAGRAM_PAGE_ACCESS_TOKEN and INSTAGRAM_USER_ID to .env and re-run.")
    else:
        print(f"App ID:    {_APP_ID or '(not set)'}")
        print(f"IG User:   {_IG_USER_ID}")
        print(f"Token set: {'yes (' + _TOKEN[:8] + '...)' if _TOKEN else 'NO'}")
        print("\nFetching recent media (limit=3)...")
        media = get_recent_media(limit=3)
        if media and isinstance(media[0], dict) and media[0].get("status") == "error":
            print(f"Error: {media[0].get('message')}")
        else:
            for m in media:
                print(f"  [{m.get('media_type')}] {m.get('timestamp')} "
                      f"— likes:{m.get('like_count')} comments:{m.get('comments_count')}")
            print("Setup OK")
