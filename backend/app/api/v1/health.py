"""
Health Check API Endpoint.
"""

from fastapi import APIRouter
from app.core.config import settings
from app.database.connection import verify_database_health

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Returns application health and vector database connection status."""
    db_health = verify_database_health()
    return {
        "status": "healthy" if db_health.get("status") == "healthy" else "degraded",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "chroma_status": db_health,
        "embedding_model": settings.EMBEDDING_MODEL,
        "generation_model": settings.GEMINI_GENERATION_MODEL
    }
