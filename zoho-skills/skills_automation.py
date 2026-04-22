"""
Zoho automation skills for the Butler Button CSMO agent.
Covers Zoho Flow webhook triggers, CRM workflow rule inspection,
and scheduled CRM reporting via Zoho Analytics.

Required OAuth scope: ZohoFlow.flows.ALL (for Flow API)
India DC: flow.zoho.in
"""

import os
import requests
from datetime import date
from claude_agent import tool
from zoho_client import zoho

FLOW_BASE = "https://flow.zoho.in/api/v1"


def _flow_get(path: str, params: dict = None) -> dict:
    r = requests.get(
        f"{FLOW_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        params=params or {},
    )
    r.raise_for_status()
    return r.json()


# ── Zoho Flow ──────────────────────────────────────────────────────────────────

@tool
def trigger_flow_webhook(webhook_url: str, payload: dict) -> str:
    """Trigger a Zoho Flow via its webhook URL with a custom payload.

    Useful for firing automations from the agent — e.g. send onboarding email,
    generate itinerary PDF, or sync to an external system.

    Args:
        webhook_url: The Zoho Flow webhook URL (from Flow > Connections > Webhook).
        payload: Dictionary of data to send as JSON body.
    """
    r = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return f"Flow triggered  |  Status: {r.status_code}  |  Response: {r.text[:200]}"


@tool
def list_active_flows() -> str:
    """List all active Zoho Flow automations in this Zoho One account."""
    data = _flow_get("flows", params={"status": "active"})
    flows = data.get("flows", [])
    if not flows:
        return "No active Zoho Flows found."
    lines = [f"Active Zoho Flows ({len(flows)}):"]
    for f in flows:
        lines.append(
            f"  [{f.get('id','—')}] {f.get('name','—')}  |  "
            f"Trigger: {f.get('trigger',{}).get('type','—')}  |  "
            f"Status: {f.get('status','—')}"
        )
    return "\n".join(lines)


@tool
def get_flow_execution_history(flow_id: str, limit: int = 10) -> str:
    """Return recent execution history for a Zoho Flow.

    Args:
        flow_id: Numeric Flow ID (from list_active_flows).
        limit: Number of executions to return (default 10).
    """
    data = _flow_get(f"flows/{flow_id}/executions", params={"limit": limit})
    executions = data.get("executions", [])
    if not executions:
        return f"No executions found for Flow {flow_id}."
    lines = [f"Executions for Flow {flow_id}:"]
    for e in executions:
        status = e.get("status", "—")
        started = (e.get("startedAt") or "—")[:19]
        lines.append(f"  [{started}]  {status}")
    return "\n".join(lines)


# ── CRM Workflow & Automation Rules ───────────────────────────────────────────

@tool
def list_crm_workflow_rules() -> str:
    """List all active workflow rules configured in Zoho CRM."""
    data = zoho.crm_get("settings/workflow_rules", params={"module": "Deals"})
    rules = data.get("workflow_rules", [])
    if not rules:
        return "No CRM workflow rules found for Deals module."
    lines = [f"CRM Workflow Rules — Deals ({len(rules)}):"]
    for r in rules:
        lines.append(
            f"  [{r.get('id','—')}] {r.get('rule_name','—')}  |  "
            f"Trigger: {r.get('trigger',{}).get('type','—')}  |  "
            f"Active: {r.get('active',False)}"
        )
    return "\n".join(lines)


# ── Scheduled CSMO Reporting ───────────────────────────────────────────────────

@tool
def run_end_of_day_report(cliq_channel: str = "csmo-daily") -> str:
    """Generate and post a full end-of-day CSMO report to Zoho Cliq.

    Compiles: MTD revenue, pipeline snapshot, new leads, overdue tasks.
    Posts result to the specified Cliq channel.

    Args:
        cliq_channel: Cliq channel to receive the report (default 'csmo-daily').
    """
    from skills_pipeline import get_pipeline_summary, get_won_deals_mtd, get_stalled_deals
    from skills_leads import get_new_leads
    from skills_activities import get_overdue_tasks

    report_parts = [
        f"END-OF-DAY CSMO REPORT  —  {date.today().isoformat()}",
        "",
        "── REVENUE ──",
        get_won_deals_mtd(),
        "",
        "── PIPELINE ──",
        get_pipeline_summary(),
        "",
        "── STALLED DEALS ──",
        get_stalled_deals(14),
        "",
        "── NEW LEADS (7d) ──",
        get_new_leads(7),
        "",
        "── OVERDUE TASKS ──",
        get_overdue_tasks(),
    ]
    full_report = "\n".join(report_parts)

    # Post to Cliq
    import requests as _r
    _r.post(
        f"https://cliq.zoho.in/api/v2/channels/{cliq_channel}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}", "Content-Type": "application/json"},
        json={"text": full_report},
    )
    return f"End-of-day report posted to #{cliq_channel}.\n\n{full_report[:600]}..."


@tool
def auto_follow_up_stalled_deals(
    inactive_days: int = 14,
    cliq_channel: str = "sales-pipeline",
) -> str:
    """Find stalled deals, create follow-up tasks, and alert the Cliq channel.

    Combines pipeline analysis + task creation + Cliq notification in one command.

    Args:
        inactive_days: Inactivity threshold in days (default 14).
        cliq_channel: Cliq channel for alert (default 'sales-pipeline').
    """
    from skills_pipeline import get_stalled_deals
    from skills_activities import create_task
    from datetime import date, timedelta
    import requests as _r

    stalled_text = get_stalled_deals(inactive_days)
    stalled_data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,id,Owner",
        "criteria": (
            f"(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)"
            f"and(Last_Activity_Time:less_equal:{(date.today() - timedelta(days=inactive_days)).isoformat()}T00:00:00-05:00)"
        ),
        "per_page": 20,
    })
    deals = stalled_data.get("data", [])
    due = (date.today() + timedelta(days=1)).isoformat()
    for d in deals:
        create_task(
            subject=f"Re-engage: {d['Deal_Name']}",
            due_date=due,
            related_to_id=d["id"],
            related_to_type="Deals",
            priority="High",
            description=f"Deal stalled {inactive_days}+ days. Reach out today.",
        )

    alert = (
        f"AUTO FOLLOW-UP TRIGGERED\n"
        f"Created {len(deals)} re-engagement tasks for stalled deals.\n\n"
        f"{stalled_text}"
    )
    _r.post(
        f"https://cliq.zoho.in/api/v2/channels/{cliq_channel}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}", "Content-Type": "application/json"},
        json={"text": alert},
    )
    return f"Follow-up tasks created for {len(deals)} stalled deals. Alert posted to #{cliq_channel}."
