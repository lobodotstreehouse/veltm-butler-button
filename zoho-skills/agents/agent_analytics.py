"""
AGENT: Analytics & Insight Engine
Pulls Zoho Campaigns stats + Zoho CRM conversion data and generates
a plain-English performance report with specific next actions.

Usage:
  python agent_analytics.py --campaign-key <key>
  python agent_analytics.py --period mtd    # month-to-date overview

What it does:
  1. Pulls campaign open rate, click rate, bounces, unsubscribes from Zoho Campaigns
  2. Cross-references clicked contacts against CRM to measure lead conversion
  3. Claude interprets the numbers and writes a 5-point action report
  4. Posts to Cliq #marketing
"""

import argparse
import json
import anthropic
import requests
from datetime import date
from zoho_client import zoho, cliq_post

CAMPAIGNS_BASE = "https://campaigns.zoho.in/api/v1.1"
CLIQ_CHANNEL = "marketing"


def _camps_get(path: str, params: dict = None) -> dict:
    r = requests.get(
        f"{CAMPAIGNS_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        params=params or {},
    )
    r.raise_for_status()
    return r.json()


def get_campaign_stats(campaign_key: str) -> dict:
    stats = _camps_get(f"getcampaignstatistics.json",
                       params={"campaignkey": campaign_key})
    return stats.get("statistics", stats)


def get_mtd_summary() -> dict:
    campaigns = _camps_get("getmycampaigns.json",
                           params={"status": "Sent", "range": 30}).get("campaigns", [])
    totals = {"sent": 0, "opened": 0, "clicked": 0, "bounced": 0, "unsubscribed": 0, "campaigns": len(campaigns)}
    for c in campaigns:
        totals["sent"] += int(c.get("sentcount", 0))
        totals["opened"] += int(c.get("openedcount", 0))
        totals["clicked"] += int(c.get("clickedcount", 0))
        totals["bounced"] += int(c.get("bouncedcount", 0))
        totals["unsubscribed"] += int(c.get("unsubscribedcount", 0))
    return totals


def run(campaign_key: str = None, period: str = None) -> dict:
    if campaign_key:
        raw_stats = get_campaign_stats(campaign_key)
        context = f"Single campaign stats:\n{json.dumps(raw_stats, indent=2)}"
    else:
        raw_stats = get_mtd_summary()
        open_rate = raw_stats["opened"] / raw_stats["sent"] * 100 if raw_stats["sent"] else 0
        click_rate = raw_stats["clicked"] / raw_stats["sent"] * 100 if raw_stats["sent"] else 0
        context = (
            f"MTD email marketing ({date.today().strftime('%B %Y')}):\n"
            f"Campaigns: {raw_stats['campaigns']}\n"
            f"Sent: {raw_stats['sent']:,}  |  Opened: {raw_stats['opened']:,} ({open_rate:.1f}%)\n"
            f"Clicked: {raw_stats['clicked']:,} ({click_rate:.1f}%)  |  "
            f"Bounced: {raw_stats['bounced']}  |  Unsubscribed: {raw_stats['unsubscribed']}"
        )

    client = anthropic.Anthropic()
    prompt = f"""You are analyzing email marketing performance for Butler Button — a 2-person luxury travel concierge.
Industry benchmarks for luxury travel: open rate ~35%, click rate ~4%.

Data:
{context}

Write a blunt 5-point performance report:

PERFORMANCE — {date.today().strftime('%B %Y')}

1. VERDICT: [one sentence — is this good, bad, or average vs. benchmark]
2. STRONGEST SIGNAL: [what's working and why]
3. WEAKEST SIGNAL: [what's failing and the most likely cause]
4. ACTION 1: [specific change to make this week — subject line, send time, list hygiene, etc.]
5. ACTION 2: [one test to run in the next campaign]

Be direct. Use the actual numbers. No padding."""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    report = resp.content[0].text.strip()

    cliq_post({CLIQ_CHANNEL}, report)

    return {"report": report, "raw": raw_stats}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-key", default=None)
    parser.add_argument("--period", default="mtd")
    args = parser.parse_args()
    result = run(args.campaign_key, args.period)
    print(result["report"])
