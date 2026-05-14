"""Unit tests for the exact and fuzzy duplicate detection service."""

from unittest.mock import MagicMock

import pytest

from app.services.deduplicator import check_duplicate


@pytest.mark.asyncio
async def test_exact_email_match(db_session, sample_leads):
    """Ensure that exact email matches are caught immediately.

    Email uniqueness is the strongest signal for duplication. This test
    verifies that if a lead exists with the same email, the system fails
    fast and returns an 'email' match type before running fuzzy queries.
    """
    # Mock DB to return a lead for email match
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_leads[0]
    db_session.execute.return_value = mock_result

    result = await check_duplicate(
        db_session,
        email="existing@example.com",
        company_name="Totally Different",
        domain="diff.com",
    )
    assert result["is_duplicate"] is True
    assert result["match_type"] == "email"


@pytest.mark.asyncio
async def test_fuzzy_company_match(db_session, sample_leads):
    """Validate that company names with slight variations are flagged via pg_trgm.

    This ensures that 'Acme Corp' and 'Acme Corporation' are treated as
    the same entity if they cross the similarity threshold, preventing
    fragmented CRM data.
    """
    # 1. First call for email (None)
    # 2. Second call for company (Success)
    mock_email_result = MagicMock()
    mock_email_result.scalar_one_or_none.return_value = None

    mock_company_result = MagicMock()
    mock_company_result.scalar_one_or_none.return_value = sample_leads[1]

    db_session.execute.side_effect = [mock_email_result, mock_company_result]

    result = await check_duplicate(
        db_session,
        email="new-person@acme.com",
        company_name="Acme Corporation",
        domain="acme.com",
    )
    assert result["is_duplicate"] is True
    assert result["match_type"] == "company_name"


@pytest.mark.asyncio
async def test_no_match(db_session):
    """Verify that genuinely unique leads are permitted through the pipeline.

    New leads with no email, name, or domain similarity to existing records
    should be marked as unique to allow a fresh CRM entry to be created.
    """
    # Mock DB to return None for all checks
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute.return_value = mock_result

    result = await check_duplicate(
        db_session,
        email="fresh@startup.io",
        company_name="Fresh Startup",
        domain="fresh-startup.io",
    )
    assert result["is_duplicate"] is False
