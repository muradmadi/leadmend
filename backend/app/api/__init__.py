"""API routing module for LeadMend.

This package manages the external interface of the application. It follows
a versioned routing strategy (e.g., /v1/) to ensure backward compatibility
as the webhook schema evolves. The primary entry point is the lead ingestion
webhook, which acts as a controller for the underlying service layer.

Exports:
    None.
"""
