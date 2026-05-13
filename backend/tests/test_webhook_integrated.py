"""End-to-end integration tests for the lead processing pipeline."""

import pytest
import httpx
import re
from app.main import app
from app.core.config import settings
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_lead_webhook_integrated_pipeline(client, httpx_mock, db_session):
    """Verify the entire ingestion-to-routing flow with a complex real-world scenario.

    This test combines email extraction from a message, external enrichment,
    and routing. It confirms that the different services interact correctly
    to produce a high-confidence lead score from minimal initial data.
    """
    # Mock all external calls
    httpx_mock.add_response(url=settings.ENRICH_API_URL, json={
        "company_name": "Future Space Corp",
        "industry": "Tech",
        "company_size": "51-200",
        "domain": "futurespace.io"
    })
    httpx_mock.add_response(url=re.compile(r".*slack\.com.*"), status_code=200)
    httpx_mock.add_response(url=re.compile(r".*crm\.com.*"), status_code=200)
    
    payload = {
        "full_name": "Alice Rocket",
        "message": "My email is alice@futurespace.io",
        "website": "https://futurespace.io"
    }
    
    response = await client.post("/api/v1/lead", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["score"] >= 50

@pytest.mark.asyncio
async def test_lead_webhook_garbage_data(client, db_session):
    """Ensure the system remains stable when receiving non-JSON or corrupted payloads.

    Resilience is a core requirement. This test verifies that the pipeline
    recovers from invalid input and returns a structured response instead of
    triggering a server-side crash (500).
    """
    response = await client.post("/api/v1/lead", content="not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    assert response.json()["status"] in ["processed", "error"]
