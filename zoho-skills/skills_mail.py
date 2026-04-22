"""
Zoho Mail skills for the Butler Button CSMO agent.
Uses Zoho Mail REST API (India DC — mail.zoho.in).

Required OAuth scope: ZohoMail.messages.ALL, ZohoMail.folders.ALL
"""

import os
import requests
from claude_agent import tool
from zoho_client import zoho

MAIL_BASE = "https://mail.zoho.in/api"
_ACCOUNT_ID: str | None = None


def _account_id() -> str:
    global _ACCOUNT_ID
    if _ACCOUNT_ID:
        return _ACCOUNT_ID
    r = requests.get(
        f"{MAIL_BASE}/accounts",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
    )
    r.raise_for_status()
    accounts = r.json().get("data", [])
    if not accounts:
        raise RuntimeError("No Zoho Mail accounts found for this token.")
    _ACCOUNT_ID = str(accounts[0]["accountId"])
    return _ACCOUNT_ID


def _mail_get(path: str, params: dict = None) -> dict:
    r = requests.get(
        f"{MAIL_BASE}/accounts/{_account_id()}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        params=params or {},
    )
    r.raise_for_status()
    return r.json()


def _mail_post(path: str, payload: dict) -> dict:
    r = requests.post(
        f"{MAIL_BASE}/accounts/{_account_id()}/{path}",
        headers={
            "Authorization": f"Zoho-oauthtoken {zoho.token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    r.raise_for_status()
    return r.json()


# ── Send & Draft ───────────────────────────────────────────────────────────────

@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    is_html: bool = False,
) -> str:
    """Send an email from the Butler Button Zoho Mail account.

    Args:
        to: Recipient email address (or comma-separated list).
        subject: Email subject line.
        body: Email body (plain text or HTML).
        cc: CC recipients, comma-separated (optional).
        bcc: BCC recipients, comma-separated (optional).
        is_html: Set True if body is HTML (default False — plain text).
    """
    payload: dict = {
        "fromAddress": os.environ.get("ZOHO_MAIL_FROM", ""),
        "toAddress": to,
        "subject": subject,
        "content": body,
        "mailFormat": "html" if is_html else "plaintext",
    }
    if cc:
        payload["ccAddress"] = cc
    if bcc:
        payload["bccAddress"] = bcc
    _mail_post("messages", payload)
    return f"Email sent to {to}  |  Subject: '{subject}'"


@tool
def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
) -> str:
    """Save an email as a draft for review before sending.

    Args:
        to: Intended recipient email.
        subject: Email subject.
        body: Email body (plain text).
        cc: CC recipients (optional).
    """
    payload: dict = {
        "fromAddress": os.environ.get("ZOHO_MAIL_FROM", ""),
        "toAddress": to,
        "subject": subject,
        "content": body,
        "mailFormat": "plaintext",
    }
    if cc:
        payload["ccAddress"] = cc
    result = _mail_post("drafts", payload)
    draft_id = result.get("data", {}).get("messageId", "—")
    return f"Draft saved  |  To: {to}  |  Subject: '{subject}'  |  Draft ID: {draft_id}"


@tool
def send_email_and_log_to_crm(
    contact_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send an email AND create a follow-up task in Zoho CRM linked to the contact.

    Args:
        contact_id: Zoho CRM Contact record ID to link the activity to.
        to_email: Recipient email address.
        subject: Email subject.
        body: Email body (plain text).
    """
    send_email(to=to_email, subject=subject, body=body)

    from datetime import date, timedelta
    from zoho_client import zoho as _zoho
    tomorrow = (date.today() + timedelta(days=3)).isoformat()
    _zoho.crm_post("Tasks", {"data": [{
        "Subject": f"Follow up: {subject}",
        "Due_Date": tomorrow,
        "Priority": "High",
        "Status": "Not Started",
        "Description": f"Email sent {date.today().isoformat()} — check for reply.",
        "What_Id": {"id": contact_id, "type": "Contacts"},
    }]})
    return (
        f"Email sent to {to_email} and follow-up task created in CRM "
        f"(due {tomorrow}) linked to contact {contact_id}."
    )


# ── Inbox & Search ─────────────────────────────────────────────────────────────

@tool
def get_recent_emails(count: int = 10, folder: str = "Inbox") -> str:
    """Return the most recent emails from a mailbox folder.

    Args:
        count: Number of emails to return (default 10, max 50).
        folder: Folder name (default 'Inbox').
    """
    data = _mail_get("messages", params={
        "limit": min(count, 50),
        "foldername": folder,
        "sortorder": "false",
    })
    messages = data.get("data", [])
    if not messages:
        return f"No messages in {folder}."
    lines = [f"Recent emails in {folder} ({len(messages)}):"]
    for m in messages:
        sender = m.get("fromAddress", "—")
        subj = m.get("subject", "(no subject)")
        date_str = m.get("receivedTime", "—")[:10] if m.get("receivedTime") else "—"
        unread = " [UNREAD]" if not m.get("isRead") else ""
        lines.append(f"  [{date_str}]{unread}  {sender}  |  {subj}")
    return "\n".join(lines)


@tool
def search_emails(query: str, folder: str = "Inbox", limit: int = 10) -> str:
    """Search Zoho Mail for emails matching a keyword or sender.

    Args:
        query: Search term (sender email, keyword, or subject fragment).
        folder: Folder to search (default 'Inbox'; use 'All' for all folders).
        limit: Max results to return (default 10).
    """
    data = _mail_get("messages", params={
        "searchKey": query,
        "foldername": folder if folder != "All" else None,
        "limit": min(limit, 50),
    })
    messages = data.get("data", [])
    if not messages:
        return f"No emails found matching '{query}'."
    lines = [f"Search results for '{query}' ({len(messages)}):"]
    for m in messages:
        date_str = m.get("receivedTime", "—")[:10] if m.get("receivedTime") else "—"
        lines.append(
            f"  [{date_str}]  From: {m.get('fromAddress','—')}  |  {m.get('subject','—')}"
        )
    return "\n".join(lines)


@tool
def get_unread_count() -> str:
    """Return unread email count across all mailbox folders."""
    data = _mail_get("folders")
    folders = data.get("data", [])
    total = 0
    lines = []
    for f in folders:
        unread = f.get("unreadCount", 0)
        if unread:
            lines.append(f"  {f.get('folderName','—')}: {unread} unread")
            total += unread
    if not total:
        return "Inbox zero. All caught up."
    return f"Unread emails: {total} total\n" + "\n".join(lines)


# ── Folders & Labels ───────────────────────────────────────────────────────────

@tool
def create_folder(folder_name: str, parent_folder: str = "") -> str:
    """Create a new mail folder in Zoho Mail.

    Args:
        folder_name: Name of the new folder.
        parent_folder: Optional parent folder name for nested organization.
    """
    payload: dict = {"folderName": folder_name}
    if parent_folder:
        payload["parentFolderName"] = parent_folder
    _mail_post("folders", payload)
    return f"Folder '{folder_name}' created."


@tool
def create_label(label_name: str, color: str = "#C9A84C") -> str:
    """Create a new label in Zoho Mail for email tagging.

    Args:
        label_name: Label display name.
        color: Hex color code for the label (default: Butler Button gold).
    """
    _mail_post("labels", {"labelName": label_name, "labelColor": color})
    return f"Label '{label_name}' created with color {color}."
