"""
Main FastAPI Application Entry Point
AI-Powered Clinical Triage & Holistic Recommendation System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import app_logger
from api import triage, hospitals

app = FastAPI(
    title="AI Clinical Triage System",
    description=(
        "AI-Powered Healthcare Triage System. "
        "Describe your symptoms and get triage recommendations."
        "\n\n**Disclaimer**: This is a demo and NOT a substitute for professional medical advice."
    ),
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# Routers
app.include_router(triage.router)
app.include_router(hospitals.router)


# Health check
@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "version": settings.VERSION}


# Startup
@app.on_event("startup")
async def startup():
    app_logger.info(f"Starting {settings.APP_NAME}...")
    os.makedirs("logs", exist_ok=True)
    
    from db.database import init_db
    await init_db()
    app_logger.info("Database initialized. Server ready!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
