"""Lead management skills for the Butler Button CSMO agent."""

from datetime import date, timedelta
from claude_agent import tool
from zoho_client import zoho


@tool
def get_new_leads(days: int = 7) -> str:
    """Return leads created in the past N days.

    Args:
        days: Lookback window in days (default 7).
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    data = zoho.crm_get("Leads", params={
        "fields": "First_Name,Last_Name,Email,Phone,Lead_Source,Lead_Status,Rating,Created_Time",
        "criteria": f"Created_Time:greater_equal:{since}T00:00:00+05:30",
        "sort_by": "Created_Time",
        "sort_order": "desc",
        "per_page": 100,
    })
    leads = data.get("data", [])
    if not leads:
        return f"No new leads in the past {days} days."
    lines = [f"New leads ({days}d): {len(leads)} total"]
    for l in leads:
        name = f"{l.get('First_Name','')} {l.get('Last_Name','')}".strip()
        lines.append(
            f"  {name}  |  {l.get('Lead_Source','—')}  |  {l.get('Lead_Status','—')}  |  {l.get('Email','—')}"
        )
    return "\n".join(lines)


@tool
def get_lead_source_breakdown() -> str:
    """Return count of leads by source channel for the current month."""
    first_of_month = date.today().replace(day=1).isoformat()
    today = date.today().isoformat()
    data = zoho.crm_get("Leads", params={
        "fields": "Lead_Source",
        "criteria": f"Created_Time:between:{first_of_month}T00:00:00+05:30,{today}T23:59:59+05:30",
        "per_page": 200,
    })
    leads = data.get("data", [])
    sources: dict[str, int] = {}
    for l in leads:
        src = l.get("Lead_Source") or "Unknown"
        sources[src] = sources.get(src, 0) + 1
    lines = [f"Lead sources MTD ({len(leads)} leads):"]
    for src, cnt in sorted(sources.items(), key=lambda x: -x[1]):
        pct = cnt / len(leads) * 100 if leads else 0
        lines.append(f"  {src}: {cnt}  ({pct:.0f}%)")
    return "\n".join(lines)


@tool
def convert_lead(lead_id: str, account_name: str = None) -> str:
    """Convert a qualified lead to Contact + Deal in Zoho CRM.

    Args:
        lead_id: Zoho CRM Lead record ID.
        account_name: Optional account/company name for the new record.
    """
    payload: dict = {"overwrite": True, "notify_lead_owner": True, "notify_new_entity_owner": True}
    if account_name:
        payload["Accounts"] = {"Account_Name": account_name}
    result = zoho.crm_post(f"Leads/{lead_id}/actions/convert", {"data": [payload]})
    converted = result.get("data", [{}])[0]
    contact_id = (converted.get("Contacts") or {}).get("id", "—")
    deal_id = (converted.get("Deals") or {}).get("id", "—")
    return f"Lead converted. Contact ID: {contact_id}  Deal ID: {deal_id}"


@tool
def qualify_lead(lead_id: str, rating: str, status: str, notes: str = "") -> str:
    """Update lead qualification fields (rating, status, notes).

    Args:
        lead_id: Zoho CRM Lead record ID.
        rating: Rating value — Hot, Warm, or Cold.
        status: Lead status picklist value.
        notes: Optional qualification notes appended to Description.
    """
    payload: dict = {"Rating": rating, "Lead_Status": status}
    if notes:
        payload["Description"] = notes
    zoho.crm_put(f"Leads/{lead_id}", {"data": [payload]})
    return f"Lead {lead_id} qualified: {rating} / {status}."
