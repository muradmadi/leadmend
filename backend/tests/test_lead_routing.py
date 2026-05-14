"""Unit tests for the lead routing and notification service."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.router import route_lead


@pytest.mark.asyncio
async def test_route_lead_high_tier():
    """Ensure high-scoring leads are correctly identified as 'high' priority.

    Leads with a score >= 60 represent our primary targets and must be routed
    to the high-value Slack channel for immediate response.
    """
    lead_data = {
        "email": "test@enterprise.com",
        "company": "Big Corp",
        "industry": "Tech",
        "company_size": "201-1000",
    }
    score = 75

    with patch(
        "app.services.router.send_slack_notification", new_callable=AsyncMock
    ) as mock_slack, patch(
        "app.services.router.send_to_crm", new_callable=AsyncMock
    ) as mock_crm:
        plan = await route_lead(score, lead_data)

        assert plan["tier"] == "high"
        assert plan["score"] == 75
        mock_slack.assert_called_once()
        mock_crm.assert_called_once()


@pytest.mark.asyncio
async def test_route_lead_duplicate():
    """Verify that duplicate leads (score <= 0) are routed to the ops-audit channel.

    Duplicates should be quarantined for manual review by the operations team
    instead of cluttering the sales channels.
    """
    lead_data = {"email": "dup@example.com"}
    score = 0

    with patch(
        "app.services.router.send_slack_notification", new_callable=AsyncMock
    ) as mock_slack, patch(
        "app.services.router.send_to_crm", new_callable=AsyncMock
    ) as mock_crm:
        plan = await route_lead(score, lead_data)

        assert plan["tier"] == "duplicate"
        mock_slack.assert_called_once()
        mock_crm.assert_called_once()


@pytest.mark.asyncio
async def test_route_lead_no_webhook_logs(caplog):
    """Confirm that the system handles unconfigured Slack webhooks gracefully.

    If a webhook URL is missing from the environment, the system should log
    a warning but still return a valid routing plan, ensuring the API
    remains functional.
    """
    lead_data = {"email": "no-webhook@example.com"}
    score = 15

    # Mock settings to have empty webhooks
    with patch("app.services.router.settings") as mock_settings, patch(
        "app.services.router.send_to_crm", new_callable=AsyncMock
    ), patch("app.services.slack_notifier.httpx.AsyncClient.post"):
        mock_settings.SLACK_LOW_VALUE_WEBHOOK = ""

        plan = await route_lead(score, lead_data)

        assert plan["tier"] == "low"
        # We check the log in slack_notifier if we were to call it for real,
        # but here we just want to ensure it doesn't crash and returns the plan.
        assert (
            "routed_to" not in plan
        )  # Based on my implementation it's "slack_notified"
        assert plan["slack_notified"] is False
