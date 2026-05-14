"""Loads and validates application settings from environment variables.

Provides a central configuration object that reads from the local environment
or a `.env` file via pydantic-settings. Defaults are provided for core
dependencies to allow the application to start in standard Docker Compose
environments without explicit configuration.

Example:
    None

"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Container for application-wide environment configuration.

    Attributes:
        DATABASE_URL (str): The connection string for the async PostgreSQL database.
        ENRICH_API_URL (str): Endpoint for the lead enrichment mock microservice.
        ENRICHMENT_MAX_RETRIES (int): Maximum number of retry attempts for the enrichment API.
        DEDUP_SIMILARITY_THRESHOLD (float): The threshold for pg_trgm fuzzy matching.
        SLACK_HIGH_VALUE_WEBHOOK (str): Webhook URL for routing high-value leads.
        SLACK_MID_VALUE_WEBHOOK (str): Webhook URL for routing mid-value leads.
        SLACK_LOW_VALUE_WEBHOOK (str): Webhook URL for routing low-value leads.
        DUPLICATE_SLACK_WEBHOOK (str): Webhook URL for routing duplicated leads.
        CRM_WEBHOOK_URL (str): Destination for leads being pushed to the CRM.

    """

    DATABASE_URL: str = "postgresql+asyncpg://leadmend:leadmend@db:5432/leadmend"
    ENRICH_API_URL: str = "http://mock-enrich:8080/enrich"
    ENRICHMENT_MAX_RETRIES: int = 3

    DEDUP_SIMILARITY_THRESHOLD: float = 0.8

    SLACK_HIGH_VALUE_WEBHOOK: str = ""
    SLACK_MID_VALUE_WEBHOOK: str = ""
    SLACK_LOW_VALUE_WEBHOOK: str = ""
    DUPLICATE_SLACK_WEBHOOK: str = ""
    SLACK_INVALID_WEBHOOK: str = ""
    CRM_WEBHOOK_URL: str = "http://n8n:5678/webhook/lead"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
