"""Initializes the FastAPI application, routing, and database lifecycle.

This module acts as the entry point for the LeadMend backend. It wires up
CORS middleware, registers the webhook API routes, and manages the database
connection pool lifecycle. The lifespan context manager ensures that the
database schema is initialized before serving requests and torn down gracefully.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.webhook import router as webhook_router
from app.core.db import engine, init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application startup and shutdown events.

    Initializes the database schema and pg_trgm extensions before the server
    starts accepting connections. It yields control to the application, and
    cleans up the database connection pool upon shutdown to prevent connection
    leaks.

    Args:
        app (FastAPI): The running application instance.

    Yields:
        None: Control is passed back to the ASGI server.

    Example:
        This is not called directly, but used by FastAPI:

        >>> app = FastAPI(lifespan=lifespan)

    """
    # Initialize DB (create tables if they don't exist)
    try:
        await init_db()
        logger.info("Database initialized (tables created)")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))

    yield
    await engine.dispose()


app = FastAPI(title="LeadMend API", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # For demo purposes, allowing all. In production, restrict this.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(webhook_router, prefix="/api/v1", tags=["webhook"])


@app.get("/health")
async def health_check():
    """Return a simple readiness indicator.

    Provides a low-overhead endpoint for load balancers or Docker healthchecks
    to verify that the web server is responsive.

    Returns:
        dict: A simple {"status": "ok"} dictionary.

    Example:
        >>> from app.main import health_check
        >>> # await health_check()
        >>> {'status': 'ok'}

    """
    return {"status": "ok"}
