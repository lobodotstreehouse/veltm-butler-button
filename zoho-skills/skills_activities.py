"""Task, call, and meeting skills for the Butler Button CSMO agent."""

from datetime import date, timedelta
from claude_agent import tool
from zoho_client import zoho


@tool
def get_tasks_due_today() -> str:
    """Return all CRM tasks due today, sorted by priority."""
    today = date.today().isoformat()
    data = zoho.crm_get("Tasks", params={
        "fields": "Subject,Due_Date,Status,Priority,What_Id,Owner",
        "criteria": f"(Due_Date:equals:{today})and(Status:not_equal:Completed)",
        "sort_by": "Priority",
        "per_page": 50,
    })
    tasks = data.get("data", [])
    if not tasks:
        return "No tasks due today. Clear runway."
    lines = [f"Tasks due today ({len(tasks)}):"]
    for t in tasks:
        owner = (t.get("Owner") or {}).get("name", "—")
        related = (t.get("What_Id") or {}).get("name", "—")
        lines.append(
            f"  [{t.get('Priority','—')}] {t.get('Subject','—')}  |  {related}  |  Owner: {owner}"
        )
    return "\n".join(lines)


@tool
def get_overdue_tasks() -> str:
    """Return all open CRM tasks whose due date has passed."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data = zoho.crm_get("Tasks", params={
        "fields": "Subject,Due_Date,Status,Priority,What_Id,Owner",
        "criteria": f"(Due_Date:less_equal:{yesterday})and(Status:not_equal:Completed)",
        "sort_by": "Due_Date",
        "per_page": 50,
    })
    tasks = data.get("data", [])
    if not tasks:
        return "No overdue tasks."
    lines = [f"Overdue tasks ({len(tasks)}):"]
    for t in tasks:
        owner = (t.get("Owner") or {}).get("name", "—")
        lines.append(
            f"  [DUE {t.get('Due_Date','—')}] {t.get('Subject','—')}  Priority: {t.get('Priority','—')}  Owner: {owner}"
        )
    return "\n".join(lines)


@tool
def create_task(
    subject: str,
    due_date: str,
    related_to_id: str = "",
    related_to_type: str = "Contacts",
    priority: str = "High",
    description: str = "",
) -> str:
    """Create a follow-up task in Zoho CRM.

    Args:
        subject: Task title/subject.
        due_date: Due date in YYYY-MM-DD format.
        related_to_id: ID of the related Contact, Deal, or Lead.
        related_to_type: Module of the related record (Contacts, Deals, Leads).
        priority: High, Medium, or Low.
        description: Additional notes.
    """
    payload: dict = {
        "Subject": subject,
        "Due_Date": due_date,
        "Priority": priority,
        "Status": "Not Started",
        "Description": description,
    }
    if related_to_id:
        payload["What_Id"] = {"id": related_to_id, "type": related_to_type}
    result = zoho.crm_post("Tasks", {"data": [payload]})
    task_id = (result.get("data") or [{}])[0].get("details", {}).get("id", "—")
    return f"Task created: '{subject}'  due {due_date}  ID: {task_id}"


@tool
def log_call(
    subject: str,
    contact_id: str,
    duration_minutes: int,
    call_result: str,
    description: str = "",
) -> str:
    """Log a completed call to a CRM contact.

    Args:
        subject: Call subject (e.g. 'Discovery call — Ritz inquiry').
        contact_id: Zoho CRM Contact record ID.
        duration_minutes: Duration of the call in minutes.
        call_result: Outcome (e.g. Interested, Callback, Not Interested).
        description: Call notes/summary.
    """
    payload = {
        "Subject": subject,
        "Call_Type": "Outbound",
        "Call_Duration": str(duration_minutes),
        "Call_Result": call_result,
        "Description": description,
        "Who_Id": {"id": contact_id, "type": "Contacts"},
        "Call_Start_Time": f"{date.today().isoformat()}T09:00:00+05:30",
    }
    result = zoho.crm_post("Calls", {"data": [payload]})
    call_id = (result.get("data") or [{}])[0].get("details", {}).get("id", "—")
    return f"Call logged: '{subject}'  {duration_minutes}min  Result: {call_result}  ID: {call_id}"


@tool
def schedule_meeting(
    subject: str,
    contact_id: str,
    meeting_date: str,
    duration_minutes: int = 60,
    agenda: str = "",
) -> str:
    """Schedule a meeting with a CRM contact.

    Args:
        subject: Meeting title.
        contact_id: Zoho CRM Contact record ID.
        meeting_date: Date in YYYY-MM-DD format.
        duration_minutes: Duration in minutes (default 60).
        agenda: Meeting agenda/notes.
    """
    payload = {
        "Subject": subject,
        "From_Time": f"{meeting_date}T10:00:00+05:30",
        "To_Time": f"{meeting_date}T{10 + duration_minutes // 60:02d}:{duration_minutes % 60:02d}:00+05:30",
        "Event_Title": subject,
        "Description": agenda,
        "Participants": [{"participant": contact_id, "type": "contact"}],
    }
    result = zoho.crm_post("Events", {"data": [payload]})
    event_id = (result.get("data") or [{}])[0].get("details", {}).get("id", "—")
    return f"Meeting scheduled: '{subject}'  on {meeting_date}  ID: {event_id}"
