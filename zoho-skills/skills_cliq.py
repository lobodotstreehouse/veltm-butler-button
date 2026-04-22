"""
Zoho Cliq skills for the Butler Button CSMO agent.
Used for team alerts, deal notifications, and concierge status updates.

Required OAuth scope: ZohoCliq.channels.ALL, ZohoCliq.messages.ALL
"""

import os
import requests
from claude_agent import tool
from zoho_client import zoho

CLIQ_BASE = "https://cliq.zoho.in/api/v2"


def _cliq_post(path: str, payload: dict) -> dict:
    r = requests.post(
        f"{CLIQ_BASE}/{path}",
        headers={
            "Authorization": f"Zoho-oauthtoken {zoho.token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    r.raise_for_status()
    return r.json()


def _cliq_get(path: str, params: dict = None) -> dict:
    r = requests.get(
        f"{CLIQ_BASE}/{path}",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}"},
        params=params or {},
    )
    r.raise_for_status()
    return r.json()


# ── Channel Messaging ──────────────────────────────────────────────────────────

@tool
def send_cliq_channel_message(
    channel_name: str,
    message: str,
    as_bot: bool = False,
    bot_name: str = "Butler Bot",
) -> str:
    """Send a message to a Zoho Cliq channel.

    Args:
        channel_name: Cliq channel unique name (e.g. 'sales-pipeline').
        message: Message text to send.
        as_bot: If True, send as a bot (requires bot configured in Cliq).
        bot_name: Bot display name if as_bot is True.
    """
    payload: dict = {"text": message}
    if as_bot:
        payload["bot"] = {"name": bot_name}
    _cliq_post(f"channels/{channel_name}/message", payload)
    return f"Message sent to #{channel_name}."


@tool
def send_cliq_direct_message(
    recipient_email: str,
    message: str,
) -> str:
    """Send a direct message to a Zoho Cliq user.

    Args:
        recipient_email: Zoho Cliq user's email address.
        message: Message text.
    """
    _cliq_post("dm", {"email": recipient_email, "text": message})
    return f"Direct message sent to {recipient_email}."


@tool
def broadcast_bot_message(
    bot_unique_name: str,
    message: str,
) -> str:
    """Broadcast a message to all subscribers of a Zoho Cliq bot.

    Args:
        bot_unique_name: The bot's unique name in Cliq (set during bot creation).
        message: Broadcast message text.
    """
    _cliq_post(f"bots/{bot_unique_name}/message", {"text": message})
    return f"Broadcast sent to all subscribers of bot '{bot_unique_name}'."


# ── CSMO-Specific Cliq Alerts ──────────────────────────────────────────────────

@tool
def alert_deal_won(
    deal_name: str,
    amount_inr: float,
    client_name: str,
    channel_name: str = "sales-pipeline",
) -> str:
    """Post a deal-won celebration alert to the Cliq sales channel.

    Args:
        deal_name: Name of the won deal.
        amount_inr: Deal value in INR.
        client_name: Client/account name.
        channel_name: Target Cliq channel (default 'sales-pipeline').
    """
    msg = (
        f"DEAL WON  |  {deal_name}\n"
        f"Client: {client_name}  |  Value: Rs.{amount_inr:,.0f}\n"
        f"Great work — log the win in CRM and schedule onboarding."
    )
    _cliq_post(f"channels/{channel_name}/message", {"text": msg})
    return f"Deal-won alert posted to #{channel_name} for '{deal_name}'."


@tool
def alert_new_hot_lead(
    lead_name: str,
    source: str,
    contact_email: str,
    channel_name: str = "leads",
) -> str:
    """Post a hot-lead alert to the Cliq leads channel.

    Args:
        lead_name: Full name of the lead.
        source: Lead source (e.g. Website, Referral, Instagram).
        contact_email: Lead's email address.
        channel_name: Target Cliq channel (default 'leads').
    """
    msg = (
        f"HOT LEAD  |  {lead_name}\n"
        f"Source: {source}  |  Email: {contact_email}\n"
        f"Action needed: qualify and respond within 2 hours."
    )
    _cliq_post(f"channels/{channel_name}/message", {"text": msg})
    return f"Hot-lead alert posted to #{channel_name} for '{lead_name}'."


@tool
def post_daily_pipeline_to_cliq(
    channel_name: str = "csmo-daily",
) -> str:
    """Pull pipeline summary from Zoho CRM and post it to a Cliq channel.

    Args:
        channel_name: Target Cliq channel for the brief (default 'csmo-daily').
    """
    from skills_pipeline import get_pipeline_summary, get_stalled_deals
    from datetime import date

    summary = get_pipeline_summary()
    stalled = get_stalled_deals(14)
    msg = f"CSMO Pipeline Brief — {date.today().isoformat()}\n\n{summary}\n\n{stalled}"
    _cliq_post(f"channels/{channel_name}/message", {"text": msg})
    return f"Pipeline brief posted to #{channel_name}."
