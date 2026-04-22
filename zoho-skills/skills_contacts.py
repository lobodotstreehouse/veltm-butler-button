"""Contact management skills for the Butler Button CSMO agent."""

from claude_agent import tool
from zoho_client import zoho


@tool
def search_contacts(query: str) -> str:
    """Search CRM contacts by name, email, or company.

    Args:
        query: Search string (name fragment, email, or company name).
    """
    data = zoho.crm_get("Contacts/search", params={
        "word": query,
        "fields": "Full_Name,Email,Phone,Account_Name,Lead_Source,Created_Time",
        "per_page": 20,
    })
    contacts = data.get("data", [])
    if not contacts:
        return f"No contacts found matching '{query}'."
    lines = [f"Contacts matching '{query}' ({len(contacts)}):"]
    for c in contacts:
        lines.append(
            f"  [{c['id']}] {c.get('Full_Name','—')}  |  {c.get('Email','—')}  "
            f"|  {c.get('Account_Name','—')}"
        )
    return "\n".join(lines)


@tool
def get_contact_history(contact_id: str) -> str:
    """Return full activity history for a CRM contact.

    Args:
        contact_id: Zoho CRM Contact record ID.
    """
    details = zoho.crm_get(f"Contacts/{contact_id}", params={
        "fields": "Full_Name,Email,Phone,Account_Name,Lead_Source,Description,Modified_Time"
    })
    contact = (details.get("data") or [{}])[0]
    name = contact.get("Full_Name", "Unknown")

    activities = zoho.crm_get(f"Contacts/{contact_id}/Activities", params={"per_page": 20})
    acts = activities.get("data", [])

    lines = [
        f"Contact: {name}  ({contact_id})",
        f"  Email: {contact.get('Email','—')}  |  Phone: {contact.get('Phone','—')}",
        f"  Company: {contact.get('Account_Name','—')}  |  Source: {contact.get('Lead_Source','—')}",
        f"  Last modified: {(contact.get('Modified_Time','—'))[:10]}",
        "",
        f"Activities ({len(acts)}):",
    ]
    for a in acts:
        lines.append(
            f"  [{a.get('Activity_Type','—')}] {a.get('Subject','—')}  {(a.get('Due_Date','—'))[:10]}"
        )
    return "\n".join(lines)


@tool
def create_contact(
    first_name: str,
    last_name: str,
    email: str = "",
    phone: str = "",
    account_name: str = "",
    lead_source: str = "Butler Button Website",
    description: str = "",
) -> str:
    """Create a new CRM contact.

    Args:
        first_name: First name.
        last_name: Last name.
        email: Email address.
        phone: Phone number.
        account_name: Company/account name.
        lead_source: How they found Butler Button.
        description: Notes about this contact.
    """
    payload = {
        "First_Name": first_name,
        "Last_Name": last_name,
        "Email": email,
        "Phone": phone,
        "Account_Name": {"name": account_name} if account_name else None,
        "Lead_Source": lead_source,
        "Description": description,
    }
    payload = {k: v for k, v in payload.items() if v}
    result = zoho.crm_post("Contacts", {"data": [payload]})
    record_id = (result.get("data") or [{}])[0].get("details", {}).get("id", "—")
    return f"Contact created: {first_name} {last_name}  ID: {record_id}"


@tool
def get_vip_clients() -> str:
    """Return contacts tagged as VIP or with deals over ₹5L."""
    data = zoho.crm_get("Contacts", params={
        "fields": "Full_Name,Email,Phone,Account_Name,Tag",
        "criteria": "Tag:equals:VIP",
        "per_page": 50,
    })
    contacts = data.get("data", [])
    if not contacts:
        return "No VIP-tagged contacts found."
    lines = [f"VIP clients ({len(contacts)}):"]
    for c in contacts:
        lines.append(f"  {c.get('Full_Name','—')}  |  {c.get('Email','—')}  |  {c.get('Account_Name','—')}")
    return "\n".join(lines)


@tool
def tag_contact(contact_id: str, tag: str) -> str:
    """Add a tag to a CRM contact for segmentation.

    Args:
        contact_id: Zoho CRM Contact record ID.
        tag: Tag label to apply (e.g. VIP, Prospect, Referral).
    """
    zoho.crm_post(f"Contacts/{contact_id}/actions/addtag", {"tags": [{"name": tag}]})
    return f"Tag '{tag}' added to contact {contact_id}."
