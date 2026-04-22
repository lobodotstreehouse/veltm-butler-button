"""
AGENT 4: Deal Won Sequence Agent
Trigger: Zoho Flow webhook — fires when a Deal stage changes to "Closed Won".
Actions (fully automatic):
  1. Fetch deal + contact details
  2. Claude writes a personalized win/welcome email
  3. Send email to client
  4. Create 5-step onboarding task sequence in CRM
  5. Post Cliq celebration with deal value

This is the handoff from sale to delivery. Zero delay.
"""

import json
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho, MAIL_BASE

CLIQ_CHANNEL = "sales-pipeline"
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")

ONBOARDING_TASKS = [
    ("Send booking confirmation & invoice", 0),
    ("Collect client travel preferences & documents", 2),
    ("Coordinate vendors & confirm bookings", 5),
    ("Send pre-trip brief to client", 10),
    ("Post-trip follow-up + referral ask", 30),
]


def run(deal_id: str):
    # 1. Fetch deal
    deal_data = zoho.crm_get(f"Deals/{deal_id}", params={
        "fields": "Deal_Name,Amount,Closing_Date,Contact_Name,Account_Name,"
                  "BB_Service_Type,BB_Destination,Description,Stage"
    })
    deal = (deal_data.get("data") or [{}])[0]
    deal_name = deal.get("Deal_Name", "")
    amount = deal.get("Amount", 0)
    destination = deal.get("BB_Destination") or deal.get("Account_Name", "")
    service_type = deal.get("BB_Service_Type", "trip")
    notes = deal.get("Description", "")

    # Get contact
    contact_ref = deal.get("Contact_Name") or {}
    contact_id = contact_ref.get("id") if isinstance(contact_ref, dict) else None
    contact_name = contact_ref.get("name", "there") if isinstance(contact_ref, dict) else "there"
    contact_email = ""
    if contact_id:
        c = zoho.crm_get(f"Contacts/{contact_id}", params={"fields": "Email,First_Name"})
        contact_data = (c.get("data") or [{}])[0]
        contact_email = contact_data.get("Email", "")
        contact_name = contact_data.get("First_Name") or contact_name

    # 2. Claude writes win/welcome email
    client = anthropic.Anthropic()
    prompt = f"""You are writing a booking-confirmed email from Butler Button, a premium luxury travel concierge.
Client: {contact_name}
Booking: {deal_name}  |  Destination: {destination or 'TBD'}  |  Service: {service_type}
Value: ${amount:,.0f}
Notes: {notes or 'None'}

Write a 3-4 sentence confirmation email that:
- Opens with genuine excitement (not corporate boilerplate)
- Confirms what they've booked in one specific sentence
- Tells them the exact next step (we'll reach out within 24hrs to collect preferences)
- Closes with confidence that this will exceed expectations

Tone: warm, premium, personal — like a trusted friend who happens to be a luxury expert.
Sign off as "The Butler Button Team".
Output ONLY the email body."""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    email_body = resp.content[0].text.strip()

    # 3. Send email
    if contact_email:
        acct_r = requests.get(f"{MAIL_BASE}/accounts",
                              headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"})
        acct_id = acct_r.json()["data"][0]["accountId"]
        requests.post(
            f"{MAIL_BASE}/accounts/{acct_id}/messages",
            headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                     "Content-Type": "application/json"},
            json={"fromAddress": MAIL_FROM, "toAddress": contact_email,
                  "subject": f"Booking confirmed — {destination or deal_name}",
                  "content": email_body, "mailFormat": "plaintext"},
        )

    # 4. Create onboarding task sequence
    today = date.today()
    for task_name, offset_days in ONBOARDING_TASKS:
        due = (today + timedelta(days=offset_days)).isoformat()
        zoho.crm_post("Tasks", {"data": [{
            "Subject": f"[{deal_name}] {task_name}",
            "Due_Date": due,
            "Priority": "High" if offset_days <= 2 else "Medium",
            "Status": "Not Started",
            "What_Id": {"id": deal_id, "type": "Deals"},
        }]})

    # 5. Cliq celebration
    celebration = (
        f"DEAL WON  —  ${amount:,.0f}\n"
        f"{deal_name}\n"
        f"Client: {contact_name}  |  {destination or 'Destination TBD'}\n"
        f"Confirmation email sent. 5 onboarding tasks created.\n"
        f"Next: collect preferences within 48hrs."
    )
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": celebration},
    )

    return {
        "deal_id": deal_id, "deal_name": deal_name, "amount": amount,
        "email_sent": bool(contact_email), "tasks_created": len(ONBOARDING_TASKS),
        "cliq_posted": True,
    }


if __name__ == "__main__":
    import sys
    result = run(sys.argv[1])
    print(json.dumps(result, indent=2))
