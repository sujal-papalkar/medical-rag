"""
FastAPI Application Entry Point.

Modular Monolith Architecture for Grounded Ayurvedic Prescription RAG.
"""

from pathlib import Path
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.v1.router import api_router
from app.database.connection import verify_database_health
from app.schemas.prescriptions import PrescriptionGenerateRequest
from app.schemas.retrieval import RetrievalQueryRequest
from app.api.v1.prescriptions import generate_prescription
from app.api.v1.retrieval import search_evidence, get_chunk_detail

configure_logging()
logger = get_logger("app-main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Clean, Production-Ready Ayurvedic Clinical Guideline RAG Backend",
    version=settings.VERSION
)

# Enable CORS for frontend Vite dev server and production clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount primary API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


# ============================================================
# BACKWARD COMPATIBILITY ENDPOINTS (For existing frontend / dashboard)
# ============================================================

@app.get("/api/health", tags=["Compatibility"])
def legacy_health():
    db_health = verify_database_health()
    return {
        "status": "healthy" if db_health.get("status") == "healthy" else "degraded",
        "phase": 1,
        "module": "ayurvedic_prescription_rag",
        "collection": settings.CHROMA_COLLECTION_NAME,
        "model": settings.EMBEDDING_MODEL,
        "chroma_status": db_health
    }


@app.post("/api/generate", tags=["Compatibility"])
def legacy_generate(payload: PrescriptionGenerateRequest):
    return generate_prescription(payload)


@app.post("/api/evaluate/custom", tags=["Compatibility"])
def legacy_custom_retrieval(payload: RetrievalQueryRequest):
    return search_evidence(payload)


@app.get("/api/chunks/{chunk_id}", tags=["Compatibility"])
def legacy_chunk_detail(chunk_id: str):
    return get_chunk_detail(chunk_id)


@app.get("/api/dataset", tags=["Compatibility"])
def legacy_get_dataset():
    draft_file = settings.DATASETS_PATH / "draft_golden_dataset.json"
    if draft_file.exists():
        return json.loads(draft_file.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Draft golden dataset not found.")


@app.on_event("startup")
def on_startup():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    db_health = verify_database_health()
    logger.info(f"Database status: {db_health}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
