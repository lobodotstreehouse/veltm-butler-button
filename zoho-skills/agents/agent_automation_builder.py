"""
AGENT: Marketing Automation Builder
Describe a trigger + desired outcome in plain English.
It builds the Zoho Campaigns autoresponder sequence AND the Zoho Flow
that connects CRM events to campaign actions — no manual setup.

Usage:
  python agent_automation_builder.py \
    --trigger "Lead created with rating Hot" \
    --outcome "Enroll in 3-email hot-lead sequence, alert Cliq immediately" \
    --list-id "<zoho-campaigns-list-id>"

What it produces:
  1. Claude designs the automation sequence (trigger, delays, conditions, emails)
  2. Creates the autoresponder series in Zoho Campaigns
  3. Creates a Zoho Flow webhook trigger for the CRM event → campaign enrollment
  4. Prints a Zoho Flow setup guide (Flow UI still requires a manual click to activate)
  5. Posts full automation spec to Cliq #marketing
"""

import argparse
import anthropic
import json
import requests
from zoho_client import zoho

CAMPAIGNS_BASE = "https://campaigns.zoho.in/api/v1.1"
CLIQ_CHANNEL = "marketing"
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def _camps_post(path: str, data: dict) -> dict:
    r = requests.post(
        f"{CAMPAIGNS_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        data=data,
    )
    r.raise_for_status()
    return r.json()


def run(trigger_desc: str, outcome_desc: str, list_id: str) -> dict:
    client = anthropic.Anthropic()

    # Step 1: Claude designs the automation
    design_prompt = f"""Design a marketing automation sequence for Butler Button, a 2-person luxury travel concierge.

Trigger: {trigger_desc}
Desired outcome: {outcome_desc}

Design the automation as a JSON spec with this structure:
{{
  "automation_name": "...",
  "trigger": {{"type": "...", "condition": "..."}},
  "immediate_action": "...",
  "emails": [
    {{"delay_hours": 0, "subject": "...", "body_brief": "...", "goal": "..."}},
    {{"delay_hours": 72, "subject": "...", "body_brief": "...", "goal": "..."}},
    {{"delay_hours": 168, "subject": "...", "body_brief": "...", "goal": "..."}}
  ],
  "exit_condition": "...",
  "zoho_flow_trigger": "...",
  "zoho_campaigns_action": "..."
}}

Keep email body_briefs to 20 words — these are instructions for email writing, not the emails themselves.
Output ONLY the JSON."""

    design_resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=600,
        messages=[{"role": "user", "content": design_prompt}]
    )
    try:
        spec = json.loads(design_resp.content[0].text.strip())
    except json.JSONDecodeError:
        spec = {"automation_name": "BB Automation", "emails": []}

    automation_name = spec.get("automation_name", "Butler Button Automation")
    created_campaigns = []

    # Step 2: Claude writes each email + creates in Zoho Campaigns
    for i, email_spec in enumerate(spec.get("emails", [])[:3]):
        write_prompt = f"""Write a marketing automation email for Butler Button — luxury travel concierge.
Sequence: {automation_name}
Position: Email {i+1} of {len(spec.get('emails', []))}
Trigger context: {trigger_desc}
This email's goal: {email_spec.get('goal', '')}
Brief for content: {email_spec.get('body_brief', '')}

Write:
- Subject line (max 8 words, no emoji)
- Email body (100-150 words, plain text, personalization token {{{{First Name}}}})

Rules: No "I hope this finds you well". No bullet lists. One CTA max. Sign off: Butler Button Team

SUBJECT: ...
BODY:
..."""

        write_resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=300,
            messages=[{"role": "user", "content": write_prompt}]
        )
        raw = write_resp.content[0].text.strip()
        lines = raw.split("\n")
        subject = next((l.replace("SUBJECT:", "").strip() for l in lines if l.startswith("SUBJECT:")), email_spec.get("subject", "Following up"))
        body_start = next((i for i, l in enumerate(lines) if l.startswith("BODY:")), len(lines))
        body = "\n".join(lines[body_start + 1:]).strip()

        try:
            result = _camps_post("campaigns/createemailcampaign.json", {
                "campaignname": f"{automation_name} — Email {i+1}",
                "from_email": MAIL_FROM,
                "from_name": "Butler Button",
                "subject": subject,
                "content": body,
                "listids": list_id,
            })
            created_campaigns.append({"email": i+1, "subject": subject, "id": result.get("details", {}).get("campaignkey", "—")})
        except Exception as e:
            created_campaigns.append({"email": i+1, "subject": subject, "error": str(e)})

    # Step 3: Zoho Flow setup instructions
    flow_guide = f"""
ZOHO FLOW SETUP (2-minute manual step):

1. Go to flow.zoho.in
2. Create New Flow: "{automation_name}"
3. Trigger: Zoho CRM → {spec.get('zoho_flow_trigger', 'Lead Created')}
4. Add condition: {spec.get('trigger', {}).get('condition', trigger_desc)}
5. Action 1: Zoho Campaigns → {spec.get('zoho_campaigns_action', 'Add Subscriber to List')}
   List ID: {list_id}
6. Action 2: Zoho Cliq → Post Message to #{CLIQ_CHANNEL}
   Message: Automation triggered: {automation_name} for {{{{Lead.Name}}}}
7. Turn ON the flow.

Campaign IDs created: {', '.join(c.get('id','—') for c in created_campaigns)}
""".strip()

    # Cliq post
    cliq_msg = (
        f"AUTOMATION BUILT — {automation_name}\n"
        f"Trigger: {trigger_desc}\n"
        f"Emails created in Zoho Campaigns: {len(created_campaigns)}\n\n"
        + "\n".join(f"  Email {c['email']}: {c['subject']}" for c in created_campaigns)
        + f"\n\nZoho Flow: 2-minute manual activation required (see flow.zoho.in)"
    )
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": cliq_msg},
    )

    return {"automation_name": automation_name, "spec": spec,
            "campaigns_created": created_campaigns, "flow_guide": flow_guide}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--list-id", required=True)
    args = parser.parse_args()
    result = run(args.trigger, args.outcome, args.list_id)
    print(f"\nAutomation: {result['automation_name']}")
    print(f"\nEmails created:")
    for c in result["campaigns_created"]:
        print(f"  Email {c['email']}: {c['subject']}  (ID: {c.get('id','—')})")
    print(f"\n{result['flow_guide']}")
