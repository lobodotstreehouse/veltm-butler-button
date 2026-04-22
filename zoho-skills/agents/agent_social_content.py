"""
AGENT: Social Content Engine
Input: topic, platforms, optional schedule flag.
Output: platform-native posts dispatched to Zoho Social via Flow webhook,
        or printed to terminal as drafts.

NOTE: Zoho Social has no public REST API.
      Posting routes through a Zoho Flow webhook (one-time setup).
      Content generation runs directly via Claude.

Usage:
  # Generate + dispatch to Zoho Social via Flow:
  python agent_social_content.py \\
    --topic "Why most luxury travel agencies are just booking agents" \\
    --platforms instagram linkedin x \\
    --schedule

  # Copy only (no dispatch):
  python agent_social_content.py --topic "Maldives honeymoon season" --copy-only

  # Full campaign burst:
  python agent_social_content.py \\
    --campaign "Monsoon Maldives" \\
    --offer "5-night overwater villa, all-inclusive" \\
    --launch 2026-05-15

  # 4-week content calendar:
  python agent_social_content.py --calendar "honeymoon season" --weeks 4
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from skills_social import (
    generate_multi_platform,
    generate_post,
    schedule_post_via_flow,
    generate_campaign_burst,
    create_content_calendar,
    get_calendar_week,
)
from datetime import datetime, timedelta


def run_posts(topic: str, platforms: list, schedule: bool = False, copy_only: bool = False) -> dict:
    results = generate_multi_platform(topic, platforms)

    if not copy_only and schedule:
        next_time = datetime.now() + timedelta(hours=2)
        for p, data in results.items():
            content = data.get("content", "")
            if content:
                dispatch = schedule_post_via_flow(
                    p, content, next_time.strftime("%Y-%m-%dT%H:%M:%S")
                )
                data["dispatch"] = dispatch
                next_time += timedelta(hours=4)

    return results


def main():
    parser = argparse.ArgumentParser(description="Butler Button Social Content Engine")
    parser.add_argument("--topic", help="Post topic / angle")
    parser.add_argument("--platforms", nargs="+", default=["instagram", "linkedin", "x"])
    parser.add_argument("--schedule", action="store_true", help="Dispatch to Zoho Social via Flow")
    parser.add_argument("--copy-only", action="store_true", help="Print copy only, no dispatch")

    # Campaign mode
    parser.add_argument("--campaign", help="Campaign name for 5-phase burst")
    parser.add_argument("--offer", help="What is being promoted")
    parser.add_argument("--launch", help="Launch date ISO (YYYY-MM-DD)")

    # Calendar mode
    parser.add_argument("--calendar", help="Content calendar theme")
    parser.add_argument("--weeks", type=int, default=4)
    parser.add_argument("--show-week", action="store_true", help="Show this week's calendar")

    args = parser.parse_args()

    if args.show_week:
        week = get_calendar_week()
        print(f"\nCalendar: {week['week']} ({week['count']} posts)")
        for p in week["posts"]:
            print(f"  {p['date']}  {p['subject'][:60]}  [{p['status']}]")
        return

    if args.calendar:
        result = create_content_calendar(args.calendar, num_weeks=args.weeks)
        print(f"\nCalendar created: {result['num_posts']} posts, {result['tasks_created']} CRM tasks")
        for entry in result.get("calendar", [])[:10]:
            print(f"  {entry['date']}  {entry['platform'].upper():<12} {entry['topic'][:50]}")
        if result['num_posts'] > 10:
            print(f"  ... and {result['num_posts'] - 10} more in CRM Tasks")
        return

    if args.campaign:
        if not args.offer or not args.launch:
            print("Campaign mode requires --offer and --launch")
            sys.exit(1)
        result = generate_campaign_burst(args.campaign, args.offer, args.launch, args.platforms)
        print(f"\nCampaign: {result['campaign']}")
        print(f"Launch: {result['launch_date']} | {result['tasks_created']} posts in CRM\n")
        for post in result["posts"]:
            print(f"  [{post['date']}] {post['platform'].upper()} — {post['phase']}")
            print(f"  {post['content'][:160]}...\n")
        return

    if not args.topic:
        parser.print_help()
        sys.exit(1)

    results = run_posts(args.topic, args.platforms, args.schedule, args.copy_only)

    for platform, data in results.items():
        print(f"\n{'='*60}")
        print(f"  {platform.upper()}")
        print(f"{'='*60}")
        print(data.get("content", data.get("error", "—")))
        if data.get("dispatch", {}).get("status") == "dispatched":
            print(f"\n  [Dispatched to Zoho Social via Flow]")
        elif data.get("dispatch", {}).get("status") == "no_webhook":
            print(f"\n  [Set ZOHO_SOCIAL_FLOW_WEBHOOK in .env to auto-post]")


if __name__ == "__main__":
    main()
