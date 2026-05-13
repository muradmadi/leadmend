"""Defines the database schema and validation models for lead data.

This module separates the SQLAlchemy ORM model used for database interactions
from the Pydantic schema used for API request validation. The Pydantic model
includes self-healing validators that attempt to extract or infer missing
information (like emails from messages or company names from domains) before
raising validation errors.
Exports:
    Lead: The SQLAlchemy ORM model for leads.
    LeadWebhookPayload: The Pydantic validation schema for incoming requests.
"""

import re
import logging
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Integer, DateTime, text, Index
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, ConfigDict, EmailStr, HttpUrl, field_validator, model_validator
from app.core.db import Base

logger = logging.getLogger(__name__)

class Lead(Base):
    """Represents a validated and enriched lead in the database.

    This class maps to the ``leads`` table and uses pg_trgm indexing on the
    ``company_name`` column to allow fuzzy matching during deduplication.

    Attributes:
        id (int): Primary key for the lead record.
        email (str): The primary contact email.
        company_name (str, optional): The name of the company.
        company_domain (str, optional): The domain of the company.
        industry (str, optional): The industry classification.
        company_size (str, optional): The size classification of the company.
        lead_score (int): The computed priority score.
        source (str, optional): The origin of the lead (e.g., 'website').
        created_at (datetime): When the record was created.
        updated_at (datetime): When the record was last modified.

    """

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lead_score: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow)

    __table_args__ = (
        Index(
            "idx_leads_company_name_trgm",
            "company_name",
            postgresql_using="gin",
            postgresql_ops={"company_name": "gin_trgm_ops"},
        ),
    )

class LeadWebhookPayload(BaseModel):
    """Validates incoming lead payloads with self-healing mechanisms.

    This model deliberately accepts incomplete data. Its pre-validators try
    to recover missing emails by searching the message body, and post-validators
    attempt to infer the company name from the provided website domain.

    Attributes:
        email (EmailStr, optional): The user's email address.
        full_name (str, optional): The user's full name.
        company (str, optional): The company name.
        website (HttpUrl, optional): The company's website URL.
        message (str, optional): A free-text message from the user.

    """

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    company: Optional[str] = None
    website: Optional[HttpUrl] = None
    message: Optional[str] = None
    
    model_config = ConfigDict(extra='allow')

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, v: Any, info: Any) -> Any:
        """Strip whitespace and lowercase the email address.

        Args:
            v (Any): The raw email field value.
            info (Any): Validation context information.

        Returns:
            Any: The normalized email string, or the original value if missing.
            
        Example:
            >>> from app.schemas.lead import LeadWebhookPayload
            >>> LeadWebhookPayload.normalize_email("  Test@Example.com  ", None)
            'test@example.com'

        """
        if isinstance(v, str):
            v = v.strip().lower()
            if v:
                return v
        
        # If email is missing or empty, try to extract from message
        # We need to access 'message' from the raw data if possible, 
        # but in 'before' validator for a field, we only have the field value.
        # Wait, Pydantic v2 'before' validator for a field only receives the value.
        # To access other fields, I might need a model_validator(mode='before').
        return v

    @model_validator(mode='before')
    @classmethod
    def extract_email_from_message(cls, data: Any) -> Any:
        """Attempt to recover an email from the message body if missing.

        Args:
            data (Any): The raw dictionary payload.

        Returns:
            Any: The modified payload with an extracted email, if found.
            
        Example:
            >>> from app.schemas.lead import LeadWebhookPayload
            >>> data = {"message": "Reach me at missing@example.com"}
            >>> LeadWebhookPayload.extract_email_from_message(data)
            {'message': 'Reach me at missing@example.com', 'email': 'missing@example.com'}

        """
        if isinstance(data, dict):
            email = data.get('email')
            message = data.get('message')
            
            if not email and message:
                email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
                match = re.search(email_regex, message)
                if match:
                    extracted_email = match.group(0).lower()
                    logger.warning(f"Email missing, extracted {extracted_email} from message")
                    data['email'] = extracted_email
            
            if email and isinstance(email, str):
                data['email'] = email.strip().lower()
        return data

    @model_validator(mode='after')
    def infer_company(self) -> 'LeadWebhookPayload':
        """Infer the company name from the website domain if missing.

        Returns:
            LeadWebhookPayload: The instance with an inferred company name.
            
        Example:
            >>> from app.schemas.lead import LeadWebhookPayload
            >>> payload = LeadWebhookPayload(website="https://acme.com")
            >>> payload.infer_company().company
            'Acme'

        """
        if not self.company and self.website:
            try:
                # crudely extract company name from domain
                host = self.website.host
                if host:
                    parts = host.split('.')
                    if len(parts) >= 2:
                        # e.g. "www.example.com" -> "example"
                        # "example.co.uk" -> "example" (maybe too complex for crude)
                        # Just take the first part that isn't www
                        if parts[0] == 'www' and len(parts) > 2:
                            self.company = parts[1].capitalize()
                        else:
                            self.company = parts[0].capitalize()
                        logger.info(f"Inferred company '{self.company}' from website {self.website}")
            except Exception:
                pass
        return self

