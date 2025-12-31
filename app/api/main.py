from fastapi import FastAPI
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

app = FastAPI(
    title="WhatToWatch API",
    description="Movie recommendation service with AI-powered personalization",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "WhatToWatch API"}


@app.get("/health")
async def health():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check that verifies database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": "disconnected", "error": str(e)}
