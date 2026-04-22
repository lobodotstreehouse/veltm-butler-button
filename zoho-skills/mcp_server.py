#!/usr/bin/env python3
"""Butler Button CSMO — MCP skill server for Claude Desktop.

Exposes all 79 public skill functions across 13 modules as FastMCP tools.
Run via the venv python:
  /Users/openclaw/veltm-butler-button/zoho-skills/.mcp-venv/bin/python mcp_server.py
"""

import os
import sys
import types

# ── Path setup ────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
os.chdir(_DIR)

# ── Stub out claude_agent so skill files that use @tool can be imported ───────
# The @tool decorator is a no-op in MCP context — FastMCP provides its own.
_claude_agent_stub = types.ModuleType("claude_agent")
_claude_agent_stub.tool = lambda f: f           # passthrough decorator
_claude_agent_stub.ClaudeSDKClient = object
_claude_agent_stub.ClaudeAgentOptions = object
sys.modules["claude_agent"] = _claude_agent_stub

# ── Load env vars from .env ───────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, ".env"), override=True)

# ── FastMCP server ────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Butler Button Skills")


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE & REVENUE  (skills_pipeline.py — 6 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_pipeline_summary() -> str:
    """Return open deal count and total value grouped by pipeline stage.

    Queries all non-closed deals from Zoho CRM and aggregates count and
    total value per stage, sorted by stage value descending.
    """
    from skills_pipeline import get_pipeline_summary as _f
    return _f()


@mcp.tool()
def get_revenue_forecast(days: int = 30) -> str:
    """Return weighted revenue forecast for deals closing within N days.

    Args:
        days: Lookahead window in days (default 30).
    """
    from skills_pipeline import get_revenue_forecast as _f
    return _f(days)


@mcp.tool()
def get_deals_closing_soon(days: int = 7) -> str:
    """List deals closing within N days that are not yet won or lost.

    Args:
        days: Days ahead to look (default 7).
    """
    from skills_pipeline import get_deals_closing_soon as _f
    return _f(days)


@mcp.tool()
def get_stalled_deals(inactive_days: int = 14) -> str:
    """List open deals with no CRM activity in the past N days.

    Args:
        inactive_days: Inactivity threshold in days (default 14).
    """
    from skills_pipeline import get_stalled_deals as _f
    return _f(inactive_days)


@mcp.tool()
def get_won_deals_mtd() -> str:
    """Return deals won month-to-date with total revenue."""
    from skills_pipeline import get_won_deals_mtd as _f
    return _f()


@mcp.tool()
def update_deal_stage(deal_id: str, new_stage: str) -> str:
    """Move a CRM deal to a new pipeline stage.

    Args:
        deal_id: Zoho CRM Deal record ID.
        new_stage: Target stage name (must match CRM picklist exactly).
    """
    from skills_pipeline import update_deal_stage as _f
    return _f(deal_id, new_stage)


# ═══════════════════════════════════════════════════════════════════════════════
# LEAD MANAGEMENT  (skills_leads.py — 4 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_new_leads(days: int = 7) -> str:
    """Return leads created in the past N days from Zoho CRM.

    Args:
        days: Lookback window in days (default 7).
    """
    from skills_leads import get_new_leads as _f
    return _f(days)


@mcp.tool()
def get_lead_source_breakdown() -> str:
    """Return count of leads by source channel for the current month."""
    from skills_leads import get_lead_source_breakdown as _f
    return _f()


@mcp.tool()
def convert_lead(lead_id: str, account_name: str = None) -> str:
    """Convert a qualified lead to Contact and Deal in Zoho CRM.

    Args:
        lead_id: Zoho CRM Lead record ID.
        account_name: Optional account/company name for the new record.
    """
    from skills_leads import convert_lead as _f
    return _f(lead_id, account_name)


@mcp.tool()
def qualify_lead(lead_id: str, rating: str, status: str, notes: str = "") -> str:
    """Update lead qualification fields: rating, status, and notes.

    Args:
        lead_id: Zoho CRM Lead record ID.
        rating: Rating value — Hot, Warm, or Cold.
        status: Lead status picklist value.
        notes: Optional qualification notes appended to Description.
    """
    from skills_leads import qualify_lead as _f
    return _f(lead_id, rating, status, notes)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTACT MANAGEMENT  (skills_contacts.py — 5 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def search_contacts(query: str) -> str:
    """Search CRM contacts by name, email, or company.

    Args:
        query: Search string (name fragment, email, or company name).
    """
    from skills_contacts import search_contacts as _f
    return _f(query)


@mcp.tool()
def get_contact_history(contact_id: str) -> str:
    """Return full activity history for a CRM contact.

    Args:
        contact_id: Zoho CRM Contact record ID.
    """
    from skills_contacts import get_contact_history as _f
    return _f(contact_id)


@mcp.tool()
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
        lead_source: How they found Butler Button (default: Butler Button Website).
        description: Notes about this contact.
    """
    from skills_contacts import create_contact as _f
    return _f(first_name, last_name, email, phone, account_name, lead_source, description)


@mcp.tool()
def get_vip_clients() -> str:
    """Return contacts tagged as VIP or with high-value deals."""
    from skills_contacts import get_vip_clients as _f
    return _f()


@mcp.tool()
def tag_contact(contact_id: str, tag: str) -> str:
    """Add a tag to a CRM contact for segmentation.

    Args:
        contact_id: Zoho CRM Contact record ID.
        tag: Tag label to apply (e.g. VIP, Prospect, Referral).
    """
    from skills_contacts import tag_contact as _f
    return _f(contact_id, tag)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITIES & FOLLOW-UP  (skills_activities.py — 5 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_tasks_due_today() -> str:
    """Return all CRM tasks due today, sorted by priority."""
    from skills_activities import get_tasks_due_today as _f
    return _f()


@mcp.tool()
def get_overdue_tasks() -> str:
    """Return all open CRM tasks whose due date has passed."""
    from skills_activities import get_overdue_tasks as _f
    return _f()


@mcp.tool()
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
    from skills_activities import create_task as _f
    return _f(subject, due_date, related_to_id, related_to_type, priority, description)


@mcp.tool()
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
    from skills_activities import log_call as _f
    return _f(subject, contact_id, duration_minutes, call_result, description)


@mcp.tool()
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
    from skills_activities import schedule_meeting as _f
    return _f(subject, contact_id, meeting_date, duration_minutes, agenda)


# ═══════════════════════════════════════════════════════════════════════════════
# BUTLER BUTTON CONCIERGE  (skills_butler_button.py — 5 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_active_requests() -> str:
    """Return all open Butler Button concierge service requests."""
    from skills_butler_button import get_active_requests as _f
    return _f()


@mcp.tool()
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
        service_type: Type of service — Hotel, Villa, Flight, Experience, or Itinerary.
        destination: Destination city or region.
        travel_date: Approximate travel date YYYY-MM-DD.
        budget_usd: Client's stated budget in USD.
        notes: Intake notes from conversation or form.
    """
    from skills_butler_button import create_service_request as _f
    return _f(client_name, service_type, destination, travel_date, budget_usd, notes)


@mcp.tool()
def get_upcoming_trips(days: int = 90) -> str:
    """Return confirmed trips departing in the next N days.

    Args:
        days: Lookahead window in days (default 90).
    """
    from skills_butler_button import get_upcoming_trips as _f
    return _f(days)


@mcp.tool()
def get_client_preferences(contact_id: str) -> str:
    """Return a client's stored concierge preferences and travel history.

    Args:
        contact_id: Zoho CRM Contact record ID.
    """
    from skills_butler_button import get_client_preferences as _f
    return _f(contact_id)


@mcp.tool()
def get_daily_csmo_brief() -> str:
    """Return a full CSMO morning brief: tasks, pipeline, new leads, stalled deals."""
    from skills_butler_button import get_daily_csmo_brief as _f
    return _f()


# ═══════════════════════════════════════════════════════════════════════════════
# ZOHO MAIL  (skills_mail.py — 8 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
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
        is_html: Set True if body is HTML (default False).
    """
    from skills_mail import send_email as _f
    return _f(to, subject, body, cc, bcc, is_html)


@mcp.tool()
def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
) -> str:
    """Save an email as a draft in Zoho Mail for review before sending.

    Args:
        to: Intended recipient email.
        subject: Email subject.
        body: Email body (plain text).
        cc: CC recipients (optional).
    """
    from skills_mail import create_draft as _f
    return _f(to, subject, body, cc)


@mcp.tool()
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
    from skills_mail import send_email_and_log_to_crm as _f
    return _f(contact_id, to_email, subject, body)


@mcp.tool()
def get_recent_emails(count: int = 10, folder: str = "Inbox") -> str:
    """Return the most recent emails from a Zoho Mail folder.

    Args:
        count: Number of emails to return (default 10, max 50).
        folder: Folder name (default 'Inbox').
    """
    from skills_mail import get_recent_emails as _f
    return _f(count, folder)


@mcp.tool()
def search_emails(query: str, folder: str = "Inbox", limit: int = 10) -> str:
    """Search Zoho Mail for emails matching a keyword or sender.

    Args:
        query: Search term (sender email, keyword, or subject fragment).
        folder: Folder to search (default 'Inbox'; use 'All' for all folders).
        limit: Max results to return (default 10).
    """
    from skills_mail import search_emails as _f
    return _f(query, folder, limit)


@mcp.tool()
def get_unread_count() -> str:
    """Return unread email count across all Zoho Mail folders."""
    from skills_mail import get_unread_count as _f
    return _f()


@mcp.tool()
def create_folder(folder_name: str, parent_folder: str = "") -> str:
    """Create a new mail folder in Zoho Mail.

    Args:
        folder_name: Name of the new folder.
        parent_folder: Optional parent folder name for nested organization.
    """
    from skills_mail import create_folder as _f
    return _f(folder_name, parent_folder)


@mcp.tool()
def create_label(label_name: str, color: str = "#C9A84C") -> str:
    """Create a new label in Zoho Mail for email tagging.

    Args:
        label_name: Label display name.
        color: Hex color code for the label (default: Butler Button gold #C9A84C).
    """
    from skills_mail import create_label as _f
    return _f(label_name, color)


# ═══════════════════════════════════════════════════════════════════════════════
# ZOHO CLIQ  (skills_cliq.py — 6 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
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
    from skills_cliq import send_cliq_channel_message as _f
    return _f(channel_name, message, as_bot, bot_name)


@mcp.tool()
def send_cliq_direct_message(
    recipient_email: str,
    message: str,
) -> str:
    """Send a direct message to a Zoho Cliq user.

    Args:
        recipient_email: Zoho Cliq user's email address.
        message: Message text.
    """
    from skills_cliq import send_cliq_direct_message as _f
    return _f(recipient_email, message)


@mcp.tool()
def broadcast_bot_message(
    bot_unique_name: str,
    message: str,
) -> str:
    """Broadcast a message to all subscribers of a Zoho Cliq bot.

    Args:
        bot_unique_name: The bot's unique name in Cliq (set during bot creation).
        message: Broadcast message text.
    """
    from skills_cliq import broadcast_bot_message as _f
    return _f(bot_unique_name, message)


@mcp.tool()
def alert_deal_won(
    deal_name: str,
    amount_usd: float,
    client_name: str,
    channel_name: str = "sales-pipeline",
) -> str:
    """Post a deal-won celebration alert to the Cliq sales channel.

    Args:
        deal_name: Name of the won deal.
        amount_usd: Deal value in USD.
        client_name: Client/account name.
        channel_name: Target Cliq channel (default 'sales-pipeline').
    """
    from skills_cliq import alert_deal_won as _f
    return _f(deal_name, amount_usd, client_name, channel_name)


@mcp.tool()
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
    from skills_cliq import alert_new_hot_lead as _f
    return _f(lead_name, source, contact_email, channel_name)


@mcp.tool()
def post_daily_pipeline_to_cliq(
    channel_name: str = "csmo-daily",
) -> str:
    """Pull pipeline summary from Zoho CRM and post it to a Cliq channel.

    Args:
        channel_name: Target Cliq channel for the brief (default 'csmo-daily').
    """
    from skills_cliq import post_daily_pipeline_to_cliq as _f
    return _f(channel_name)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION & FLOW  (skills_automation.py — 6 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def trigger_flow_webhook(webhook_url: str, payload: dict) -> str:
    """Trigger a Zoho Flow via its webhook URL with a custom JSON payload.

    Useful for firing automations from the agent — e.g. send onboarding email,
    generate itinerary PDF, or sync to an external system.

    Args:
        webhook_url: The Zoho Flow webhook URL (from Flow > Connections > Webhook).
        payload: Dictionary of data to send as JSON body.
    """
    from skills_automation import trigger_flow_webhook as _f
    return _f(webhook_url, payload)


@mcp.tool()
def list_active_flows() -> str:
    """List all active Zoho Flow automations in this Zoho One account."""
    from skills_automation import list_active_flows as _f
    return _f()


@mcp.tool()
def get_flow_execution_history(flow_id: str, limit: int = 10) -> str:
    """Return recent execution history for a Zoho Flow.

    Args:
        flow_id: Numeric Flow ID (from list_active_flows).
        limit: Number of executions to return (default 10).
    """
    from skills_automation import get_flow_execution_history as _f
    return _f(flow_id, limit)


@mcp.tool()
def list_crm_workflow_rules() -> str:
    """List all active workflow rules configured in Zoho CRM for the Deals module."""
    from skills_automation import list_crm_workflow_rules as _f
    return _f()


@mcp.tool()
def run_end_of_day_report(cliq_channel: str = "csmo-daily") -> str:
    """Generate and post a full end-of-day CSMO report to Zoho Cliq.

    Compiles MTD revenue, pipeline snapshot, new leads, and overdue tasks,
    then posts the full report to the specified Cliq channel.

    Args:
        cliq_channel: Cliq channel to receive the report (default 'csmo-daily').
    """
    from skills_automation import run_end_of_day_report as _f
    return _f(cliq_channel)


@mcp.tool()
def auto_follow_up_stalled_deals(
    inactive_days: int = 14,
    cliq_channel: str = "sales-pipeline",
) -> str:
    """Find stalled deals, create follow-up tasks, and alert the Cliq channel.

    Combines pipeline analysis, task creation, and Cliq notification in one command.

    Args:
        inactive_days: Inactivity threshold in days (default 14).
        cliq_channel: Cliq channel for alert (default 'sales-pipeline').
    """
    from skills_automation import auto_follow_up_stalled_deals as _f
    return _f(inactive_days, cliq_channel)


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL CONTENT AI  (skills_social.py — 13 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def generate_post(platform: str, topic: str, cta: str = "") -> dict:
    """Generate a single platform-native post via Claude AI.

    Args:
        platform: instagram | linkedin | x | facebook
        topic: What the post is about (angle, hook, story).
        cta: Optional call-to-action to include (e.g. 'DM us to start planning').
    """
    from skills_social import generate_post as _f
    return _f(platform, topic, cta)


@mcp.tool()
def generate_multi_platform(topic: str, platforms: list = None, cta: str = "") -> dict:
    """Generate native posts for multiple platforms from one topic using Claude AI.

    Args:
        topic: The angle or story to communicate.
        platforms: List of platforms (default: instagram, linkedin, x).
        cta: Optional CTA for all platforms.
    """
    from skills_social import generate_multi_platform as _f
    return _f(topic, platforms, cta)


@mcp.tool()
def repurpose_content(source_content: str, target_platforms: list = None) -> dict:
    """Turn a blog post, email, or long-form piece into platform-native posts.

    Args:
        source_content: The full text to repurpose (article, newsletter, etc.).
        target_platforms: Platforms to create for (default: instagram, linkedin, x).
    """
    from skills_social import repurpose_content as _f
    return _f(source_content, target_platforms)


@mcp.tool()
def generate_carousel_copy(topic: str, num_slides: int = 6) -> dict:
    """Generate slide-by-slide copy for an Instagram carousel or LinkedIn document post.

    Args:
        topic: The theme or subject of the carousel.
        num_slides: Number of slides (default 6: cover + content + CTA).
    """
    from skills_social import generate_carousel_copy as _f
    return _f(topic, num_slides)


@mcp.tool()
def generate_story_copy(topic: str, has_link: bool = True) -> dict:
    """Generate Instagram/Facebook Story copy: hook + 3 frames + swipe-up CTA.

    Args:
        topic: Story angle (e.g. 'behind the scenes planning a Maldives honeymoon').
        has_link: Whether to include a swipe-up / link sticker CTA (default True).
    """
    from skills_social import generate_story_copy as _f
    return _f(topic, has_link)


@mcp.tool()
def generate_hashtag_set(niche: str, post_content: str = "") -> dict:
    """Research and curate a 3-tier hashtag set for an Instagram post.

    Returns broad (1M+ posts), niche (50k-500k), and branded hashtag lists.

    Args:
        niche: Core niche (e.g. 'luxury travel India', 'honeymoon travel').
        post_content: Optional post text to tailor hashtags to.
    """
    from skills_social import generate_hashtag_set as _f
    return _f(niche, post_content)


@mcp.tool()
def publish_post(platforms: list, content: str, scheduled_time: str = None) -> dict:
    """Publish content to one or more social platforms.

    Routes to the right API: LinkedIn (UGC Posts), Facebook (Graph API),
    Instagram (Graph API), or Ayrshare for other platforms.

    Args:
        platforms: List of platforms — instagram | linkedin | linkedin_company | x | facebook.
        content: Post copy.
        scheduled_time: ISO 8601 datetime string to schedule; None = post immediately.
    """
    from skills_social import publish_post as _f
    return _f(platforms, content, scheduled_time)


@mcp.tool()
def create_content_calendar(
    theme: str, start_date: str = None, num_weeks: int = 4
) -> dict:
    """Generate a 4-week social content calendar and save each post as a CRM Task.

    Args:
        theme: Overarching campaign theme (e.g. 'honeymoon season', 'monsoon escapes').
        start_date: ISO date string (default: today).
        num_weeks: Number of weeks to plan (default 4).
    """
    from skills_social import create_content_calendar as _f
    return _f(theme, start_date, num_weeks)


@mcp.tool()
def get_calendar_week(week_offset: int = 0) -> dict:
    """Pull this week's social content tasks from Zoho CRM.

    Args:
        week_offset: 0 = this week, 1 = next week, -1 = last week.
    """
    from skills_social import get_calendar_week as _f
    return _f(week_offset)


@mcp.tool()
def log_post_performance(
    platform: str,
    post_description: str,
    reach: int,
    likes: int,
    comments: int,
    shares: int = 0,
    saves: int = 0,
) -> dict:
    """Record post performance metrics in CRM for benchmarking.

    Args:
        platform: Platform the post was on (instagram, linkedin, x, facebook).
        post_description: Short description of the post for identification.
        reach: Number of accounts reached.
        likes: Like count.
        comments: Comment count.
        shares: Share/repost count (default 0).
        saves: Save/bookmark count (default 0).
    """
    from skills_social import log_post_performance as _f
    return _f(platform, post_description, reach, likes, comments, shares, saves)


@mcp.tool()
def generate_performance_brief(platform_stats: dict) -> str:
    """Generate a Claude-written weekly social performance analysis.

    Args:
        platform_stats: Dict of platform to metrics dict.
          e.g. {"instagram": {"reach": 5200, "followers_gained": 14, "top_post": "Maldives reel"}}
    """
    from skills_social import generate_performance_brief as _f
    return _f(platform_stats)


@mcp.tool()
def generate_reply(comment_text: str, platform: str, post_topic: str = "") -> str:
    """Draft a brand-voice reply to a comment or DM using Claude AI.

    Args:
        comment_text: The comment or message to respond to.
        platform: Platform context (affects tone — instagram, linkedin, x, facebook).
        post_topic: What the original post was about (for context).
    """
    from skills_social import generate_reply as _f
    return _f(comment_text, platform, post_topic)


@mcp.tool()
def generate_campaign_burst(
    campaign_name: str,
    offer: str,
    launch_date: str,
    platforms: list = None,
) -> dict:
    """Generate a full launch campaign: 5 posts across platforms over 2 weeks.

    Posts follow a sequence: Tease → Announce → Proof → Urgency → Close.
    Each post is saved as a CRM Task with the generated copy.

    Args:
        campaign_name: Name of the campaign (e.g. 'Monsoon Maldives Package').
        offer: What's being promoted (e.g. '5-night Maldives overwater villa, all-inclusive').
        launch_date: ISO date string for the official launch day.
        platforms: Platforms to create content for (default: instagram, linkedin, x).
    """
    from skills_social import generate_campaign_burst as _f
    return _f(campaign_name, offer, launch_date, platforms)


# ═══════════════════════════════════════════════════════════════════════════════
# FACEBOOK PAGE  (skills_facebook.py — 4 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def fb_post_to_page(
    content: str, link: str = None, scheduled_unix: int = None
) -> dict:
    """Publish or schedule a post on the VELTM TOURS Facebook Page via Graph API.

    Args:
        content: Post message text.
        link: Optional URL to attach as a link preview.
        scheduled_unix: Unix timestamp (UTC) to schedule the post (10 min to 30 days ahead).
    """
    from skills_facebook import post_to_page as _f
    return _f(content, link, scheduled_unix)


@mcp.tool()
def fb_get_page_token(user_access_token: str = None) -> str:
    """Exchange a short-lived user token for a long-lived Facebook page access token.

    Args:
        user_access_token: A short-lived user token with pages_manage_posts scope.
                           If omitted, uses FACEBOOK_PAGE_ACCESS_TOKEN from env.
    """
    from skills_facebook import get_page_token as _f
    return _f(user_access_token)


@mcp.tool()
def fb_get_recent_posts(limit: int = 10) -> list:
    """Fetch recent posts from the VELTM TOURS Facebook Page with engagement metrics.

    Args:
        limit: Number of posts to return (default 10, max 100).
    """
    from skills_facebook import get_recent_posts as _f
    return _f(limit)


@mcp.tool()
def fb_setup_instructions() -> str:
    """Return step-by-step instructions to obtain Facebook Graph API credentials for VELTM TOURS."""
    from skills_facebook import setup_instructions as _f
    return _f()


# ═══════════════════════════════════════════════════════════════════════════════
# INSTAGRAM  (skills_instagram.py — 6 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def ig_post_image(image_url: str, caption: str) -> dict:
    """Post a feed image to @veltmtours via the two-step Instagram Graph API container flow.

    The image must be at a publicly accessible HTTPS URL. If no public URL is
    available, use ig_post_caption_only() instead.

    Args:
        image_url: Publicly accessible HTTPS URL of the image (JPEG or PNG).
        caption: Post caption including hashtags.
    """
    from skills_instagram import post_image as _f
    return _f(image_url, caption)


@mcp.tool()
def ig_post_reel(video_url: str, caption: str) -> dict:
    """Post a Reel (video) to @veltmtours via the Instagram Graph API container flow.

    The video must be at a publicly accessible HTTPS URL.
    Supported: MP4 H.264/AAC, min 3s, max 15min, 9:16 aspect ratio recommended.

    Args:
        video_url: Publicly accessible HTTPS URL of the video file.
        caption: Reel caption including hashtags.
    """
    from skills_instagram import post_reel as _f
    return _f(video_url, caption)


@mcp.tool()
def ig_post_caption_only(caption: str) -> dict:
    """Save an Instagram caption as a CRM Task when no image URL is available.

    Creates a Zoho CRM Task with status 'Ready to post' so the caption can be
    copy-pasted when the image is uploaded manually via the Instagram app.

    Args:
        caption: The full post caption (with hashtags) to save.
    """
    from skills_instagram import post_caption_only as _f
    return _f(caption)


@mcp.tool()
def ig_get_account_insights(period: str = "day") -> dict:
    """Fetch reach, impressions, and follower_count for @veltmtours.

    Args:
        period: 'day' | 'week' | 'days_28' | 'month' | 'lifetime'
    """
    from skills_instagram import get_account_insights as _f
    return _f(period)


@mcp.tool()
def ig_get_recent_media(limit: int = 10) -> list:
    """Return recent @veltmtours posts with engagement metrics.

    Args:
        limit: Number of recent posts to return (default 10, max 100).
    """
    from skills_instagram import get_recent_media as _f
    return _f(limit)


@mcp.tool()
def ig_setup_instructions() -> str:
    """Return step-by-step instructions for connecting @veltmtours to the Instagram Graph API."""
    from skills_instagram import setup_instructions as _f
    return _f()


# ═══════════════════════════════════════════════════════════════════════════════
# LINKEDIN COMPANY PAGE  (skills_linkedin_company.py — 5 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def li_company_post_text(content: str) -> dict:
    """Post plain text as the VELTM LinkedIn organization page.

    Args:
        content: The text body of the post (max ~3000 chars recommended by LinkedIn).
    """
    from skills_linkedin_company import post_text as _f
    return _f(content)


@mcp.tool()
def li_company_post_with_article(
    content: str,
    article_url: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Post with a link/article share as the VELTM LinkedIn company page.

    Args:
        content: Commentary text shown above the link card.
        article_url: The URL to share (must be publicly accessible for LinkedIn to card it).
        title: Optional override for the link card title.
        description: Optional override for the link card description.
    """
    from skills_linkedin_company import post_with_article as _f
    return _f(content, article_url, title, description)


@mcp.tool()
def li_company_get_org_followers() -> int:
    """Fetch the current follower count for the VELTM LinkedIn organization page."""
    from skills_linkedin_company import get_org_followers as _f
    return _f()


@mcp.tool()
def li_company_get_recent_posts(count: int = 10) -> list:
    """Fetch recent posts made by the VELTM LinkedIn company page.

    Args:
        count: Number of posts to retrieve (1-50).
    """
    from skills_linkedin_company import get_recent_posts as _f
    return _f(count)


@mcp.tool()
def li_company_setup_instructions() -> str:
    """Return step-by-step instructions to configure the LinkedIn company posting skill."""
    from skills_linkedin_company import setup_instructions as _f
    return _f()


# ═══════════════════════════════════════════════════════════════════════════════
# LINKEDIN PERSONAL  (skills_linkedin_personal.py — 5 tools)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def li_personal_get_profile_id() -> str:
    """Fetch and cache the authenticated LinkedIn person URN (Carl Remi Beauregard).

    Calls GET /v2/userinfo and writes LINKEDIN_PERSON_ID to .env for future use.
    """
    from skills_linkedin_personal import get_profile_id as _f
    return _f()


@mcp.tool()
def li_personal_post_text(content: str) -> dict:
    """Post a plain-text update to Carl Remi Beauregard's LinkedIn personal profile.

    Args:
        content: The post body text (LinkedIn recommends under 3,000 characters).
    """
    from skills_linkedin_personal import post_text as _f
    return _f(content)


@mcp.tool()
def li_personal_post_with_article(
    content: str,
    article_url: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Post a LinkedIn personal update that includes an article or URL share.

    Args:
        content: Commentary text above the link preview.
        article_url: Fully qualified URL to share (must start with https://).
        title: Optional article headline for the link preview card.
        description: Optional article description for the link preview card.
    """
    from skills_linkedin_personal import post_with_article as _f
    return _f(content, article_url, title, description)


@mcp.tool()
def li_personal_get_recent_posts(count: int = 10) -> list:
    """Fetch the most recent UGC posts authored by Carl Remi Beauregard.

    Args:
        count: Number of posts to return (max 100 per LinkedIn page).
    """
    from skills_linkedin_personal import get_recent_posts as _f
    return _f(count)


@mcp.tool()
def li_personal_setup_instructions() -> str:
    """Return step-by-step instructions for creating a LinkedIn app and personal access token."""
    from skills_linkedin_personal import setup_instructions as _f
    return _f()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
