"""Augments lead data by querying an external enrichment API.

This module uses a mock or third-party Clearbit-compatible API to fetch
firmographic data based on the lead's email domain. It wraps the HTTP
client with a tenacity exponential backoff policy, prioritizing pipeline
continuity over perfect data; if the external API fails repeatedly, it
returns a default dictionary.
Exports:
    enrich_lead: Calls the enrichment API for a given lead.
"""

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.schemas.lead import LeadWebhookPayload

logger = logging.getLogger(__name__)


async def enrich_lead(
    payload: LeadWebhookPayload, simulate_failure: bool = False
) -> dict:
    """Enrich lead data by calling an external enrichment API.

    If simulate_failure is True, it skips the API call and returns fallback values.

    Retries on failure with exponential backoff. Returns a dictionary with
    enriched data or default values on failure to ensure the pipeline continues
    even if the enrichment provider is down.

    Args:
        payload (LeadWebhookPayload): The validated lead payload.
        simulate_failure (bool, optional): If True, skips the API call and returns fallback values. Defaults to False.

    Returns:
        dict: The enriched firmographic data.

    Example:
        >>> from app.schemas.lead import LeadWebhookPayload
        >>> from app.services.enricher import enrich_lead
        >>> payload = LeadWebhookPayload(email="test@clearbit.com")
        >>> await enrich_lead(payload)
        {'company_name': 'Clearbit', 'industry': 'Tech'}

    """
    domain = None
    if payload.website:
        domain = payload.website.host

    request_data = {"email": payload.email, "domain": domain}

    try:
        if simulate_failure:
            raise httpx.HTTPError("Simulated enrichment failure")

        async with httpx.AsyncClient() as client:
            return await _enrich_call_with_retry(client, request_data)
    except Exception as e:
        logger.warning(
            f"Enrichment failed after {settings.ENRICHMENT_MAX_RETRIES} attempts: {e}"
        )
        return {
            "company_name": payload.company or "Unknown",
            "industry": "Unknown",
            "company_size": "Unknown",
            "company_domain": domain or "Unknown",
        }


@retry(
    stop=stop_after_attempt(settings.ENRICHMENT_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def _enrich_call_with_retry(client: httpx.AsyncClient, data: dict) -> dict:
    """Execute the HTTP POST request to the enrichment API with retries.

    Args:
        client (httpx.AsyncClient): The HTTPX async client.
        data (dict): The payload to send to the enrichment API.

    Raises:
        httpx.HTTPError: If the request fails after all retries.
        httpx.TimeoutException: If the request times out repeatedly.

    Returns:
        dict: The JSON response parsed into a dictionary.

    Example:
        >>> import httpx
        >>> from app.services.enricher import _enrich_call_with_retry
        >>> async with httpx.AsyncClient() as client:
        ...     await _enrich_call_with_retry(client, {"email": "test@test.com"})
        {'company_name': 'Test'}

    """
    response = await client.post(settings.ENRICH_API_URL, json=data, timeout=5.0)
    response.raise_for_status()

    res_json = response.json()
    return {
        "company_name": res_json.get("company_name", "Unknown"),
        "industry": res_json.get("industry", "Unknown"),
        "company_size": res_json.get("company_size", "Unknown"),
        "company_domain": res_json.get("domain", data.get("domain")),
    }
