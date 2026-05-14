"""Calculates priority scores for incoming leads based on firmographic data.

The scoring logic applies predefined weights to various attributes like
company size, industry, and email domain type. Duplicate leads are
immediately zero-scored to prevent unnecessary downstream processing and
sales rep notification fatigue.
Exports:
    calculate_score: Returns an integer score for a given lead.
"""

import logging

from app.schemas.lead import LeadWebhookPayload

logger = logging.getLogger(__name__)


def calculate_score(
    payload: LeadWebhookPayload, enriched_data: dict, is_duplicate: bool
) -> int:
    """Calculate a priority score for the lead.

    Applies scoring rules based on firmographics and email domain quality.
    Duplicate leads are automatically scored at 0.

    Args:
        payload (LeadWebhookPayload): The incoming lead data.
        enriched_data (dict): Firmographic data retrieved from the enrichment API.
        is_duplicate (bool): Whether this lead was flagged as a duplicate.

    Returns:
        int: The computed lead score.

    Example:
        >>> from app.schemas.lead import LeadWebhookPayload
        >>> from app.services.scorer import calculate_score
        >>> payload = LeadWebhookPayload(email="test@enterprise.com")
        >>> calculate_score(payload, {"company_size": "201-1000"}, False)
        40

    """
    if is_duplicate:
        logger.info(f"Lead {payload.email} is a duplicate, setting score to 0")
        return 0

    score = 10

    # Enrichment: Company Size
    company_size = enriched_data.get("company_size")
    if company_size in ["51-200"]:
        score += 15
    elif company_size == "201-1000":
        score += 25

    # Enrichment: Industry
    industry = enriched_data.get("industry", "")
    tech_industries = ["saas", "tech", "artificial intelligence", "ai/ml", "software"]
    if isinstance(industry, str) and industry.lower() in tech_industries:
        score += 20
    elif industry == "Finance":
        score += 10

    # Email Domain
    email = payload.email or ""
    free_providers = [
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com",
    ]
    domain = email.split("@")[-1] if "@" in email else ""
    if domain and domain not in free_providers and domain != "unknown.com":
        score += 10

    # Company field presence
    if payload.company and payload.company.lower() not in ["unknown", "???", ""]:
        score += 5

    logger.info(f"Calculated score {score} for lead {email}")
    return score
