"""
AGENT 3: Morning Brief Agent
Trigger: Cron — fires at 07:00 IST every weekday.
Actions:
  1. Pulls live data from Zoho CRM (pipeline, tasks, leads, forecast)
  2. Claude synthesizes into a sharp executive brief with ranked priorities
  3. Posts to Cliq #csmo-daily
  4. Sends as email to CSMO

No fluff. Numbers only. Tells you what to do first.
"""

import json
import anthropic
import requests
from datetime import date, timedelta
from zoho_client import zoho, MAIL_BASE

CLIQ_CHANNEL = "csmo-daily"
CSMO_EMAIL = __import__("os").environ.get("CSMO_EMAIL", "carlremi@gmail.com")
MAIL_FROM = __import__("os").environ.get("ZOHO_MAIL_FROM", "")


def _collect_data() -> dict:
    today = date.today()
    week = (today + timedelta(days=7)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    stale_14 = (today - timedelta(days=14)).isoformat()

    tasks = zoho.crm_get("Tasks", params={
        "fields": "Subject,Priority,What_Id,Due_Date",
        "criteria": f"(Due_Date:equals:{today.isoformat()})and(Status:not_equal:Completed)",
        "per_page": 50,
    }).get("data", [])

    overdue = zoho.crm_get("Tasks", params={
        "fields": "Subject,Due_Date",
        "criteria": f"(Due_Date:less_equal:{yesterday})and(Status:not_equal:Completed)",
        "per_page": 20,
    }).get("data", [])

    closing_soon = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Closing_Date,Probability",
        "criteria": f"(Closing_Date:between:{today.isoformat()},{week})and(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "per_page": 20,
    }).get("data", [])

    stalled = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Last_Activity_Time",
        "criteria": f"(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)and(Last_Activity_Time:less_equal:{stale_14}T00:00:00+05:30)",
        "per_page": 20,
    }).get("data", [])

    new_leads = zoho.crm_get("Leads", params={
        "fields": "First_Name,Last_Name,Lead_Source,Rating",
        "criteria": f"Created_Time:greater_equal:{yesterday}T00:00:00+05:30",
        "per_page": 50,
    }).get("data", [])

    pipeline = zoho.crm_get("Deals", params={
        "fields": "Stage,Amount,Probability",
        "criteria": "(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "per_page": 200,
    }).get("data", [])

    weighted = sum((d.get("Amount") or 0) * (d.get("Probability") or 0) / 100 for d in pipeline)
    gross = sum(d.get("Amount") or 0 for d in pipeline)

    return {
        "date": today.isoformat(),
        "tasks_today": len(tasks),
        "task_subjects": [t.get("Subject","—") for t in tasks[:5]],
        "overdue_count": len(overdue),
        "closing_soon": [
            f"{d['Deal_Name']} Rs.{d.get('Amount',0):,.0f} closes {d.get('Closing_Date')}"
            for d in sorted(closing_soon, key=lambda x: -(x.get("Amount") or 0))[:5]
        ],
        "stalled_count": len(stalled),
        "stalled_value": sum(d.get("Amount") or 0 for d in stalled),
        "new_leads_24h": len(new_leads),
        "hot_leads": [
            f"{l.get('First_Name','')} {l.get('Last_Name','')} ({l.get('Lead_Source','—')})"
            for l in new_leads if l.get("Rating") == "Hot"
        ],
        "pipeline_gross": gross,
        "pipeline_weighted": weighted,
        "open_deals": len(pipeline),
    }


def run():
    data = _collect_data()
    client = anthropic.Anthropic()

    prompt = f"""You are the AI chief of staff for Butler Button, a 2-person luxury travel concierge.
Today is {data['date']}.

Raw CRM data:
- Tasks due today: {data['tasks_today']}
- Today's tasks: {', '.join(data['task_subjects']) or 'none'}
- Overdue tasks: {data['overdue_count']}
- Deals closing this week: {chr(10).join(data['closing_soon']) or 'none'}
- Stalled deals: {data['stalled_count']} worth Rs.{data['stalled_value']:,.0f}
- New leads (24h): {data['new_leads_24h']} (hot: {len(data['hot_leads'])})
- Hot leads: {', '.join(data['hot_leads']) or 'none'}
- Pipeline gross: Rs.{data['pipeline_gross']:,.0f}  |  Weighted: Rs.{data['pipeline_weighted']:,.0f}
- Open deals: {data['open_deals']}

Write a sharp morning brief in exactly this format:

BRIEF — {data['date']}

NUMBERS
[4-5 bullet KPIs, numbers only]

PRIORITY ORDER
1. [Most urgent action — be specific]
2. [Second action]
3. [Third action]

RISK
[One sentence: biggest threat to revenue today]

Keep it under 200 words. Zero fluff. Assume the reader has 90 seconds."""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    brief = resp.content[0].text.strip()

    # Post to Cliq
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_CHANNEL}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": brief},
    )

    # Send as email
    acct_r = requests.get(f"{MAIL_BASE}/accounts",
                          headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"})
    acct_id = acct_r.json()["data"][0]["accountId"]
    requests.post(
        f"{MAIL_BASE}/accounts/{acct_id}/messages",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"fromAddress": MAIL_FROM, "toAddress": CSMO_EMAIL,
              "subject": f"Butler Button Brief — {data['date']}",
              "content": brief, "mailFormat": "plaintext"},
    )

    return {"brief": brief, "cliq_posted": True, "email_sent": True}


if __name__ == "__main__":
    result = run()
    print(result["brief"])
