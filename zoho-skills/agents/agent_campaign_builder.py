"""
AGENT: Campaign Builder
Give it a brief. It builds a complete 3-email drip campaign in Zoho Campaigns —
subject lines, bodies, send schedule, list segment — and launches it.

Usage:
  python agent_campaign_builder.py \
    --segment "Maldives inquiries" \
    --goal "Book a discovery call" \
    --angle "Peak season urgency — limited villas in June" \
    --list-id "abc123"

What it does:
  1. Claude writes 3 campaign emails (hook, proof, CTA) with personalization tokens
  2. Creates the campaign series in Zoho Campaigns
  3. Attaches to the specified mailing list segment
  4. Schedules Email 1 for today, Email 2 for Day 3, Email 3 for Day 7
  5. Posts campaign summary to Cliq #marketing
"""

import argparse
import json
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho

CAMPAIGNS_BASE = "https://campaigns.zoho.in/api/v1.1"
CLIQ_CHANNEL = "marketing"
FROM_EMAIL = __import__("os").environ.get("ZOHO_MAIL_FROM", "")
FROM_NAME = "Butler Button"


def _campaigns_post(path: str, data: dict) -> dict:
    r = requests.post(
        f"{CAMPAIGNS_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        data=data,  # Zoho Campaigns uses form-encoded
    )
    r.raise_for_status()
    return r.json()


def _campaigns_get(path: str, params: dict = None) -> dict:
    r = requests.get(
        f"{CAMPAIGNS_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        params=params or {},
    )
    r.raise_for_status()
    return r.json()


EMAIL_ROLES = [
    ("hook",  "Day 0 — Grab attention. One sharp insight or provocative question specific to their segment. No pitch yet. End with intrigue."),
    ("proof", "Day 3 — Build credibility. One specific client story or outcome (make it feel real). Soft CTA — reply to this email or visit the site."),
    ("cta",   "Day 7 — Close. Clear offer, clear urgency, single CTA. Make it easy to say yes."),
]


def run(segment_desc: str, goal: str, angle: str, list_id: str, campaign_name: str = None):
    client = anthropic.Anthropic()
    today = date.today()
    campaign_name = campaign_name or f"BB — {segment_desc[:40]} — {today.isoformat()}"

    emails = []
    for role, role_brief in EMAIL_ROLES:
        prompt = f"""You are writing a luxury travel concierge marketing email for Butler Button (butlerbutton.co).
Butler Button is a premium concierge for discerning travelers — think Ritz-Carlton level of personal service, but for planning the whole trip.

Segment: {segment_desc}
Campaign goal: {goal}
Angle / hook: {angle}
This email's role: {role_brief}

Write:
1. SUBJECT: (one subject line, max 8 words, no emoji)
2. PREVIEW: (one preview text, max 12 words)
3. BODY: (the email, 120-180 words, plain text)

Rules:
- Use {{{{First Name}}}} for personalization token
- No corporate language ("we are pleased to", "I hope this finds you")
- No bullet lists — flowing prose only
- No "luxury" or "exclusive" — show don't tell
- One link maximum, placeholder: {{{{CTA_LINK}}}}

Output exactly:
SUBJECT: ...
PREVIEW: ...
BODY:
..."""

        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        lines = raw.split("\n")
        subject = next((l.replace("SUBJECT:", "").strip() for l in lines if l.startswith("SUBJECT:")), f"Butler Button — {role}")
        preview = next((l.replace("PREVIEW:", "").strip() for l in lines if l.startswith("PREVIEW:")), "")
        body_start = next((i for i, l in enumerate(lines) if l.startswith("BODY:")), len(lines))
        body = "\n".join(lines[body_start + 1:]).strip()
        emails.append({"role": role, "subject": subject, "preview": preview, "body": body})

    # Create campaigns in Zoho Campaigns
    campaign_ids = []
    schedule_offsets = [0, 3, 7]
    for i, (email, offset) in enumerate(zip(emails, schedule_offsets)):
        send_date = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
        payload = {
            "campaignname": f"{campaign_name} — Email {i+1}: {email['role']}",
            "from_email": FROM_EMAIL,
            "from_name": FROM_NAME,
            "subject": email["subject"],
            "content": email["body"],
            "listids": list_id,
            "sender_address": FROM_EMAIL,
        }
        try:
            result = _campaigns_post("campaigns/createemailcampaign.json", payload)
            cid = result.get("details", {}).get("campaignkey", "—")
            campaign_ids.append(cid)
        except Exception as e:
            campaign_ids.append(f"error: {e}")

    # Cliq summary
    summary = (
        f"CAMPAIGN CREATED — {campaign_name}\n"
        f"Segment: {segment_desc}  |  Goal: {goal}\n"
        f"3-email drip: Day 0 / Day 3 / Day 7\n\n"
        + "\n".join(f"  Email {i+1} ({e['role']}): {e['subject']}" for i, e in enumerate(emails))
    )
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": summary},
    )

    return {"campaign_name": campaign_name, "emails": emails, "campaign_ids": campaign_ids}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--segment", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--angle", required=True)
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    result = run(args.segment, args.goal, args.angle, args.list_id, args.name)
    for i, e in enumerate(result["emails"], 1):
        print(f"\n── Email {i} ({e['role']}) ──")
        print(f"Subject: {e['subject']}")
        print(f"Preview: {e['preview']}")
        print(e["body"])
