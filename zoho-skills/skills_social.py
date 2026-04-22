"""
Butler Button — Zoho Social Skill Suite
----------------------------------------
Zoho Social has no public REST API.
Posting routes through a Zoho Flow webhook you configure once.
Everything else (content, calendar, analytics brief, repurposing) runs directly.

SETUP (one-time):
  In Zoho Flow → New Flow → Webhook trigger → Action: Zoho Social → Post.
  Set ZOHO_SOCIAL_FLOW_WEBHOOK in .env to the webhook URL Flow gives you.

Skills:
  generate_post            — Claude writes platform-native copy
  generate_multi_platform  — One topic → Instagram + LinkedIn + X simultaneously
  repurpose_content        — Long-form content → platform-native posts
  generate_carousel_copy   — Slide-by-slide text for carousels / reels
  generate_story_copy      — Story format (hook + swipe-up CTA)
  generate_hashtag_set     — Research + curate hashtags by niche
  schedule_post_via_flow   — Dispatch to Zoho Flow webhook → Zoho Social
  create_content_calendar  — 30-day calendar saved as CRM Activities
  get_calendar_week        — Pull this week's scheduled posts from CRM
  log_post_performance     — Record reach/engagement in CRM for benchmarking
  generate_performance_brief — Weekly social performance summary via Claude
  generate_reply           — Draft response to a comment or DM
  generate_campaign_burst  — Full launch campaign: 5 posts across 3 platforms
"""

import os
import json
import anthropic
import requests
from datetime import date, datetime, timedelta
from zoho_client import zoho

_client = None
def _ai():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client

FLOW_WEBHOOK = os.environ.get("ZOHO_SOCIAL_FLOW_WEBHOOK", "")
CLIQ_MARKETING = "marketing"

PLATFORM_VOICE = {
    "instagram": (
        "Instagram — visual-first, emotion-led. 150-220 words. 5-8 hashtags at the end. "
        "NO links. Tone: intimate travel diary of someone who's seen the best the world offers. "
        "Hook in first line — before the 'more' break."
    ),
    "linkedin": (
        "LinkedIn — authority and credibility. 100-160 words. 1-2 hashtags max. "
        "Structure: one sharp observation → brief proof → clear takeaway. "
        "Tone: CSMO voice, thought-leadership, talks about the business of luxury travel."
    ),
    "x": (
        "X/Twitter — max 240 characters. Zero hashtags. One punchy take — contrarian, "
        "confident, or genuinely surprising. Reads like an expert thinking out loud."
    ),
    "facebook": (
        "Facebook — conversational, community-first. 80-120 words. 1-3 hashtags. "
        "Ask a question or invite a comment. Warm, inclusive, slightly less polished than IG."
    ),
}

BB_POV = """Butler Button context:
- Premium luxury travel concierge for discerning travelers
- Not a travel agency — we handle the entire trip end-to-end
- Clients value time over money; they want things arranged, not just booked
- We access inventory and experiences not available on any booking site
- Two-person team: intimate, expert, accountable
Sign off voice: confident, warm, never salesy."""


def _claude(prompt: str, max_tokens: int = 500) -> str:
    r = _ai().messages.create(
        model="claude-opus-4-7",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return r.content[0].text.strip()


def _cliq(msg: str):
    if not zoho.token:
        return
    requests.post(
        f"https://cliq.zoho.in/api/v2/channels/{CLIQ_MARKETING}/message",
        headers={"Authorization": f"Zoho-oauthtoken {zoho.token}",
                 "Content-Type": "application/json"},
        json={"text": msg},
    )


def _post_to_flow(platform: str, content: str, scheduled_time: str = None) -> dict:
    if not FLOW_WEBHOOK:
        return {"status": "no_webhook", "note": "Set ZOHO_SOCIAL_FLOW_WEBHOOK in .env"}
    payload = {"platform": platform, "content": content}
    if scheduled_time:
        payload["scheduled_time"] = scheduled_time
    r = requests.post(FLOW_WEBHOOK, json=payload, timeout=10)
    return {"status": "dispatched", "http": r.status_code}


# ── Content Generation ─────────────────────────────────────────────────────────

def generate_post(platform: str, topic: str, cta: str = "") -> dict:
    """Generate a single platform-native post via Claude.

    Args:
        platform: instagram | linkedin | x | facebook
        topic: What the post is about (angle, hook, story)
        cta: Optional call-to-action to include (e.g. 'DM us to start planning')
    Returns:
        dict with 'platform', 'content', 'char_count'
    """
    voice = PLATFORM_VOICE.get(platform.lower())
    if not voice:
        return {"error": f"Unknown platform '{platform}'. Use: {list(PLATFORM_VOICE)}"}

    prompt = f"""{BB_POV}

Platform: {voice}
Topic / angle: {topic}
{"CTA: " + cta if cta else ""}

Write ONE post. No preamble, no labels. Output ONLY the post copy."""

    content = _claude(prompt)
    return {"platform": platform, "content": content, "char_count": len(content)}


def generate_multi_platform(topic: str, platforms: list = None, cta: str = "") -> dict:
    """Generate native posts for multiple platforms from one topic.

    Args:
        topic: The angle or story to communicate
        platforms: List of platforms (default: instagram, linkedin, x)
        cta: Optional CTA for all platforms
    Returns:
        dict keyed by platform name, each with 'content' and 'char_count'
    """
    platforms = platforms or ["instagram", "linkedin", "x"]
    results = {}
    for p in platforms:
        results[p] = generate_post(p, topic, cta)
    _cliq(f"CONTENT BATCH — {topic[:60]}\n" +
          "\n".join(f"{p.upper()}: {r.get('content','')[:120]}..." for p, r in results.items()))
    return results


def repurpose_content(source_content: str, target_platforms: list = None) -> dict:
    """Turn a blog post, email, or long-form piece into platform-native posts.

    Args:
        source_content: The full text to repurpose (article, newsletter, etc.)
        target_platforms: Platforms to create for (default: instagram, linkedin, x)
    Returns:
        dict keyed by platform with generated post copy
    """
    target_platforms = target_platforms or ["instagram", "linkedin", "x"]
    results = {}
    for p in target_platforms:
        voice = PLATFORM_VOICE.get(p.lower(), "")
        prompt = f"""{BB_POV}

Repurpose the following content into a {p} post.
Platform: {voice}

SOURCE CONTENT:
{source_content[:3000]}

Extract the most compelling angle for {p}. Do not summarize — find the hook.
Output ONLY the post copy."""
        results[p] = {"platform": p, "content": _claude(prompt), "source": "repurposed"}
    return results


def generate_carousel_copy(topic: str, num_slides: int = 6) -> dict:
    """Generate slide-by-slide copy for an Instagram carousel or LinkedIn document post.

    Args:
        topic: The theme or subject of the carousel
        num_slides: Number of slides (default 6; cover + content + CTA)
    Returns:
        dict with 'slides' list, each with 'slide_num', 'headline', 'body'
    """
    prompt = f"""{BB_POV}

Create a {num_slides}-slide Instagram/LinkedIn carousel on: {topic}

Structure:
- Slide 1: COVER — bold hook headline (5-8 words), short subhead
- Slides 2-{num_slides-1}: ONE insight per slide — headline + 1-2 sentence body
- Slide {num_slides}: CTA — strong close + follow/DM prompt

Return as JSON array:
[{{"slide": 1, "headline": "...", "body": "..."}}]
Output ONLY valid JSON."""

    raw = _claude(prompt, max_tokens=800)
    try:
        slides = json.loads(raw[raw.find("["):raw.rfind("]")+1])
    except Exception:
        slides = [{"slide": i+1, "headline": f"Slide {i+1}", "body": raw} for i in range(num_slides)]
    return {"topic": topic, "num_slides": num_slides, "slides": slides}


def generate_story_copy(topic: str, has_link: bool = True) -> dict:
    """Generate Instagram/Facebook Story copy — hook + 3 frames + swipe-up CTA.

    Args:
        topic: Story angle (e.g. 'behind the scenes planning a Maldives honeymoon')
        has_link: Whether to include a swipe-up / link sticker CTA
    Returns:
        dict with 'frames' list (hook, body_1, body_2, cta)
    """
    prompt = f"""{BB_POV}

Write Instagram Story copy for: {topic}

4 frames:
1. HOOK (5-8 words, stops the scroll)
2. FRAME 2 (1 sentence — tension or intrigue)
3. FRAME 3 (1 sentence — payoff or reveal)
4. CTA ({"swipe up / tap link" if has_link else "DM us"} — 6-10 words)

Return as JSON: [{{"frame": 1, "text": "..."}}]
Output ONLY valid JSON."""

    raw = _claude(prompt, max_tokens=300)
    try:
        frames = json.loads(raw[raw.find("["):raw.rfind("]")+1])
    except Exception:
        frames = [{"frame": i+1, "text": ""} for i in range(4)]
    return {"topic": topic, "frames": frames}


def generate_hashtag_set(niche: str, post_content: str = "") -> dict:
    """Research and curate a hashtag set for a post.

    Args:
        niche: Core niche (e.g. 'luxury travel India', 'honeymoon travel')
        post_content: Optional post text to tailor hashtags to
    Returns:
        dict with 'broad', 'niche', 'branded' hashtag lists and 'recommended_mix'
    """
    prompt = f"""Create a 3-tier hashtag strategy for an Instagram post in the luxury travel concierge niche.

Niche: {niche}
{"Post excerpt: " + post_content[:300] if post_content else ""}

Return JSON:
{{
  "broad": ["#travel", ...],        // 3-5 high-volume (1M+ posts)
  "niche": ["#luxurytravel", ...],  // 8-12 targeted (50k-500k posts)
  "branded": ["#ButlerButton", ...], // 2-3 brand/owned tags
  "recommended_mix": "...",          // one sentence on how to use them
  "avoid": ["..."]                   // 2-3 overused or spammy tags to avoid
}}
Output ONLY valid JSON."""

    raw = _claude(prompt, max_tokens=400)
    try:
        return json.loads(raw[raw.find("{"):raw.rfind("}")+1])
    except Exception:
        return {"raw": raw}


# ── Scheduling & Dispatch ──────────────────────────────────────────────────────

def schedule_post_via_flow(platform: str, content: str, scheduled_time: str = None) -> dict:
    """Dispatch a post to Zoho Social via a Zoho Flow webhook.

    Requires ZOHO_SOCIAL_FLOW_WEBHOOK set in .env.
    In Zoho Flow: Webhook trigger → Zoho Social: Create Post action.

    Args:
        platform: Target platform (instagram | linkedin | x | facebook)
        content: Post copy
        scheduled_time: ISO datetime string (e.g. '2026-04-25T10:00:00'); None = post now
    Returns:
        dict with dispatch status
    """
    result = _post_to_flow(platform, content, scheduled_time)
    if result.get("status") == "dispatched":
        _cliq(f"POST DISPATCHED → {platform.upper()}\n"
              f"Time: {scheduled_time or 'now'}\n"
              f"{content[:200]}")
    return result


def create_content_calendar(theme: str, start_date: str = None, num_weeks: int = 4) -> dict:
    """Generate a 4-week social content calendar and save each post as a CRM Task.

    Args:
        theme: Overarching campaign theme (e.g. 'honeymoon season', 'monsoon escapes')
        start_date: ISO date string (default: today)
        num_weeks: Number of weeks to plan (default 4)
    Returns:
        dict with 'calendar' list and 'tasks_created' count
    """
    start = date.fromisoformat(start_date) if start_date else date.today()

    prompt = f"""{BB_POV}

Plan a {num_weeks}-week social media content calendar for Butler Button.
Campaign theme: {theme}
Start date: {start.isoformat()}

Posting cadence: 3x per week (Mon/Wed/Fri). Mix of platforms.

Return as JSON array (one entry per post):
[{{
  "date": "YYYY-MM-DD",
  "platform": "instagram|linkedin|x",
  "format": "feed|carousel|story|reel",
  "topic": "specific post angle",
  "hook": "opening line or headline"
}}]

Output ONLY valid JSON array."""

    raw = _claude(prompt, max_tokens=2000)
    try:
        calendar = json.loads(raw[raw.find("["):raw.rfind("]")+1])
    except Exception:
        return {"error": "Failed to parse calendar", "raw": raw[:500]}

    tasks_created = 0
    for entry in calendar:
        try:
            zoho.crm_post("Tasks", {"data": [{
                "Subject": f"[Social] {entry['platform'].title()} — {entry['topic'][:60]}",
                "Due_Date": entry["date"],
                "Status": "Not Started",
                "Priority": "Normal",
                "Description": (
                    f"Platform: {entry['platform']}\n"
                    f"Format: {entry.get('format','feed')}\n"
                    f"Topic: {entry['topic']}\n"
                    f"Hook: {entry.get('hook','')}"
                ),
            }]})
            tasks_created += 1
        except Exception:
            pass

    _cliq(f"CONTENT CALENDAR CREATED — {theme}\n"
          f"{num_weeks} weeks | {tasks_created} posts scheduled in CRM Tasks")

    return {"theme": theme, "start": start.isoformat(),
            "num_posts": len(calendar), "tasks_created": tasks_created,
            "calendar": calendar}


def get_calendar_week(week_offset: int = 0) -> dict:
    """Pull this week's social content tasks from CRM.

    Args:
        week_offset: 0 = this week, 1 = next week, -1 = last week
    Returns:
        dict with 'posts' list and 'count'
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    tasks = zoho.crm_get("Tasks", params={
        "fields": "Subject,Due_Date,Description,Status",
        "criteria": f"(Due_Date:between:{week_start.isoformat()}:{week_end.isoformat()})",
        "per_page": 50,
    })
    posts = [t for t in tasks.get("data", []) if "[Social]" in (t.get("Subject") or "")]
    return {
        "week": f"{week_start.isoformat()} – {week_end.isoformat()}",
        "count": len(posts),
        "posts": [{"date": t["Due_Date"], "subject": t["Subject"],
                   "status": t["Status"]} for t in posts]
    }


# ── Performance & Reporting ────────────────────────────────────────────────────

def log_post_performance(platform: str, post_description: str,
                         reach: int, likes: int, comments: int,
                         shares: int = 0, saves: int = 0) -> dict:
    """Record post performance metrics in CRM for benchmarking.

    Args:
        platform: Platform the post was on
        post_description: Short description of the post (for identification)
        reach: Number of accounts reached
        likes: Like count
        comments: Comment count
        shares: Share/repost count (default 0)
        saves: Save/bookmark count (default 0)
    Returns:
        dict confirming the logged data
    """
    engagement_rate = round((likes + comments + shares + saves) / max(reach, 1) * 100, 2)
    note = (
        f"SOCIAL PERFORMANCE — {platform.upper()}\n"
        f"Post: {post_description}\n"
        f"Date: {date.today().isoformat()}\n"
        f"Reach: {reach:,} | Likes: {likes} | Comments: {comments} | "
        f"Shares: {shares} | Saves: {saves}\n"
        f"Engagement rate: {engagement_rate}%"
    )
    zoho.crm_post("Notes", {"data": [{
        "Note_Title": f"Social Perf [{platform}] — {date.today().isoformat()}",
        "Note_Content": note,
        "Parent_Id": {"module": "Leads", "id": ""},
    }]})
    return {"platform": platform, "reach": reach, "engagement_rate": engagement_rate,
            "logged": True}


def generate_performance_brief(platform_stats: dict) -> str:
    """Generate a Claude-written weekly social performance analysis.

    Args:
        platform_stats: Dict of platform → metrics dict
          e.g. {"instagram": {"reach": 5200, "followers_gained": 14, "top_post": "Maldives reel"}}
    Returns:
        Formatted performance brief as a string
    """
    BENCHMARKS = {
        "instagram": {"engagement_rate": 3.5, "reach_per_post": 1200},
        "linkedin":  {"engagement_rate": 2.0, "reach_per_post": 800},
        "x":         {"engagement_rate": 1.0, "reach_per_post": 500},
    }

    prompt = f"""{BB_POV}

Analyze this week's social media performance for Butler Button and write a brief.

METRICS:
{json.dumps(platform_stats, indent=2)}

LUXURY TRAVEL BENCHMARKS:
{json.dumps(BENCHMARKS, indent=2)}

Write a 200-word performance brief that:
1. Calls out 1-2 wins (beat benchmark or standout post)
2. Flags 1 underperformer with a specific fix
3. Gives 2 concrete content recommendations for next week
4. Ends with one priority action

Tone: direct, analytical, no fluff. This is an internal brief."""

    brief = _claude(prompt, max_tokens=400)
    _cliq(f"WEEKLY SOCIAL BRIEF\n\n{brief[:600]}")
    return brief


# ── Community & Engagement ─────────────────────────────────────────────────────

def generate_reply(comment_text: str, platform: str, post_topic: str = "") -> str:
    """Draft a brand-voice reply to a comment or DM.

    Args:
        comment_text: The comment or message to respond to
        platform: Platform context (affects tone)
        post_topic: What the original post was about (for context)
    Returns:
        Draft reply as a string
    """
    prompt = f"""{BB_POV}

Platform: {platform}
{"Post was about: " + post_topic if post_topic else ""}
Comment/DM received: "{comment_text}"

Write ONE reply (1-3 sentences). Stay in brand voice — warm, expert, premium.
If it's a lead inquiry, invite them to DM/email for a proper conversation.
Output ONLY the reply text."""

    return _claude(prompt, max_tokens=150)


# ── Campaign Mode ──────────────────────────────────────────────────────────────

def generate_campaign_burst(campaign_name: str, offer: str,
                            launch_date: str, platforms: list = None) -> dict:
    """Generate a full launch campaign: 5 posts across platforms over 2 weeks.

    Posts follow a sequence: Tease → Announce → Proof → Urgency → Close.
    Each is saved as a CRM Task. Copy is generated per platform.

    Args:
        campaign_name: Name of the campaign (e.g. 'Monsoon Maldives Package')
        offer: What's being promoted (e.g. '5-night Maldives overwater villa, all-inclusive')
        launch_date: ISO date string for the official launch day
        platforms: Platforms to create content for (default: instagram, linkedin, x)
    Returns:
        dict with 'posts' list (date, platform, phase, content) and 'tasks_created'
    """
    platforms = platforms or ["instagram", "linkedin", "x"]
    launch = date.fromisoformat(launch_date)

    phases = [
        ("Tease",    -5, "Build intrigue without revealing. Ask a question. No explicit offer."),
        ("Announce",  0, "Official launch. State the offer clearly. Create excitement."),
        ("Proof",     3, "Social proof, a story, or a specific detail that validates the offer."),
        ("Urgency",   7, "Scarcity or deadline. Drive action without being pushy."),
        ("Close",    10, "Final call. Warm but clear. Make it easy to take the next step."),
    ]

    posts = []
    tasks_created = 0

    for phase_name, offset, phase_brief in phases:
        post_date = launch + timedelta(days=offset)
        for platform in platforms:
            voice = PLATFORM_VOICE.get(platform.lower(), "")
            prompt = f"""{BB_POV}

Campaign: {campaign_name}
Offer: {offer}
Phase: {phase_name} — {phase_brief}
Platform: {voice}

Write ONE post for this phase. Stay true to the phase intent.
Output ONLY the post copy."""

            content = _claude(prompt, max_tokens=400)
            posts.append({
                "date": post_date.isoformat(), "platform": platform,
                "phase": phase_name, "content": content
            })

            try:
                zoho.crm_post("Tasks", {"data": [{
                    "Subject": f"[Campaign] {campaign_name} — {phase_name} ({platform})",
                    "Due_Date": post_date.isoformat(),
                    "Status": "Not Started",
                    "Priority": "High",
                    "Description": f"Phase: {phase_name}\nPlatform: {platform}\n\n{content}",
                }]})
                tasks_created += 1
            except Exception:
                pass

    _cliq(
        f"CAMPAIGN BURST CREATED — {campaign_name}\n"
        f"Launch: {launch_date} | {len(phases)} phases × {len(platforms)} platforms "
        f"= {tasks_created} posts in CRM"
    )

    return {"campaign": campaign_name, "launch_date": launch_date,
            "platforms": platforms, "posts": posts, "tasks_created": tasks_created}
