"""
AGENT: Personalization Engine
Pulls a segment from Zoho CRM and generates individually personalized
email variants for each contact. No merge tags — Claude writes a unique
version for each person based on their actual CRM data.

Usage:
  python agent_personalization.py \
    --segment "VIP" \
    --campaign-goal "Re-engage for summer 2026 season" \
    --send            # or omit for drafts only

What it does:
  1. Pulls contacts matching segment tag from Zoho CRM
  2. For each contact, fetches their history (past bookings, preferences, last contact)
  3. Claude writes a UNIQUE email referencing their specific history
  4. Saves as Zoho Mail draft OR sends (if --send flag)
  5. Logs activity in CRM for each contact
  6. Cliq summary with send count
"""

import argparse
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho, cliq_post, MAIL_BASE

CLIQ_CHANNEL = "marketing"
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def _get_acct_id() -> str:
    r = requests.get(f"{MAIL_BASE}/accounts",
                     headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"})
    return str(r.json()["data"][0]["accountId"])


def _get_contact_context(contact: dict) -> str:
    contact_id = contact["id"]
    name = contact.get("Full_Name") or f"{contact.get('First_Name','')} {contact.get('Last_Name','')}".strip()

    history = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Closing_Date,BB_Destination,BB_Service_Type,Amount",
        "criteria": f"(Contact_Name.id:equals:{contact_id})and(Stage:equals:Closed Won)",
        "sort_by": "Closing_Date",
        "sort_order": "desc",
        "per_page": 5,
    }).get("data", [])

    past_trips = ", ".join(
        f"{d.get('BB_Destination','?')} ({d.get('Closing_Date','?')[:7]})"
        for d in history
    ) or "No previous bookings on record"

    prefs = {
        "room": contact.get("BB_Preferred_Room_Type", ""),
        "dietary": contact.get("BB_Dietary", ""),
        "style": contact.get("BB_Travel_Style", ""),
        "tier": contact.get("BB_Budget_Tier", ""),
        "loyalty": contact.get("BB_Loyalty_Programs", ""),
        "notes": contact.get("Description", ""),
    }
    prefs_str = " | ".join(f"{k}: {v}" for k, v in prefs.items() if v)

    return f"Name: {name}\nEmail: {contact.get('Email','')}\nPast trips: {past_trips}\nPreferences: {prefs_str or 'None on file'}"


def run(segment: str, campaign_goal: str, send: bool = False, limit: int = 50) -> dict:
    # Pull contacts by tag
    contacts_data = zoho.crm_get("Contacts", params={
        "fields": "Full_Name,First_Name,Last_Name,Email,Tag,BB_Preferred_Room_Type,"
                  "BB_Dietary,BB_Travel_Style,BB_Budget_Tier,BB_Loyalty_Programs,Description",
        "criteria": f"Tag:equals:{segment}",
        "per_page": min(limit, 200),
    })
    contacts = contacts_data.get("data", [])
    if not contacts:
        return {"error": f"No contacts found with tag '{segment}'"}

    client = anthropic.Anthropic()
    acct_id = _get_acct_id()
    sent, drafted, skipped = 0, 0, 0
    today = date.today()

    for contact in contacts:
        email = contact.get("Email", "")
        if not email:
            skipped += 1
            continue

        first_name = contact.get("First_Name") or (contact.get("Full_Name") or "").split()[0]
        context = _get_contact_context(contact)

        prompt = f"""You are writing a PERSONAL email from Butler Button to one specific client.
This is NOT a campaign blast. It should read like Carl wrote it personally after looking at their file.

Client data:
{context}

Campaign goal: {campaign_goal}

Write a 3-4 sentence email that:
- References something SPECIFIC from their history or preferences (a past destination, a preference on file, etc.)
- If no history exists, acknowledges they're a valued client without being generic
- Connects naturally to the campaign goal without being salesy
- Ends with a single low-friction question or offer

DO NOT use "I hope this email finds you well" or any corporate opener.
DO NOT use the word "luxury" or "exclusive".
Sign off: Carl, Butler Button

Output ONLY the email body (no subject line)."""

        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        body = resp.content[0].text.strip()
        subject = f"Thinking of you, {first_name}"

        endpoint = "messages" if send else "drafts"
        requests.post(
            f"{MAIL_BASE}/accounts/{acct_id}/{endpoint}",
            headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                     "Content-Type": "application/json"},
            json={"fromAddress": MAIL_FROM, "toAddress": email,
                  "subject": subject, "content": body, "mailFormat": "plaintext"},
        )

        # Log activity in CRM
        zoho.crm_post("Tasks", {"data": [{
            "Subject": f"{'Sent' if send else 'Draft'}: {campaign_goal[:60]}",
            "Due_Date": (today + timedelta(days=5)).isoformat(),
            "Priority": "Medium",
            "Status": "Not Started",
            "Description": f"Personalized email {'sent' if send else 'drafted'} — check for reply.",
            "What_Id": {"id": contact["id"], "type": "Contacts"},
        }]})

        if send:
            sent += 1
        else:
            drafted += 1

    # Cliq summary
    cliq_post({CLIQ_CHANNEL}, msg)

    return {"segment": segment, "total": len(contacts),
            "sent": sent, "drafted": drafted, "skipped": skipped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--segment", required=True, help="CRM contact tag (e.g. VIP, Maldives-2025)")
    parser.add_argument("--campaign-goal", required=True)
    parser.add_argument("--send", action="store_true", help="Auto-send (default: save as drafts)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    result = run(args.segment, args.campaign_goal, args.send, args.limit)
    print(json.dumps(result, indent=2) if "error" not in result else result["error"])

import json
