"""Integration tests for the main lead webhook endpoint."""

import pytest
import re
from unittest.mock import MagicMock
from app.schemas.lead import Lead
from app.core.config import settings

@pytest.fixture(autouse=True)
def mock_settings():
    """Mock webhook URLs to ensure httpx calls are made."""
    settings.SLACK_HIGH_VALUE_WEBHOOK = "http://slack.com/high"
    settings.SLACK_MID_VALUE_WEBHOOK = "http://slack.com/mid"
    settings.SLACK_LOW_VALUE_WEBHOOK = "http://slack.com/low"
    settings.DUPLICATE_SLACK_WEBHOOK = "http://slack.com/dup"
    settings.SLACK_INVALID_WEBHOOK = "http://slack.com/invalid"
    settings.CRM_WEBHOOK_URL = "http://crm.com/webhook"

def mock_routing_calls(httpx_mock):
    """Mock Slack and CRM calls which are common in most tests."""
    # We use regex to cover any slack webhook and is_reusable to handle multiple calls if needed
    httpx_mock.add_response(url=re.compile(r"http://slack\.com/.*"), status_code=200)
    httpx_mock.add_response(url=settings.CRM_WEBHOOK_URL, status_code=200)

@pytest.mark.asyncio
async def test_webhook_valid_complete_data(client, httpx_mock, db_session):
    """Ensure that a well-formed lead payload is processed and scored correctly.

    This test verifies the 'happy path' where all required fields are present,
    enrichment is successful, and the lead is not a duplicate. It confirms
    that the pipeline calculates the expected score and routes to the correct
    Slack channel.
    """
    # Mock Enrichment
    httpx_mock.add_response(
        method="POST",
        url=settings.ENRICH_API_URL,
        json={
            "company_name": "Apple",
            "industry": "Tech",
            "company_size": "201-1000",
            "domain": "apple.com"
        }
    )
    mock_routing_calls(httpx_mock)
    
    payload = {
        "email": "tim@apple.com",
        "company": "Apple",
        "website": "https://apple.com"
    }
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    # Base 10 + Business 10 + Company 5 + Size 30 + Industry 15 = 70
    assert data["score"] == 70
    assert data["routing"]["slack_channel"] == "#sales-hot"
    
    assert db_session.add.called
    assert db_session.commit.called

@pytest.mark.asyncio
async def test_webhook_missing_fields(client, httpx_mock, db_session):
    """Validate the 'self-healing' capability when critical fields are missing.

    This test submits a payload without an email or company name to ensure
    the normalizer provides sensible defaults and doesn't crash the pipeline,
    satisfying the requirement for high-availability ingestion.
    """
    # Mock Enrichment
    httpx_mock.add_response(
        method="POST",
        url=settings.ENRICH_API_URL,
        json={"company_name": "Unknown", "industry": "Unknown", "company_size": "Unknown", "domain": "unknown.com"}
    )
    mock_routing_calls(httpx_mock)

    # Missing email/company
    payload = {"message": "Hello", "website": "https://none.com"}
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

@pytest.mark.asyncio
async def test_webhook_duplicate_email(client, httpx_mock, db_session):
    """Verify that duplicate leads are identified and routed to the audit channel.

    Duplicate leads should not trigger a new CRM entry or high-priority
    notifications. This test ensures the system recognizes an existing email
    and correctly flags it as a duplicate in the response.
    """
    # Mock existing lead
    existing_lead = Lead(id=123, email="dup@example.com", company_name="Old Corp")
    existing_lead.industry = "Unknown"
    existing_lead.company_size = "Unknown"
    existing_lead.company_domain = "Unknown"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_lead
    db_session.execute.return_value = mock_result

    # Mock Enrichment
    httpx_mock.add_response(method="POST", url=settings.ENRICH_API_URL, json={"company_name": "New Corp"})
    mock_routing_calls(httpx_mock)

    payload = {"email": "dup@example.com", "company": "New Corp"}
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_duplicate"] is True
    assert data["score"] == 0
    assert data["routing"]["slack_channel"] == "#ops-duplicates"

@pytest.mark.asyncio
async def test_webhook_enrichment_failure(client, httpx_mock, db_session):
    """Confirm pipeline resilience when the external enrichment API is unreachable.

    The system must continue processing even if 3rd-party services fail.
    This test simulates repeated HTTP 503 errors from the enrichment service
    and verifies that the lead is still ingested with basic data.
    """
    # Mock Enrichment Failure
    for _ in range(settings.ENRICHMENT_MAX_RETRIES):
        httpx_mock.add_response(method="POST", url=settings.ENRICH_API_URL, status_code=503)
    
    mock_routing_calls(httpx_mock)
    
    # Gmail + Unknown company = score 10
    payload = {"email": "fail@gmail.com", "company": "Unknown"}
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    assert response.json()["score"] == 10

@pytest.mark.asyncio
async def test_webhook_routing_logic(client, httpx_mock, db_session):
    """Verify that lead scores are correctly mapped to specific Slack webhooks.

    This test checks the final routing logic to ensure that a high-scoring
    lead actually triggers a POST request to the 'high-value' Slack webhook
    configured in settings.
    """
    # High score
    httpx_mock.add_response(
        method="POST",
        url=settings.ENRICH_API_URL,
        json={"company_name": "Giant", "company_size": "201-1000", "industry": "Tech"}
    )
    mock_routing_calls(httpx_mock)
    
    payload = {"email": "ceo@giant.com", "company": "Giant"}
    
    await client.post("/api/v1/lead", json=payload)
    
    # Verify high value slack called
    requests = httpx_mock.get_requests()
    slack_urls = [str(r.url) for r in requests]
    assert settings.SLACK_HIGH_VALUE_WEBHOOK in slack_urls


@pytest.mark.asyncio
async def test_webhook_garbage_payload(client, httpx_mock, db_session):
    """Confirm that obviously garbage payloads are short-circuited and routed to #ops-invalid.

    Garbage payloads should result in a score of 0, skip enrichment,
    not be saved to the database, and route to the invalid lead channel.
    """
    mock_routing_calls(httpx_mock)
    
    payload = {
        "name": "???",
        "email": "asdf@jkl",
        "company": "",
        "website": "",
        "message": "1234"
    }
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0
    assert data["routing_channel"] == "#ops-invalid"
    assert data["enriched_data"]["industry"] == "Unknown"
    
    # Verify enrichment was NEVER called
    requests = httpx_mock.get_requests()
    enrich_calls = [r for r in requests if str(r.url) == settings.ENRICH_API_URL]
    assert len(enrich_calls) == 0
    
    # Verify DB add was NEVER called for this lead
    assert not db_session.add.called
