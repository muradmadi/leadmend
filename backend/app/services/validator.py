"""Validates and normalizes raw lead-capture form payloads.

The validators in this module are deliberately tolerant: a missing email
field does not cause a rejection. Instead, the normalizer attempts to
extract an email from a free-text message field, and falls back to
``unknown@unknown.com`` if no email can be found. This trade-off —
accepting incomplete data over pipeline interruption — was chosen because
the downstream enrichment API can often recover firmographic data from a
company domain alone.
Exports:
    normalize_payload: Transforms raw JSON dict into a LeadWebhookPayload.
"""

import logging
from pydantic import ValidationError
from app.schemas.lead import LeadWebhookPayload

logger = logging.getLogger(__name__)

def normalize_payload(raw: dict) -> tuple[LeadWebhookPayload, dict]:
    """Transform raw JSON dict into a LeadWebhookPayload.

    Attempts to validate the payload, and if it fails, logs the errors 
    and returns an object with default values for critical missing/invalid fields.
    This approach ensures that malformed webhook data doesn't crash the pipeline.

    Args:
        raw (dict): The raw JSON payload received from the webhook.

    Returns:
        tuple[LeadWebhookPayload, dict]: A tuple containing the validated payload 
            and a metadata dict with 'original_had_email' and 'warnings'.
        
    Example:
        >>> from app.services.validator import normalize_payload
        >>> payload, meta = normalize_payload({"email": "test@test.com"})
        >>> meta['original_had_email']
        True

    """
    warnings = []
    original_had_email = bool(raw.get("email") and str(raw.get("email")).strip())
    
    try:
        payload = LeadWebhookPayload(**raw)
    except ValidationError as e:
        logger.warning(f"Validation failed for lead payload: {e.errors()}")
        
        sanitized_data = raw.copy()
        
        # Remove fields that caused errors
        for error in e.errors():
            loc = error['loc']
            if loc:
                field_name = loc[0]
                if isinstance(field_name, str) and field_name in sanitized_data:
                    logger.debug(f"Removing invalid field '{field_name}' from payload")
                    del sanitized_data[field_name]
        
        # Try validating again with invalid fields removed
        try:
            payload = LeadWebhookPayload(**sanitized_data)
        except ValidationError:
            # If it still fails, just use model_construct
            payload = LeadWebhookPayload.model_construct(**sanitized_data)
    
    # Check if email was recovered from message (this logic is also in the Pydantic model)
    # but we want to capture it as a warning for the UI.
    if not original_had_email and payload.email and payload.email != "unknown@unknown.com":
        warnings.append(f"Email extracted from message: {payload.email}")
    
    # Fill in critical defaults if missing (after successful validation or healing)
    if not payload.email:
        payload.email = "unknown@unknown.com"
        logger.info("Setting default email 'unknown@unknown.com'")
    
    if not payload.company:
        payload.company = "Unknown"
        logger.info("Setting default company 'Unknown'")
            
    metadata = {
        "original_had_email": original_had_email,
        "warnings": warnings
    }
            
    return payload, metadata


def is_garbage(payload: LeadWebhookPayload) -> bool:
    """Determine if a lead payload contains garbage or nonsensical data.

    A payload is flagged as garbage if it fails basic sanity checks:
    - Email is missing the '@' character OR is the fallback 'unknown@unknown.com'
    - AND company is empty or 'Unknown'
    - AND website is missing
    - AND (message is shorter than 5 characters OR consists only of digits)

    Args:
        payload (LeadWebhookPayload): The normalized lead payload.

    Returns:
        bool: True if the payload is considered garbage, False otherwise.

    Example:
        >>> from app.schemas.lead import LeadWebhookPayload
        >>> from app.services.validator import is_garbage
        >>> payload = LeadWebhookPayload(email="???", message="123")
        >>> is_garbage(payload)
        True

    """
    email = payload.email or ""
    company = payload.company or ""
    website = str(payload.website) if payload.website else ""
    message = payload.message or ""

    email_invalid = "@" not in email or email == "unknown@unknown.com"
    company_empty = not company or company == "Unknown"
    website_empty = not website or website == "None"
    message_garbage = len(message) < 5 or message.isdigit()

    if email_invalid and company_empty and website_empty and message_garbage:
        logger.warning(f"Garbage payload detected for email: {email}")
        return True

    return False

