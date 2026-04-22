"""Pipeline & revenue skills for the Butler Button CSMO agent."""

import json
from datetime import date, timedelta
from claude_agent import tool
from zoho_client import zoho


@tool
def get_pipeline_summary() -> str:
    """Return open deal count and total value grouped by pipeline stage."""
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Closing_Date,Account_Name",
        "criteria": "(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "per_page": 200,
    })
    deals = data.get("data", [])
    stages: dict[str, dict] = {}
    for d in deals:
        s = d.get("Stage", "Unknown")
        stages.setdefault(s, {"count": 0, "value": 0})
        stages[s]["count"] += 1
        stages[s]["value"] += d.get("Amount") or 0
    total_value = sum(v["value"] for v in stages.values())
    lines = [f"Pipeline snapshot — {len(deals)} open deals  |  ${total_value:,.0f} total"]
    for stage, agg in sorted(stages.items(), key=lambda x: -x[1]["value"]):
        lines.append(f"  {stage}: {agg['count']} deals  ${agg['value']:,.0f}")
    return "\n".join(lines)


@tool
def get_revenue_forecast(days: int = 30) -> str:
    """Return weighted revenue forecast for deals closing within N days.

    Args:
        days: Lookahead window in days (default 30).
    """
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Closing_Date,Probability,Account_Name",
        "criteria": f"(Closing_Date:less_equal:{cutoff})and(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "per_page": 200,
    })
    deals = data.get("data", [])
    weighted_total = sum((d.get("Amount") or 0) * (d.get("Probability") or 0) / 100 for d in deals)
    gross_total = sum(d.get("Amount") or 0 for d in deals)
    lines = [
        f"Forecast (next {days} days) — {len(deals)} deals",
        f"  Gross pipeline: ${gross_total:,.0f}",
        f"  Weighted forecast: ${weighted_total:,.0f}",
        "",
        "Top deals:",
    ]
    for d in sorted(deals, key=lambda x: -(x.get("Amount") or 0))[:5]:
        lines.append(
            f"  {d['Deal_Name']} — ${d.get('Amount', 0):,.0f}  "
            f"({d.get('Probability', 0)}%)  closes {d.get('Closing_Date', '?')}"
        )
    return "\n".join(lines)


@tool
def get_deals_closing_soon(days: int = 7) -> str:
    """List deals closing within N days that are not yet won/lost.

    Args:
        days: Days ahead to look (default 7).
    """
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    today = date.today().isoformat()
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Closing_Date,Account_Name,Owner",
        "criteria": f"(Closing_Date:between:{today},{cutoff})and(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)",
        "sort_by": "Closing_Date",
        "per_page": 50,
    })
    deals = data.get("data", [])
    if not deals:
        return f"No deals closing in the next {days} days."
    lines = [f"Deals closing in {days} days ({len(deals)}):"]
    for d in deals:
        owner = (d.get("Owner") or {}).get("name", "—")
        lines.append(
            f"  [{d.get('Closing_Date')}] {d['Deal_Name']}  {d.get('Stage')}  "
            f"${d.get('Amount', 0):,.0f}  Owner: {owner}"
        )
    return "\n".join(lines)


@tool
def get_stalled_deals(inactive_days: int = 14) -> str:
    """List open deals with no CRM activity in the past N days.

    Args:
        inactive_days: Inactivity threshold in days (default 14).
    """
    cutoff = (date.today() - timedelta(days=inactive_days)).isoformat()
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Stage,Amount,Last_Activity_Time,Account_Name,Owner",
        "criteria": f"(Stage:not_equal:Closed Won)and(Stage:not_equal:Closed Lost)and(Last_Activity_Time:less_equal:{cutoff}T00:00:00-05:00)",
        "sort_by": "Last_Activity_Time",
        "per_page": 50,
    })
    deals = data.get("data", [])
    if not deals:
        return f"No stalled deals (all touched within {inactive_days} days)."
    lines = [f"Stalled deals — no activity in {inactive_days}+ days ({len(deals)}):"]
    for d in deals:
        owner = (d.get("Owner") or {}).get("name", "—")
        last = d.get("Last_Activity_Time", "never")[:10] if d.get("Last_Activity_Time") else "never"
        lines.append(
            f"  {d['Deal_Name']}  {d.get('Stage')}  ${d.get('Amount', 0):,.0f}  "
            f"last touched: {last}  Owner: {owner}"
        )
    return "\n".join(lines)


@tool
def get_won_deals_mtd() -> str:
    """Return deals won month-to-date with total revenue."""
    first_of_month = date.today().replace(day=1).isoformat()
    today = date.today().isoformat()
    data = zoho.crm_get("Deals", params={
        "fields": "Deal_Name,Amount,Closing_Date,Account_Name",
        "criteria": f"(Stage:equals:Closed Won)and(Closing_Date:between:{first_of_month},{today})",
        "per_page": 200,
    })
    deals = data.get("data", [])
    total = sum(d.get("Amount") or 0 for d in deals)
    lines = [f"Won MTD: {len(deals)} deals  ${total:,.0f}"]
    for d in sorted(deals, key=lambda x: -(x.get("Amount") or 0)):
        lines.append(f"  {d['Deal_Name']}  ${d.get('Amount', 0):,.0f}  {d.get('Closing_Date')}")
    return "\n".join(lines)


@tool
def update_deal_stage(deal_id: str, new_stage: str) -> str:
    """Move a CRM deal to a new pipeline stage.

    Args:
        deal_id: Zoho CRM Deal record ID.
        new_stage: Target stage name (must match CRM picklist exactly).
    """
    zoho.crm_put(f"Deals/{deal_id}", {"data": [{"Stage": new_stage}]})
    return f"Deal {deal_id} moved to '{new_stage}'."
