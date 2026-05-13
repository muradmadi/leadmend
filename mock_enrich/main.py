"""Simulates an external data enrichment provider for local testing.

This microservice provides a random, plausible firmographic profile for
a given email domain. It injects artificial latency to simulate real-world
network conditions, allowing developers to test the main backend's resilience,
timeout, and retry logic without incurring third-party API costs.
"""

import asyncio
import random
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from faker import Faker

app = FastAPI(title="Mock Enrichment API")
fake = Faker()

INDUSTRIES = ["SaaS", "Healthcare", "Finance", "Education", "E-commerce", "Cybersecurity", "AI/ML"]
COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]

class EnrichRequest(BaseModel):
    """Payload schema for requesting enrichment data.

    Attributes:
        email (EmailStr): The lead's email address.
        domain (str, optional): The lead's company domain.

    """

    email: EmailStr
    domain: Optional[str] = None

class EnrichResponse(BaseModel):
    """Schema for the firmographic data returned by the service.

    Attributes:
        company_name (str): The generated company name.
        industry (str): The randomly selected industry.
        company_size (str): The randomly selected employee count bracket.
        domain (str): The domain associated with the company.

    """

    company_name: str
    industry: str
    company_size: str
    domain: str

@app.post("/enrich", response_model=EnrichResponse)
async def enrich(request: EnrichRequest):
    """Provide synthetic firmographic data with simulated network latency.

    Args:
        request (EnrichRequest): The incoming enrichment request.

    Returns:
        EnrichResponse: A mock response containing plausible company data.
        
    Example:
        >>> await enrich(EnrichRequest(email="test@startup.io"))
        EnrichResponse(company_name='Random Inc', industry='SaaS', company_size='11-50', domain='startup.io')

    """
    # Simulate API latency
    delay = random.uniform(0.2, 0.5)
    await asyncio.sleep(delay)
    
    # Extract domain from email if not provided
    domain = request.domain
    if not domain:
        domain = request.email.split("@")[-1]
    
    # Deterministic responses for demo scenarios
    if domain == "techflow.ai":
        return EnrichResponse(
            company_name="TechFlow AI",
            industry="Artificial Intelligence",
            company_size="201-1000",
            domain=domain
        )
    elif domain == "thorne.global":
        return EnrichResponse(
            company_name="Thorne Global",
            industry="Finance",
            company_size="51-200",
            domain=domain
        )
    
    return EnrichResponse(
        company_name=fake.company(),
        industry=random.choice(INDUSTRIES),
        company_size=random.choice(COMPANY_SIZES),
        domain=domain
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
