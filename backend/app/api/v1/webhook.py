"""Provides the main entry point for the lead ingestion webhook.

This module orchestrates the entire lead processing pipeline: it parses incoming
JSON, attempts to normalize and self-heal missing fields, queries external APIs
for enrichment, checks for duplicates using exact and fuzzy matching, calculates
a routing score, persists or updates the database record, and finally dispatches
notifications to Slack and the CRM. It guarantees a 200 OK response to the caller
even in the event of internal failures.
Exports:
    router: The FastAPI APIRouter containing the webhook endpoint.
"""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.lead import Lead
from app.services.deduplicator import check_duplicate
from app.services.enricher import enrich_lead
from app.services.router import route_lead
from app.services.scorer import calculate_score
from app.services.validator import is_garbage, normalize_payload

router = APIRouter()
logger = structlog.get_logger()


@router.post("/lead")
async def process_lead(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_request_id: Optional[str] = Header(None),
    simulate_failure: bool = False,
):
    """Process an incoming lead webhook payload.

    Coordinates validation, enrichment, deduplication, scoring, and routing.
    If the lead is identified as a duplicate, its existing database record
    is 'healed' using any newly provided or enriched data.

    Args:
        request (Request): The raw FastAPI request object.
        db (AsyncSession): The active database session injected via dependency.
        x_request_id (str, optional): An optional correlation ID for logging. Defaults to None.
        simulate_failure (bool, optional): If True, skips external API calls to simulate failure modes. Defaults to False.

    Returns:
        dict: A status summary detailing the score, duplicate status, and routing destination.

    Example:
        >>> # Simulating an HTTP POST to /api/v1/lead
        >>> response_data = {"status": "processed", "score": 75, "is_duplicate": False}
        >>> response_data['status']
        'processed'

    """
    correlation_id = x_request_id or str(uuid.uuid4())
    log = logger.bind(request_id=correlation_id)

    try:
        # 1. Receive raw JSON as dict
        try:
            raw_payload = await request.json()
        except Exception:
            log.warning("Invalid JSON received")
            raw_payload = {}

        log.info("Processing lead webhook", payload=raw_payload)

        # 2. Call normalize_payload(raw) -> (LeadWebhookPayload, metadata)
        payload, meta = normalize_payload(raw_payload)
        log.info("Payload normalized", email=payload.email, company=payload.company)

        # --- Garbage Detection Short-circuit ---
        if is_garbage(payload):
            log.warning(
                "Pipeline short-circuited: Garbage lead detected", email=payload.email
            )
            score = 0
            is_duplicate = False
            enriched_data = {
                "industry": "Unknown",
                "company_size": "Unknown",
                "company_name": "Unknown",
                "company_domain": "unknown.com",
            }
            # Skip real enrichment, dedupe, and DB persistence for garbage
            routing_result = await route_lead(
                score,
                {
                    "email": payload.email,
                    "company": payload.company,
                    **enriched_data,
                    "lead_id": None,
                    "score": score,
                    "is_garbage": True,
                },
            )

            return {
                "status": "processed",
                "score": score,
                "is_duplicate": is_duplicate,
                "lead_id": None,
                "email": payload.email,
                "original_payload_had_email": meta.get("original_had_email", False),
                "validation_warnings": meta.get("warnings", []),
                "routing_channel": "#ops-invalid",
                "enriched_data": enriched_data,
                "routing": {"slack_channel": "#ops-invalid", "crm_posted": False},
            }
        # ----------------------------------------

        # 3. Call enrich_lead(payload, simulate_failure) -> dict
        enriched_data = await enrich_lead(payload, simulate_failure)
        log.info("Lead enrichment complete", enriched_data=enriched_data)

        # 4. Call check_duplicate(db, payload.email, payload.company, company_domain)
        company_domain = enriched_data.get("company_domain")
        dup_check = await check_duplicate(
            db, payload.email, payload.company, company_domain
        )
        is_duplicate = dup_check.get("is_duplicate", False)
        existing_id = dup_check.get("existing_id")
        log.info(
            "Duplicate check complete",
            is_duplicate=is_duplicate,
            match_type=dup_check.get("match_type"),
        )

        # 5. Call calculate_score(payload, enriched_data, is_duplicate)
        score = calculate_score(payload, enriched_data, is_duplicate)
        log.info("Score calculated", score=score)

        # 6. Database persistence (Update or Create)
        lead_id = None
        if is_duplicate and existing_id:
            # Self-healing: enrich the old record
            result = await db.execute(select(Lead).where(Lead.id == existing_id))
            existing_lead = result.scalar_one_or_none()

            if existing_lead:
                # Only update if current data is placeholder/empty
                if (
                    not existing_lead.company_name
                    or existing_lead.company_name == "Unknown"
                ):
                    existing_lead.company_name = (
                        enriched_data.get("company_name") or payload.company
                    )
                if not existing_lead.industry or existing_lead.industry == "Unknown":
                    existing_lead.industry = enriched_data.get("industry")
                if (
                    not existing_lead.company_size
                    or existing_lead.company_size == "Unknown"
                ):
                    existing_lead.company_size = enriched_data.get("company_size")
                if (
                    not existing_lead.company_domain
                    or existing_lead.company_domain == "Unknown"
                ):
                    existing_lead.company_domain = company_domain

                await db.commit()
                log.info(
                    "Existing lead record healed with new enrichment data",
                    lead_id=existing_id,
                )
            lead_id = existing_id
        else:
            # Create new lead record
            new_lead = Lead(
                email=payload.email,
                company_name=enriched_data.get("company_name") or payload.company,
                company_domain=company_domain,
                industry=enriched_data.get("industry"),
                company_size=enriched_data.get("company_size"),
                lead_score=score,
                source=raw_payload.get("source", "webhook"),
            )
            db.add(new_lead)
            await db.commit()
            await db.refresh(new_lead)
            lead_id = new_lead.id
            log.info("New lead created in database", lead_id=lead_id)

        # 7. Call route_lead(score, combined_data)
        combined_data = {
            "email": payload.email,
            "company": payload.company,
            **enriched_data,
            "lead_id": lead_id,
            "score": score,
        }
        routing_result = await route_lead(score, combined_data)
        log.info("Lead routing triggered", routing_plan=routing_result)

        # Map tier to channel-like name for the return JSON
        tier_mapping = {
            "high": "#sales-hot",
            "mid": "#sales-warm",
            "low": "#sales-cold",
            "duplicate": "#ops-duplicates",
            "invalid": "#ops-invalid",
        }
        slack_channel = tier_mapping.get(routing_result.get("tier"), "#general")

        return {
            "status": "processed",
            "score": score,
            "is_duplicate": is_duplicate,
            "lead_id": lead_id,
            "email": payload.email,
            "original_payload_had_email": meta.get("original_had_email", False),
            "validation_warnings": meta.get("warnings", []),
            "routing_channel": slack_channel,
            "enriched_data": enriched_data,
            "routing": {
                "slack_channel": slack_channel,
                "crm_posted": routing_result.get("crm_synced", False),
            },
        }

    except Exception as e:
        log.error("Webhook processing pipeline failed", error=str(e), exc_info=True)
        # Requirement: Always a 200 with helpful response, no 500s.
        return {
            "status": "error",
            "message": "Lead received but processing encountered an error",
            "error_detail": str(e),
        }


@router.post("/reset")
async def reset_database(db: AsyncSession = Depends(get_db)):
    """Delete all leads from the database for demo reset purposes.

    Args:
        db (AsyncSession): The active database session injected via dependency.

    Returns:
        dict: A status message confirming the deletion.

    Example:
        >>> from app.api.v1.webhook import reset_database
        >>> # await reset_database(db)
        >>> {'status': 'reset', 'message': 'All leads deleted.'}

    """
    await db.execute(delete(Lead))
    await db.commit()
    return {"status": "reset", "message": "All leads deleted."}
