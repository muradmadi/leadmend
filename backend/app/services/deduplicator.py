"""Identifies potential duplicate leads using exact and fuzzy matching.

This module leverages PostgreSQL's pg_trgm extension to catch variations
in company names or domains, which simple exact matches would miss. By
evaluating similarity thresholds, it prevents redundant CRM entries while
accommodating slight typos or different domain formats.
Exports:
    check_duplicate: Evaluates a lead against existing database records.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.lead import Lead


async def check_duplicate(
    db: AsyncSession, email: str, company_name: str, domain: str
) -> dict:
    """Check if a lead already exists in the database.

    Performs an exact match on the email address, followed by fuzzy pg_trgm
    similarity matching on the company name and domain against a configured
    threshold. This order is chosen to fail fast on exact matches before
    resorting to more expensive similarity queries.

    Args:
        db (AsyncSession): An active database session.
        email (str): The email address to check exactly.
        company_name (str): The company name to check via fuzzy matching.
        domain (str): The company domain to check via fuzzy matching.

    Returns:
        dict: A dictionary indicating if it is a duplicate, the existing ID,
        and the match type.

    Example:
        >>> from app.services.deduplicator import check_duplicate
        >>> # Assuming 'session' is an active AsyncSession
        >>> await check_duplicate(session, "test@test.com", "Test Co", "test.com")
        {'is_duplicate': True, 'existing_id': 1, 'match_type': 'email'}

    """
    # 1. Exact email match
    query_email = select(Lead).where(Lead.email == email)
    result_email = await db.execute(query_email)
    existing_lead = result_email.scalar_one_or_none()

    if existing_lead:
        return {
            "is_duplicate": True,
            "existing_id": existing_lead.id,
            "match_type": "email",
        }

    # 2. Fuzzy match on company name
    if company_name:
        # Use pg_trgm similarity
        query_company = (
            select(Lead)
            .where(
                func.similarity(Lead.company_name, company_name)
                > settings.DEDUP_SIMILARITY_THRESHOLD
            )
            .order_by(func.similarity(Lead.company_name, company_name).desc())
            .limit(1)
        )

        result_company = await db.execute(query_company)
        match_company = result_company.scalar_one_or_none()

        if match_company:
            return {
                "is_duplicate": True,
                "existing_id": match_company.id,
                "match_type": "company_name",
            }

    # 3. Fuzzy match on domain
    if domain:
        query_domain = (
            select(Lead)
            .where(
                func.similarity(Lead.company_domain, domain)
                > settings.DEDUP_SIMILARITY_THRESHOLD
            )
            .order_by(func.similarity(Lead.company_domain, domain).desc())
            .limit(1)
        )

        result_domain = await db.execute(query_domain)
        match_domain = result_domain.scalar_one_or_none()

        if match_domain:
            return {
                "is_duplicate": True,
                "existing_id": match_domain.id,
                "match_type": "domain",
            }

    return {"is_duplicate": False}
