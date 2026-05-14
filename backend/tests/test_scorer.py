"""Unit tests for the lead scoring service."""

from app.schemas.lead import LeadWebhookPayload
from app.services.scorer import calculate_score


def test_calculate_score_base():
    """Ensure the baseline score is correctly applied for leads with no metadata.

    A lead with a generic email and no enrichment data should receive only
    the base configuration score (10 points), representing the minimum
    threshold for a valid ingestion.
    """
    # Base case: no enrichment, generic email, unknown company
    payload = LeadWebhookPayload(email="test@gmail.com", company="Unknown")
    enriched_data = {}
    score = calculate_score(payload, enriched_data, is_duplicate=False)
    # Base 10, nothing else matches
    assert score == 10


def test_calculate_score_acceptance_criteria():
    """Validate scoring for high-value target profiles (Business email + Enterprise size + Tech).

    High-value leads are defined by corporate domains and larger company sizes
    in relevant industries. This test ensures the additive weights (Base 10 +
    Size 25 + Industry 20 + Business Email 10) total exactly 65.
    """
    # A lead from a SaaS company with size 201-1000 and business email
    # scores 10 + 30 + 15 + 10 = 65
    payload = LeadWebhookPayload(
        email="john@acme.com",
        company="Unknown",  # Set to "Unknown" to avoid +5 bonus
    )
    enriched_data = {"industry": "SaaS", "company_size": "201-1000"}
    score = calculate_score(payload, enriched_data, is_duplicate=False)
    assert score == 65


def test_calculate_score_with_company_bonus():
    """Ensure that explicitly providing a company name yields a quality bonus.

    Leads that include a company name in the raw payload are considered
    higher intent and should receive a small score boost (+5) over those that
    only provide a website.
    """
    payload = LeadWebhookPayload(email="john@acme.com", company="Acme Corp")
    enriched_data = {"industry": "SaaS", "company_size": "201-1000"}
    # 10 (base) + 30 (size) + 15 (industry) + 10 (business email) + 5 (company field) = 70
    score = calculate_score(payload, enriched_data, is_duplicate=False)
    assert score == 70


def test_calculate_score_duplicate():
    """Confirm that duplicate leads are zero-scored regardless of their profile.

    To prevent redundant alerts and skewing of analytics, any lead identified
    as a duplicate must have its score neutralized to 0.
    """
    payload = LeadWebhookPayload(email="john@acme.com")
    enriched_data = {"industry": "SaaS", "company_size": "201-1000"}
    score = calculate_score(payload, enriched_data, is_duplicate=True)
    assert score == 0


def test_calculate_score_small_company():
    """Verify that small company sizes (unsupported in tiers) do not receive bonuses.

    Our current ICP targets mid-to-enterprise companies. Small company sizes
    like '11-50' should not trigger size-based bonuses, resulting in a base
    score only.
    """
    payload = LeadWebhookPayload(email="test@gmail.com", company="Unknown")
    enriched_data = {"company_size": "11-50"}
    # 10 (base) + 0 (size) = 10
    score = calculate_score(payload, enriched_data, is_duplicate=False)
    assert score == 10


def test_calculate_score_tech_industry():
    """Ensure that technology-sector leads receive a significant priority boost.

    The 'Tech' industry is a primary target segment and should receive a
    +20 point bonus, leading to a total of 30 when starting from the base.
    """
    payload = LeadWebhookPayload(email="test@gmail.com", company="Unknown")
    enriched_data = {"industry": "Tech"}
    # 10 (base) + 20 (industry) = 30
    score = calculate_score(payload, enriched_data, is_duplicate=False)
    assert score == 30
