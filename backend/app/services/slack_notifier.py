"""Manages asynchronous webhook dispatches to Slack and CRM.

This module uses httpx and tenacity to ensure that network blips don't
result in lost notifications. It implements a fallback mechanism that logs
a simulated notification if the Slack webhook URL is not configured, ensuring
that development and testing can proceed without a live Slack integration.
Exports:
    send_slack_notification: Dispatches a Block Kit payload to Slack.
    send_to_crm: Syncs the lead data to the configured CRM endpoint.
"""

import logging
import httpx
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def send_slack_notification(webhook_url: str, blocks: list, fallback_text: str = "New Lead Notification") -> None:
    """Send a Slack notification using Block Kit.

    Retries up to 3 times on failure. If no webhook URL is configured, it
    simulates the send by logging the payload to standard output.

    Args:
        webhook_url (str): The destination Slack webhook URL.
        blocks (list): A list of Slack Block Kit layout dictionaries.
        fallback_text (str, optional): Plain text fallback for notifications. Defaults to "New Lead Notification".

    Raises:
        httpx.HTTPError: If the request fails after all retries.
        
    Example:
        >>> await send_slack_notification("http://hooks.slack.com/...", [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}])

    """
    if not webhook_url:
        logger.warning(f"Slack webhook not configured, logging message: {fallback_text}")
        print(f"--- SLACK NOTIFICATION (SIMULATED) ---\n{json.dumps(blocks, indent=2)}\n--- END ---")
        return

    payload = {
        "text": fallback_text,
        "blocks": blocks
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Slack notification sent successfully to {webhook_url[:20]}...")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack notification: {e}")
            raise

async def send_to_crm(lead_data: dict) -> None:
    """Send lead data to a CRM endpoint.

    Attempts to POST the lead data once. Any exceptions are caught and logged
    as errors, but they are not raised, ensuring that CRM synchronization
    failures do not break the main webhook pipeline.

    Args:
        lead_data (dict): The complete lead data dictionary.
        
    Example:
        >>> await send_to_crm({"email": "test@test.com", "score": 50})

    """
    url = settings.CRM_WEBHOOK_URL
    if not url:
        logger.warning("CRM_WEBHOOK_URL not configured. Skipping CRM sync.")
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=lead_data)
            response.raise_for_status()
            logger.info("Lead successfully sent to CRM.")
        except Exception as e:
            logger.error(f"CRM sync failed: {e}")
            # Flow should not break as per requirements
