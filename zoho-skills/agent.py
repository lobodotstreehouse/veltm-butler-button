"""
Butler Button CSMO Agent
Run:  python agent.py
Requires: .env with ANTHROPIC_API_KEY, ZOHO_CLIENT_ID,
          ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN, ZOHO_MAIL_FROM
"""

import asyncio
from claude_agent import ClaudeSDKClient, ClaudeAgentOptions

from skills_pipeline import (
    get_pipeline_summary, get_revenue_forecast, get_deals_closing_soon,
    get_stalled_deals, get_won_deals_mtd, update_deal_stage,
)
from skills_leads import (
    get_new_leads, get_lead_source_breakdown, convert_lead, qualify_lead,
)
from skills_contacts import (
    search_contacts, get_contact_history, create_contact,
    get_vip_clients, tag_contact,
)
from skills_activities import (
    get_tasks_due_today, get_overdue_tasks, create_task,
    log_call, schedule_meeting,
)
from skills_butler_button import (
    get_active_requests, create_service_request,
    get_upcoming_trips, get_client_preferences, get_daily_csmo_brief,
)
from skills_mail import (
    send_email, create_draft, send_email_and_log_to_crm,
    get_recent_emails, search_emails, get_unread_count,
    create_folder, create_label,
)
from skills_cliq import (
    send_cliq_channel_message, send_cliq_direct_message,
    broadcast_bot_message, alert_deal_won, alert_new_hot_lead,
    post_daily_pipeline_to_cliq,
)
from skills_automation import (
    trigger_flow_webhook, list_active_flows, get_flow_execution_history,
    list_crm_workflow_rules, run_end_of_day_report, auto_follow_up_stalled_deals,
)

SYSTEM_PROMPT = """
You are the CSMO AI assistant for Butler Button (butlerbutton.co) — a premium
luxury travel concierge service. You help Carl, the Chief Sales & Marketing
Officer, manage the full commercial operation across Zoho CRM, Zoho Mail,
Zoho Cliq, and Zoho Flow automations.

Your priorities:
1. Revenue: Surface stalled deals, close-soon deals, and pipeline health.
2. Leads: Identify hot leads quickly; recommend qualification or conversion.
3. Clients: Protect VIP relationships; always note client preferences.
4. Operations: Keep tasks current; nothing falls through the cracks.
5. Communication: Use Cliq for team alerts, Mail for client outreach.
6. Automation: Trigger Zoho Flows to handle repetitive workflows.

Tone: direct, crisp, executive-level. Use numbers. Flag risks clearly.
Currency is INR (Rs.). All dates are Asia/Kolkata time (IST).
""".strip()

ALL_TOOLS = [
    # Pipeline
    get_pipeline_summary, get_revenue_forecast, get_deals_closing_soon,
    get_stalled_deals, get_won_deals_mtd, update_deal_stage,
    # Leads
    get_new_leads, get_lead_source_breakdown, convert_lead, qualify_lead,
    # Contacts
    search_contacts, get_contact_history, create_contact,
    get_vip_clients, tag_contact,
    # Activities
    get_tasks_due_today, get_overdue_tasks, create_task,
    log_call, schedule_meeting,
    # Butler Button concierge
    get_active_requests, create_service_request,
    get_upcoming_trips, get_client_preferences, get_daily_csmo_brief,
    # Mail
    send_email, create_draft, send_email_and_log_to_crm,
    get_recent_emails, search_emails, get_unread_count,
    create_folder, create_label,
    # Cliq
    send_cliq_channel_message, send_cliq_direct_message,
    broadcast_bot_message, alert_deal_won, alert_new_hot_lead,
    post_daily_pipeline_to_cliq,
    # Automation
    trigger_flow_webhook, list_active_flows, get_flow_execution_history,
    list_crm_workflow_rules, run_end_of_day_report, auto_follow_up_stalled_deals,
]


async def main():
    options = ClaudeAgentOptions(
        model="claude-opus-4-7",
        system_prompt=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
    )
    async with ClaudeSDKClient(options) as agent:
        print("Butler Button CSMO Agent ready. Type 'quit' to exit.\n")
        print("Suggested prompts:")
        print("  'Give me my morning brief'")
        print("  'Show stalled deals and create follow-up tasks'")
        print("  'Send a proposal email to [name] and log it in CRM'")
        print("  'Post end-of-day report to Cliq'\n")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in {"quit", "exit", "q"}:
                break
            if not user_input:
                continue
            response = await agent.send_message(user_input)
            print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
