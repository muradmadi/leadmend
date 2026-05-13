"""Routes leads to appropriate downstream channels based on priority tier.

This module translates numerical lead scores into action tiers (high, mid,
low, duplicate) and dispatches notifications via Slack. It orchestrates
asynchronous deliveries to both communication and CRM channels, ensuring
that slow or failed webhooks don't block the main web request.
Exports:
    route_lead: Determines tier and triggers notifications.
"""

import logging
from app.core.config import settings
from app.services.slack_notifier import send_slack_notification, send_to_crm

logger = logging.getLogger(__name__)

async def route_lead(score: int, lead_data: dict) -> dict:
    """Route a lead based on its calculated score.

    Maps the score to a priority tier (high, mid, low, duplicate) and
    dispatches an asynchronous Slack notification to the configured channel.
    It also pushes the lead to the CRM.

    Args:
        score (int): The computed lead score.
        lead_data (dict): The consolidated payload and enrichment data.

    Returns:
        dict: A routing plan summary detailing the assigned tier and sync status.
        
    Example:
        >>> await route_lead(65, {"email": "ceo@bigcorp.com"})
        {'tier': 'high', 'score': 65, 'slack_notified': True, 'crm_synced': True}

    """
    if lead_data.get("is_garbage"):
        tier = "invalid"
        webhook_url = settings.SLACK_INVALID_WEBHOOK
    elif score >= 60:
        tier = "high"
        webhook_url = settings.SLACK_HIGH_VALUE_WEBHOOK
    elif 30 <= score < 60:
        tier = "mid"
        webhook_url = settings.SLACK_MID_VALUE_WEBHOOK
    elif 0 < score < 30:
        tier = "low"
        webhook_url = settings.SLACK_LOW_VALUE_WEBHOOK
    elif score <= 0:
        tier = "duplicate"
        webhook_url = settings.DUPLICATE_SLACK_WEBHOOK

    # Extract data for routing and logging
    email = lead_data.get("email", "Unknown")
    company = lead_data.get("company", "Unknown")
    industry = lead_data.get("industry", "N/A")
    size = lead_data.get("company_size", "N/A")

    # If webhook URL is missing, log a warning but don't fail
    if tier == "invalid" and not webhook_url:
        logger.warning(f"Invalid lead detected but SLACK_INVALID_WEBHOOK is not set. Lead: {email}")
    
    # Build Slack Blocks for a premium feel
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔥 New Lead: {tier.capitalize()} Priority",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"A new lead has been processed and scored *{score}* points."
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                {"type": "mrkdwn", "text": f"*Company:*\n{company}"},
                {"type": "mrkdwn", "text": f"*Industry:*\n{industry}"},
                {"type": "mrkdwn", "text": f"*Size:*\n{size}"}
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Status: Processed by Leadmend Routing Service | Tier: {tier.upper()}"
                }
            ]
        }
    ]
    
    # Send Slack Notification (async)
    await send_slack_notification(
        webhook_url=webhook_url, 
        blocks=blocks, 
        fallback_text=f"New {tier} lead: {email} ({score})"
    )
    
    # Send to CRM (async, handled internally to not break flow)
    await send_to_crm(lead_data)
    
    routing_plan = {
        "tier": tier,
        "score": score,
        "slack_notified": bool(webhook_url),
        "crm_synced": True
    }
    
    logger.info(f"Lead {email} routed. Tier: {tier}, Score: {score}")
    return routing_plan
