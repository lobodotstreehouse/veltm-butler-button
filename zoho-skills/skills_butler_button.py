"""
Butler Button–specific concierge CRM skills.
Maps to the 'Service_Requests' and 'Contacts' modules in Zoho CRM,
with custom fields provisioned for the BB concierge workflow.
"""

from datetime import date, timedelta
from claude_agent import tool
from zoho_client import zoho


# ── Concierge Request Management ──────────────────────────────────────────────

@tool
def get_active_requests() -> str:
    """Return all open Butler Button concierge service requests."""
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Account_Name,Closing_Date,Description,Owner,BB_Service_Type,BB_Destination",
        "criteria": "(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)and(BB_Service_Type:is_not_empty:true)",
        "sort_by": "Closing_Date",
        "per_page": 100,
    })
    requests = data.get("data", [])
    if not requests:
        return "No active concierge requests."
    lines = [f"Active concierge requests ({len(requests)}):"]
    for r in requests:
        owner = (r.get("Owner") or {}).get("name", "—")
        lines.append(
            f"  [{r.get('Stage','—')}] {r['Deal_Name']}  |  "
            f"{r.get('BB_Service_Type','—')}  →  {r.get('BB_Destination','—')}  |  "
            f"closes {r.get('Closing_Date','—')}  Owner: {owner}"
        )
    return "\n".join(lines)


@tool
def create_service_request(
    client_name: str,
    service_type: str,
    destination: str,
    travel_date: str,
    budget_usd: float = 0,
    notes: str = "",
) -> str:
    """Create a new Butler Button concierge service request as a CRM Deal.

    Args:
        client_name: Full name of the client (existing contact name or new).
        service_type: Type of service — e.g. Hotel, Villa, Flight, Experience, Itinerary.
        destination: Destination city or region.
        travel_date: Approximate travel date YYYY-MM-DD.
        budget_usd: Client's stated budget in USD.
        notes: Intake notes from conversation or form.
    """
    payload = {
        "Deal_Name": f"{client_name} — {service_type} — {destination}",
        "Stage": "Qualification",
        "Closing_Date": travel_date,
        "Amount": budget_usd,
        "BB_Service_Type": service_type,
        "BB_Destination": destination,
        "Description": notes,
        "Lead_Source": "Butler Button Website",
    }
    result = zoho.crm_post("Deals", {"data": [payload]})
    deal_id = (result.get("data") or [{}])[0].get("details", {}).get("id", "—")
    return f"Service request created: '{payload['Deal_Name']}'  ID: {deal_id}"


@tool
def get_upcoming_trips(days: int = 90) -> str:
    """Return confirmed trips departing in the next N days.

    Args:
        days: Lookahead window in days (default 90).
    """
    today = date.today().isoformat()
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Account_Name,Closing_Date,BB_Service_Type,BB_Destination,Stage,Owner",
        "criteria": (
            f"(Stage:equals:Closed Won)"
            f"and(Closing_Date:between:{today},{cutoff})"
        ),
        "sort_by": "Closing_Date",
        "per_page": 100,
    })
    trips = data.get("data", [])
    if not trips:
        return f"No confirmed trips in the next {days} days."
    lines = [f"Upcoming confirmed trips (next {days}d):  {len(trips)} total"]
    for t in trips:
        lines.append(
            f"  [{t.get('Closing_Date')}] {t['Deal_Name']}  "
            f"{t.get('BB_Destination','—')}  ({t.get('BB_Service_Type','—')})"
        )
    return "\n".join(lines)


@tool
def get_client_preferences(contact_id: str) -> str:
    """Return a client's stored concierge preferences and travel history.

    Args:
        contact_id: Zoho CRM Contact record ID.
    """
    data = zoho.crm_get(f"Contacts/{contact_id}", params={
        "fields": (
            "Full_Name,Email,Phone,Account_Name,Description,"
            "BB_Preferred_Room_Type,BB_Dietary,BB_Loyalty_Programs,"
            "BB_Travel_Style,BB_Budget_Tier,Tag"
        )
    })
    c = (data.get("data") or [{}])[0]

    history = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Closing_Date,BB_Destination,BB_Service_Type",
        "criteria": f"(Contact_Name.id:equals:{contact_id})and(Stage:equals:Closed Won)",
        "sort_by": "Closing_Date",
        "sort_order": "desc",
        "per_page": 10,
    })
    past = history.get("data", [])

    lines = [
        f"Client profile: {c.get('Full_Name','—')}",
        f"  Email: {c.get('Email','—')}  |  Phone: {c.get('Phone','—')}",
        f"  Travel style: {c.get('BB_Travel_Style','—')}  |  Budget tier: {c.get('BB_Budget_Tier','—')}",
        f"  Room preference: {c.get('BB_Preferred_Room_Type','—')}",
        f"  Dietary: {c.get('BB_Dietary','—')}",
        f"  Loyalty programs: {c.get('BB_Loyalty_Programs','—')}",
        f"  Tags: {c.get('Tag','—')}",
        f"  Notes: {c.get('Description','—')}",
        "",
        f"Past bookings ({len(past)}):",
    ]
    for p in past:
        lines.append(f"  {p.get('Closing_Date','—')[:7]}  {p.get('BB_Destination','—')}  ({p.get('BB_Service_Type','—')})")
    return "\n".join(lines)


# ── CSMO Reporting Skills ──────────────────────────────────────────────────────

@tool
def get_daily_csmo_brief() -> str:
    """Return a full CSMO morning brief: tasks, pipeline, new leads, stalled deals."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    tasks_data = zoho.crm_get("Tasks", params={
        "fields": "Subject,Priority,What_Id",
        "criteria": f"(Due_Date:equals:{today})and(Status:not_equal:Completed)",
        "per_page": 50,
    })
    tasks = tasks_data.get("data", [])

    overdue_data = zoho.crm_get("Tasks", params={
        "fields": "Subject,Due_Date",
        "criteria": f"(Due_Date:less_equal:{yesterday})and(Status:not_equal:Completed)",
        "per_page": 20,
    })
    overdue = overdue_data.get("data", [])

    new_leads_data = zoho.crm_get("Leads", params={
        "fields": "First_Name,Last_Name,Lead_Source",
        "criteria": f"Created_Time:greater_equal:{week_ago}T00:00:00-05:00",
        "per_page": 100,
    })
    new_leads = new_leads_data.get("data", [])

    stalled_cutoff = (date.today() - timedelta(days=14)).isoformat()
    stalled_data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount",
        "criteria": f"(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)and(Last_Activity_Time:less_equal:{stalled_cutoff}T00:00:00-05:00)",
        "per_page": 20,
    })
    stalled = stalled_data.get("data", [])

    lines = [
        f"═══  Butler Button CSMO Brief  —  {today}  ═══",
        "",
        f"✓  Tasks due today:    {len(tasks)}",
        f"⚠  Overdue tasks:      {len(overdue)}",
        f"→  New leads (7d):     {len(new_leads)}",
        f"⏸  Stalled deals:      {len(stalled)}  (14d+ no activity)",
        "",
        "Top tasks today:",
    ]
    for t in tasks[:5]:
        lines.append(f"  • {t.get('Subject','—')}")
    if overdue:
        lines.append("\nOverdue (needs action):")
        for t in overdue[:3]:
            lines.append(f"  ⚠ {t.get('Subject','—')}  due {t.get('Due_Date','—')[:10]}")
    return "\n".join(lines)
