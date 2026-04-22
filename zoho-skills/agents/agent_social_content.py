"""
AGENT: Social Content Engine
Input: a topic or angle.
Output: platform-optimized posts for Instagram, LinkedIn, and X — scheduled
in Zoho Social or saved as drafts.

Usage:
  python agent_social_content.py \
    --topic "Why most luxury travel agencies are actually just booking agents" \
    --platforms instagram linkedin x \
    --schedule    # auto-schedule at next best time, or omit for drafts

What it does:
  1. Claude generates native posts for each platform (different voice per platform)
  2. Creates posts in Zoho Social (scheduled or draft)
  3. Outputs all copy to terminal for review
"""

import argparse
import json
import anthropic
import requests
from datetime import datetime, timedelta
from zoho_client import zoho

SOCIAL_BASE = "https://social.zoho.in/api/v1"
CLIQ_CHANNEL = "marketing"

PLATFORM_BRIEFS = {
    "instagram": "Instagram (visual-first, emotion-led, 150-220 words, 3-5 hashtags, NO links in caption). Tone: aspirational, intimate, like a friend's travel diary.",
    "linkedin":  "LinkedIn (professional credibility, 120-180 words, one insight + one CTA, minimal hashtags). Tone: thought-leadership, CSMO voice — you've seen what separates great travel from great concierge.",
    "x":         "X/Twitter (punchy, max 240 chars, no hashtags, one provocation or contrarian take). Tone: sharp, confident, slightly irreverent.",
}


def _social_post(portal_id: str, network_ids: list, content: str, scheduled_time: str = None) -> dict:
    payload = {
        "portalId": portal_id,
        "networkIds": json.dumps(network_ids),
        "content": content,
    }
    if scheduled_time:
        payload["scheduledTime"] = scheduled_time
        payload["status"] = "scheduled"
    else:
        payload["status"] = "draft"
    r = requests.post(
        f"{SOCIAL_BASE}/posts",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json=payload,
    )
    r.raise_for_status()
    return r.json()


def _get_portal_and_networks() -> tuple[str, dict]:
    r = requests.get(
        f"{SOCIAL_BASE}/portals",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
    )
    r.raise_for_status()
    portals = r.json().get("portals", [])
    if not portals:
        raise RuntimeError("No Zoho Social portals found. Connect social accounts in Zoho Social first.")
    portal = portals[0]
    portal_id = str(portal["id"])
    networks = {n["type"].lower(): n["id"] for n in portal.get("networks", [])}
    return portal_id, networks


def run(topic: str, platforms: list[str], schedule: bool = False) -> dict:
    client = anthropic.Anthropic()
    results = {}

    try:
        portal_id, networks = _get_portal_and_networks()
        zoho_social_available = True
    except Exception:
        zoho_social_available = False
        portal_id, networks = "", {}

    next_post_time = datetime.now() + timedelta(hours=2)

    for platform in platforms:
        brief = PLATFORM_BRIEFS.get(platform.lower())
        if not brief:
            results[platform] = {"error": f"Unknown platform: {platform}"}
            continue

        prompt = f"""You are the voice of Butler Button — a premium luxury travel concierge for India's discerning travelers.
Write a social media post for {brief}

Topic / angle: {topic}

Butler Button's POV:
- We handle the entire trip, not just the hotel booking
- Our clients are successful professionals who value their time more than their money
- We have access to things that aren't on booking.com
- We are NOT a travel agency — we are a concierge

Write ONE post. No preamble. Output ONLY the post copy."""

        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        content = resp.content[0].text.strip()
        results[platform] = {"content": content, "posted": False}

        # Post to Zoho Social
        if zoho_social_available:
            platform_key = {"instagram": "ig", "linkedin": "ln", "x": "tw"}.get(platform.lower(), platform.lower())
            network_id = networks.get(platform_key) or networks.get(platform.lower())
            if network_id:
                scheduled_time = next_post_time.strftime("%Y-%m-%dT%H:%M:%S") if schedule else None
                try:
                    _social_post(portal_id, [network_id], content, scheduled_time)
                    results[platform]["posted"] = True
                    results[platform]["scheduled_for"] = scheduled_time
                    next_post_time += timedelta(hours=4)  # space out posts
                except Exception as e:
                    results[platform]["error"] = str(e)

    # Cliq summary
    cliq_msg = f"SOCIAL CONTENT — {topic[:60]}\n\n"
    for p, r in results.items():
        status = "scheduled" if r.get("scheduled_for") else ("draft" if r.get("posted") else "copy only")
        cliq_msg += f"{p.upper()} [{status}]:\n{r.get('content','—')[:200]}\n\n"
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": cliq_msg},
    )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--platforms", nargs="+", default=["instagram", "linkedin", "x"])
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()
    results = run(args.topic, args.platforms, args.schedule)
    for platform, data in results.items():
        print(f"\n{'='*60}")
        print(f"  {platform.upper()}")
        print(f"{'='*60}")
        print(data.get("content", data.get("error", "—")))
        if data.get("scheduled_for"):
            print(f"\n  [Scheduled: {data['scheduled_for']}]")
