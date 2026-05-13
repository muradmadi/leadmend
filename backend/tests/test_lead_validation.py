"""Unit tests for lead payload validation and self-healing logic."""

import pytest
from app.services.validator import normalize_payload
from app.schemas.lead import LeadWebhookPayload

def test_valid_payload():
    """Ensure that standard, well-formed lead payloads are correctly parsed.

    This test confirms that when the source provides all expected fields in
    the correct format, the normalizer maps them 1:1 without alteration.
    """
    raw = {
        "email": "test@example.com",
        "full_name": "John Doe",
        "company": "Test Co",
        "website": "https://test.com",
        "message": "Hello"
    }
    payload, meta = normalize_payload(raw)
    assert payload.email == "test@example.com"
    assert payload.full_name == "John Doe"
    assert payload.company == "Test Co"
    assert str(payload.website).rstrip('/') == "https://test.com"
    assert meta['original_had_email'] is True

def test_empty_payload():
    """Confirm the system can handle completely empty JSON objects without crashing.

    Requirement: Always accept leads. This test ensures that an empty body
    triggers 'unknown' defaults for the database, allowing the ingestion
    pipeline to complete.
    """
    raw = {}
    payload, meta = normalize_payload(raw)
    assert payload.email == "unknown@unknown.com"
    assert payload.company == "Unknown"
    assert payload.full_name is None
    assert meta['original_had_email'] is False

def test_weird_email():
    """Validate recovery when an invalid email format is provided.

    If the user enters garbage in the email field, Pydantic will fail.
    This test verifies that the 'self-healing' logic catches the validation
    error and falls back to a default placeholder email.
    """
    # Invalid email format should be caught and replaced by default
    raw = {
        "email": "not-an-email",
        "full_name": "Jane Doe"
    }
    payload, meta = normalize_payload(raw)
    assert payload.email == "unknown@unknown.com"
    assert payload.full_name == "Jane Doe"

def test_email_extraction_from_message():
    """Ensure emails buried in free-text message bodies can be extracted.

    Many leads forget the email field but mention it in their message.
    This test verifies the regex-based extraction logic that attempts to
    find and promote an email from the 'message' field to the 'email' field.
    """
    raw = {
        "message": "Contact me at contact@startup.io or visit our site."
    }
    payload, meta = normalize_payload(raw)
    assert payload.email == "contact@startup.io"
    # Company should be inferred as "Unknown" if no website given
    assert payload.company == "Unknown"
    assert meta['original_had_email'] is False
    assert any("extracted" in w for w in meta['warnings'])

def test_company_inference_from_website():
    """Validate that company names are intelligently inferred from website URLs.

    When the company name is missing, the system should look at the domain
    name and capitalize it to create a human-readable placeholder.
    """
    raw = {
        "email": "info@acme.com",
        "website": "https://acme-tools.com"
    }
    payload, meta = normalize_payload(raw)
    assert payload.company == "Acme-tools"

def test_company_inference_from_www_website():
    """Confirm that 'www' prefixes are ignored during company name inference.

    URLs like 'www.globex.com' should yield 'Globex', not 'Www'. This test
    verifies the subdomain-stripping logic.
    """
    raw = {
        "email": "info@globex.com",
        "website": "https://www.globex.com"
    }
    payload, meta = normalize_payload(raw)
    assert payload.company == "Globex"

def test_unknown_extra_fields():
    """Ensure that non-standard metadata fields are preserved in the payload.

    The model is configured with 'extra=allow'. This test confirms that
    marketing-specific fields (like ad IDs) are not discarded during
    normalization, allowing them to be passed to downstream CRM workflows.
    """
    raw = {
        "email": "extra@fields.com",
        "meta_data": {"source": "facebook", "ad_id": 123},
        "custom_id": "999"
    }
    payload, meta = normalize_payload(raw)
    assert payload.email == "extra@fields.com"
    # Check if extra fields are preserved if using model_dump(exclude_unset=False)
    # Pydantic v2 extra fields are accessible via __dict__ or model_extra
    assert payload.model_extra["meta_data"] == {"source": "facebook", "ad_id": 123}
    assert payload.model_extra["custom_id"] == "999"

def test_normalization_stripping():
    """Verify that email addresses are lowercased and stripped of whitespace.

    To ensure consistent deduplication, '  USER@Example.COM  ' must be
    normalized to 'user@example.com' before database lookup.
    """
    raw = {
        "email": "  USER@Example.COM  ",
        "company": "  Spacey Co  "
    }
    payload, meta = normalize_payload(raw)
    assert payload.email == "user@example.com"
    # Note: company field doesn't have explicit strip validator in schema, 
    # but could be added. The user didn't ask for company stripping, 
    # only email normalization.
