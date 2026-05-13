"""Pytest fixtures and configuration for the LeadMend backend.

Provides common dependencies such as the mocked database session, test client,
and sample lead data to be injected into the test suite.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.db import get_db
from app.schemas.lead import Lead

@pytest_asyncio.fixture
async def client():
    """Provide an asynchronous HTTP client for testing FastAPI endpoints.

    Yields:
        AsyncClient: The configured test client.

    """
    # Use httpx.ASGITransport for testing without a running server
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def db_session():
    """Create a mock SQLAlchemy AsyncSession.

    Configures default behaviors for execute and other methods.
    """
    session = AsyncMock()
    
    # Mock the result of session.execute(...)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    
    session.execute.return_value = mock_result
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    
    return session

@pytest.fixture
def sample_leads():
    """Return a list of mock Lead objects."""
    return [
        Lead(id=1, email="existing@example.com", company_name="Acme International", company_domain="acme-int.com"),
        Lead(id=2, email="another@globex.com", company_name="Globex Corporation", company_domain="long-domain-name-for-testing.com"),
    ]

@pytest.fixture(autouse=True)
def override_get_db(db_session):
    """Automatically override the get_db dependency for all tests."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.pop(get_db, None)
