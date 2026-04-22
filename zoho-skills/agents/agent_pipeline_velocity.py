"""
AGENT 2: Pipeline Velocity Agent
Trigger: Cron — runs every morning at 06:30 IST.
Actions (fully autonomous):
  1. Find every open deal with no activity in 7+ days
  2. Claude drafts a personalized re-engagement email per deal
  3. Saves as Zoho Mail draft (7d stalled) OR auto-sends (14d+ stalled)
  4. Creates follow-up task linked to each deal
  5. Posts Cliq heat map: stalled count, draft count, auto-sent count

Threshold logic:
  7-13 days: draft saved, you review before sending
  14+ days:  email auto-sends, task created, Cliq alert fires
"""

import json
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho, MAIL_BASE

CLIQ_CHANNEL = "sales-pipeline"
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def _acct_id() -> str:
    r = requests.get(f"{MAIL_BASE}/accounts",
                     headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"})
    return str(r.json()["data"][0]["accountId"])


def _draft_or_send(acct_id: str, to_email: str, subject: str, body: str, auto_send: bool):
    endpoint = "messages" if auto_send else "drafts"
    requests.post(
        f"{MAIL_BASE}/accounts/{acct_id}/{endpoint}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"fromAddress": MAIL_FROM, "toAddress": to_email,
              "subject": subject, "content": body, "mailFormat": "plaintext"},
    )


def run():
    today = date.today()
    client = anthropic.Anthropic()
    acct_id = _acct_id()

    cutoff_7 = (today - timedelta(days=7)).isoformat()
    cutoff_14 = (today - timedelta(days=14)).isoformat()

    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Last_Activity_Time,Account_Name,Contact_Name,Owner,Description",
        "criteria": (
            f"(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)"
            f"and(Last_Activity_Time:less_equal:{cutoff_7}T00:00:00+05:30)"
        ),
        "per_page": 50,
    })
    deals = data.get("data", [])
    if not deals:
        return {"stalled": 0, "message": "Pipeline clean — no stalled deals."}

    drafts, auto_sent, tasks_created = 0, 0, 0
    due = (today + timedelta(days=1)).isoformat()

    for deal in deals:
        last_activity = deal.get("Last_Activity_Time", "")
        days_stalled = (today - date.fromisoformat(last_activity[:10])).days if last_activity else 99
        auto_send = days_stalled >= 14

        contact = deal.get("Contact_Name") or {}
        contact_name = contact.get("name", "") if isinstance(contact, dict) else str(contact)
        deal_name = deal.get("Deal_Name", "")
        amount = deal.get("Amount", 0)
        stage = deal.get("Stage", "")

        # Get contact email
        contact_id = contact.get("id") if isinstance(contact, dict) else None
        contact_email = ""
        if contact_id:
            c_data = zoho.crm_get(f"Contacts/{contact_id}", params={"fields": "Email"})
            contact_email = (c_data.get("data") or [{}])[0].get("Email", "")

        # Claude drafts re-engagement email
        prompt = f"""You are writing a re-engagement email for Butler Button, a premium luxury travel concierge.
Deal: {deal_name}  |  Stage: {stage}  |  Value: Rs.{amount:,.0f}
Client: {contact_name}  |  Days since last contact: {days_stalled}
Context: {deal.get('Description','None')}

Write a 2-3 sentence re-engagement email that:
- References the specific trip or inquiry naturally (not robotically)
- Adds a single new hook (a seasonal angle, a limited availability nudge, or a new property/experience)
- Ends with one low-friction CTA (a call, a quick question, or a yes/no)

Do NOT say "I noticed we haven't spoken" or anything passive-aggressive.
Tone: warm, premium, brief. Sign off as "The Butler Button Team".
Output ONLY the email body."""

        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}]
        )
        body = resp.content[0].text.strip()
        subject = f"Re: {deal_name}" if contact_name else f"Following up — {deal_name}"

        if contact_email:
            _draft_or_send(acct_id, contact_email, subject, body, auto_send)
            if auto_send:
                auto_sent += 1
            else:
                drafts += 1

        # Create task
        zoho.crm_post("Tasks", {"data": [{
            "Subject": f"{'AUTO-SENT' if auto_send else 'DRAFT READY'}: Re-engage {deal_name} ({days_stalled}d stalled)",
            "Due_Date": due,
            "Priority": "High",
            "Status": "Not Started",
            "Description": body[:500],
            "What_Id": {"id": deal["id"], "type": "Deals"},
        }]})
        tasks_created += 1

    # Cliq heat map
    heat = (
        f"PIPELINE HEAT MAP — {today.isoformat()}\n"
        f"Stalled deals found: {len(deals)}\n"
        f"  Drafts saved (7-13d): {drafts}  — review in Zoho Mail before sending\n"
        f"  Auto-sent (14d+):     {auto_sent}  — already gone\n"
        f"  Tasks created:        {tasks_created}\n\n"
        + "\n".join(
            f"  [{(today - date.fromisoformat(d.get('Last_Activity_Time','2020-01-01')[:10])).days}d] "
            f"{d['Deal_Name']}  Rs.{d.get('Amount',0):,.0f}  {d.get('Stage')}"
            for d in sorted(deals, key=lambda x: x.get("Last_Activity_Time",""), reverse=False)[:8]
        )
    )
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": heat},
    )

    return {"stalled": len(deals), "drafts": drafts, "auto_sent": auto_sent, "tasks": tasks_created}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
