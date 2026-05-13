"""Business logic and external service integrations.

This module contains the core domain logic for LeadMend, including lead
validation, enrichment via external APIs, duplicate detection using fuzzy
matching, and prioritized routing. Services are designed to be idempotent
and resilient, ensuring that failures in individual components (like
enrichment or CRM sync) do not block the overall lead ingestion pipeline.

Exports:
    None (Services are imported individually from their respective modules).
"""
