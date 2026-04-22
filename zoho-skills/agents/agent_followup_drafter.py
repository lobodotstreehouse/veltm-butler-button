"""
AGENT 5: Follow-up Drafter Agent
Trigger: CLI after any call — takes 30 seconds.
Usage: python agent_followup_drafter.py <contact_id> "<call notes>"

Actions:
  1. Fetch contact + open deal from CRM
  2. Claude writes personalized follow-up email referencing the exact call notes
  3. Saves as Zoho Mail draft (you review, then send)
  4. Logs the call in CRM with notes
  5. Creates next follow-up task (3 days)
  6. Optionally posts Cliq note to #sales-pipeline

The draft is waiting in your inbox the second you hang up.
"""

import json
import sys
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho, MAIL_BASE

MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def run(contact_id: str, call_notes: str, duration_min: int = 15, post_cliq: bool = False):
    # 1. Fetch contact + open deal
    c_data = zoho.crm_get(f"Contacts/{contact_id}", params={
        "fields": "First_Name,Last_Name,Email,Account_Name,Phone"
    })
    contact = (c_data.get("data") or [{}])[0]
    first_name = contact.get("First_Name", "there")
    full_name = f"{first_name} {contact.get('Last_Name','')}".strip()
    email = contact.get("Email", "")

    deal_data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,BB_Destination,BB_Service_Type",
        "criteria": f"(Contact_Name.id:equals:{contact_id})and(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "per_page": 1,
    })
    deals = deal_data.get("data", [])
    deal = deals[0] if deals else {}
    deal_name = deal.get("Deal_Name", "")
    destination = deal.get("BB_Destination") or deal.get("Account_Name", "")

    # 2. Claude drafts follow-up
    client = anthropic.Anthropic()
    prompt = f"""You are writing a post-call follow-up email for Butler Button, a premium luxury travel concierge.
Client: {first_name}  |  Deal: {deal_name or 'Inquiry'}  |  Destination: {destination or 'TBD'}
Call notes: "{call_notes}"

Write a concise follow-up email (3-4 sentences) that:
- Opens by referencing one specific thing from the call notes (not generic)
- Recaps the 1-2 key decisions or commitments made
- States the clear next step with a timeline
- Feels personal, not templated

Tone: premium, confident, brief. Sign off as "The Butler Button Team".
Output ONLY the email body."""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    email_body = resp.content[0].text.strip()
    subject = f"Great speaking with you, {first_name}" if not deal_name else f"Next steps — {deal_name}"

    # 3. Save as draft
    if email:
        acct_r = requests.get(f"{MAIL_BASE}/accounts",
                              headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"})
        acct_id = acct_r.json()["data"][0]["accountId"]
        requests.post(
            f"{MAIL_BASE}/accounts/{acct_id}/drafts",
            headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                     "Content-Type": "application/json"},
            json={"fromAddress": MAIL_FROM, "toAddress": email,
                  "subject": subject, "content": email_body, "mailFormat": "plaintext"},
        )

    # 4. Log call in CRM
    zoho.crm_post("Calls", {"data": [{
        "Subject": f"Call — {full_name} re: {deal_name or 'inquiry'}",
        "Call_Type": "Outbound",
        "Call_Duration": str(duration_min),
        "Call_Result": "Interested",
        "Description": call_notes,
        "Who_Id": {"id": contact_id, "type": "Contacts"},
        "Call_Start_Time": f"{date.today().isoformat()}T12:00:00-05:00",
    }]})

    # 5. Create next follow-up task
    follow_up_date = (date.today() + timedelta(days=3)).isoformat()
    zoho.crm_post("Tasks", {"data": [{
        "Subject": f"Follow up: {full_name}" + (f" — {deal_name}" if deal_name else ""),
        "Due_Date": follow_up_date,
        "Priority": "High",
        "Status": "Not Started",
        "Description": f"Called {date.today().isoformat()}. Notes: {call_notes}",
        "What_Id": {"id": contact_id, "type": "Contacts"},
    }]})

    # 6. Optional Cliq note
    if post_cliq:
        requests.post(
            "https://cliq.zoho.in/api/v2/channels/sales-pipeline/message",
            headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                     "Content-Type": "application/json"},
            json={"text": (
                f"CALL LOGGED — {full_name}\n"
                f"Deal: {deal_name or '—'}  |  {duration_min}min\n"
                f"Notes: {call_notes[:200]}\n"
                f"Draft ready. Follow-up task: {follow_up_date}"
            )},
        )

    return {
        "contact": full_name, "email": email, "draft_saved": bool(email),
        "call_logged": True, "task_date": follow_up_date,
        "draft_preview": email_body[:300],
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python agent_followup_drafter.py <contact_id> '<call notes>' [duration_minutes]")
        sys.exit(1)
    contact_id = sys.argv[1]
    notes = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    result = run(contact_id, notes, duration, post_cliq=True)
    print(f"\nDraft saved for {result['contact']}")
    print(f"Follow-up task: {result['task_date']}")
    print(f"\nDraft preview:\n{result['draft_preview']}")
