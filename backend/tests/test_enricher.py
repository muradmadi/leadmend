"""Unit tests for the resilient lead enrichment service."""

import logging

import pytest

from app.core.config import settings
from app.schemas.lead import LeadWebhookPayload
from app.services.enricher import enrich_lead


@pytest.mark.asyncio
async def test_enrich_lead_success(httpx_mock):
    """Test successful enrichment on the first call."""
    payload = LeadWebhookPayload(
        email="test@example.com", website="https://example.com"
    )

    httpx_mock.add_response(
        method="POST",
        url=settings.ENRICH_API_URL,
        json={
            "company_name": "Example Corp",
            "industry": "Technology",
            "company_size": "11-50",
            "domain": "example.com",
        },
    )

    result = await enrich_lead(payload)

    assert result["company_name"] == "Example Corp"
    assert result["industry"] == "Technology"
    assert result["company_size"] == "11-50"
    assert result["company_domain"] == "example.com"
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_enrich_lead_retry_and_success(httpx_mock):
    """Test that enrichment succeeds after a temporary failure."""
    payload = LeadWebhookPayload(email="retry@example.com", website="https://retry.com")

    # First call fails with 500, second call succeeds
    httpx_mock.add_response(method="POST", status_code=500)
    httpx_mock.add_response(
        method="POST",
        json={
            "company_name": "Retry Success Ltd",
            "industry": "Software",
            "company_size": "51-200",
            "domain": "retry.com",
        },
    )

    result = await enrich_lead(payload)

    assert result["company_name"] == "Retry Success Ltd"
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio
async def test_enrich_lead_fallback_after_max_retries(httpx_mock, caplog):
    """Test that default values are returned and a warning is logged after all retries fail."""
    payload = LeadWebhookPayload(
        email="fail@example.com", website="https://fail.com", company="Original Name"
    )

    # Mock failures for all allowed retry attempts
    for _ in range(settings.ENRICHMENT_MAX_RETRIES):
        httpx_mock.add_response(method="POST", status_code=503)

    with caplog.at_level(logging.WARNING):
        result = await enrich_lead(payload)

    assert result["industry"] == "Unknown"
    assert result["company_size"] == "Unknown"
    assert result["company_name"] == "Original Name"
    assert result["company_domain"] == "fail.com"

    # Verify that the warning was logged
    assert any("Enrichment failed after" in record.message for record in caplog.records)

    # Verify the number of attempts made
    assert len(httpx_mock.get_requests()) == settings.ENRICHMENT_MAX_RETRIES
