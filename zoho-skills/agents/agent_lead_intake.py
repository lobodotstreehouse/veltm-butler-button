"""
AGENT 1: Lead Intake Agent
Trigger: Zoho Flow webhook — fires the instant a new Lead is created in CRM.
Actions (all automatic, under 90 seconds):
  1. Pull full lead details from CRM
  2. Score the lead (budget signals, source, destination)
  3. Claude writes a personalized first-response email
  4. Send email via Zoho Mail
  5. Create "Call within 1hr" task in CRM
  6. Post hot-lead alert to Cliq #leads

Deploy: webhook_server.py routes POST /webhook/lead-intake here.
"""

import json
import anthropic
from datetime import date, timedelta
from zoho_client import zoho

CLIQ_CHANNEL = "leads"
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def score_lead(lead: dict) -> tuple[str, str]:
    """Return (rating, reason) based on lead signals."""
    source = lead.get("Lead_Source", "")
    desc = (lead.get("Description") or "").lower()
    budget_signals = any(w in desc for w in ["lakh", "lakhs", "budget", "₹", "rs.", "luxury", "private", "villa"])
    dest_signals = any(w in desc for w in ["maldives", "europe", "bali", "dubai", "switzerland", "private"])
    referral = "referral" in source.lower() or "word" in source.lower()

    if referral or (budget_signals and dest_signals):
        return "Hot", "Referral or high-budget + destination signal"
    if budget_signals or dest_signals or source.lower() in ["website", "butler button website"]:
        return "Warm", "Website or single intent signal"
    return "Cold", "Low signal"


def run(lead_id: str):
    # 1. Fetch lead
    data = zoho.crm_get(f"Leads/{lead_id}", params={
        "fields": "First_Name,Last_Name,Email,Phone,Lead_Source,Description,Rating,Lead_Status"
    })
    lead = (data.get("data") or [{}])[0]
    name = f"{lead.get('First_Name','')} {lead.get('Last_Name','')}".strip()
    email = lead.get("Email", "")
    source = lead.get("Lead_Source", "Unknown")
    notes = lead.get("Description", "")

    # 2. Score
    rating, reason = score_lead(lead)

    # 3. Write personalized first-response email via Claude
    client = anthropic.Anthropic()
    prompt = f"""You are writing a first-response email from Butler Button, a premium luxury travel concierge.
The lead's name is {name}, source: {source}.
Their notes/message: "{notes}"

Write a warm, confident, 3-sentence reply that:
- Acknowledges their specific interest (pull any detail from their notes)
- Establishes Butler Button's expertise without bragging
- Asks ONE specific qualifying question (budget range OR travel dates OR group size)

Tone: premium but human. No fluff. Sign off as "The Butler Button Team".
Output ONLY the email body, no subject line."""

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    email_body = response.content[0].text.strip()
    subject = f"Your Butler Button inquiry — {name.split()[0] if name else 'there'}"

    # 4. Send email
    if email:
        import requests as _r
        from zoho_client import MAIL_BASE, zoho as _z
        acct_r = _r.get(f"{MAIL_BASE}/accounts", headers={"Authorization": f"Zoho-oauthtoken {_z.token}"})
        acct_id = acct_r.json()["data"][0]["accountId"]
        _r.post(
            f"{MAIL_BASE}/accounts/{acct_id}/messages",
            headers={"Authorization": f"Zoho-oauthtoken {_z.token}", "Content-Type": "application/json"},
            json={"fromAddress": MAIL_FROM, "toAddress": email, "subject": subject,
                  "content": email_body, "mailFormat": "plaintext"},
        )

    # 5. Update lead rating + create task
    zoho.crm_put(f"Leads/{lead_id}", {"data": [{"Rating": rating, "Lead_Status": "Contacted"}]})
    due = (date.today() + timedelta(hours=1)).isoformat()[:10]
    zoho.crm_post("Tasks", {"data": [{
        "Subject": f"CALL NOW: {name} ({source})",
        "Due_Date": due,
        "Priority": "High",
        "Status": "Not Started",
        "Description": f"Auto-scored {rating}: {reason}\nLead notes: {notes}",
        "What_Id": {"id": lead_id, "type": "Leads"},
    }]})

    # 6. Cliq alert
    import requests as _r2
    alert = (
        f"NEW LEAD — {rating.upper()}\n"
        f"Name: {name}  |  Source: {source}\n"
        f"Email: {email or '—'}\n"
        f"Score: {rating} ({reason})\n"
        f"Notes: {notes[:120] or '—'}\n"
        f"Action: First response sent. Call within 1hr task created."
    )
    _r2.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}", "Content-Type": "application/json"},
        json={"text": alert},
    )

    return {
        "lead_id": lead_id, "name": name, "rating": rating,
        "email_sent": bool(email), "task_created": True, "cliq_posted": True
    }


if __name__ == "__main__":
    import sys
    result = run(sys.argv[1])
    print(json.dumps(result, indent=2))
