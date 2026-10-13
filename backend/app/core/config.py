"""
Central Configuration for Medical RAG System.

Resolves all filesystem paths absolutely using Path(__file__) to prevent
accidental duplicate ChromaDB creation or missing runtime artifact folders.
"""

from pathlib import Path
from typing import List, Optional
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# ============================================================
# ABSOLUTE DIRECTORY PATHS
# ============================================================

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

ENV_FILE = BACKEND_DIR / ".env"
CHROMA_DB_PATH = BACKEND_DIR / "chroma_db"
DATA_DIR = BACKEND_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
EXTRACTED_DIR = DATA_DIR / "extracted"
CHUNKS_DIR = DATA_DIR / "chunks"
CHUNKS_FILE = CHUNKS_DIR / "chunks.json"
CHUNK_SUMMARY_FILE = CHUNKS_DIR / "chunk_summary.json"

EVALUATION_DIR = BACKEND_DIR / "evaluation"
DATASETS_DIR = EVALUATION_DIR / "datasets"
REPORTS_DIR = EVALUATION_DIR / "reports"
LOGS_DIR = BACKEND_DIR / "logs"

# Ensure runtime directories exist
for path in (UPLOADS_DIR, EXTRACTED_DIR, CHUNKS_DIR, REPORTS_DIR, LOGS_DIR):
    path.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application Settings loaded from environment and backend/.env."""

    PROJECT_NAME: str = "Ayurvedic Medical Guidelines RAG"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # API Keys
    GEMINI_API_KEY: str = ""

    # Embedding and Vector Storage
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768
    CHROMA_COLLECTION_NAME: str = "medical_guidelines"
    CHROMA_PERSIST_DIR: str = str(CHROMA_DB_PATH)

    # Retrieval and Reranking Parameters (Hybrid Semantic + BM25 + Cross-Encoder)
    RETRIEVAL_CANDIDATE_K: int = 20
    DEFAULT_TOP_K: int = 5
    EVALUATION_TOP_K: int = 10
    SEMANTIC_WEIGHT: float = 0.70
    LEXICAL_WEIGHT: float = 0.30

    # Cross-Encoder Reranking Parameters
    ENABLE_CROSS_ENCODER: bool = True
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    CROSS_ENCODER_TOP_N: int = 10
    RERANKING_MODE: str = "hybrid"  # "hybrid" (calibrated ensemble) or "cascade" (cross-encoder reordering)
    CROSS_ENCODER_WEIGHT: float = 0.50
    HYBRID_SEMANTIC_WEIGHT: float = 0.35
    HYBRID_LEXICAL_WEIGHT: float = 0.15

    # Generation Parameters
    GEMINI_GENERATION_MODEL: str = "gemini-3.5-flash-lite"
    FALLBACK_MODELS: List[str] = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
    NUM_GENERATION_CANDIDATES: int = 3
    MAX_GENERATION_RETRIES: int = 3
    INITIAL_BACKOFF_SECONDS: float = 2.0

    # Paths
    CHROMA_PATH: Path = CHROMA_DB_PATH
    DATA_PATH: Path = DATA_DIR
    UPLOADS_PATH: Path = UPLOADS_DIR
    EXTRACTED_PATH: Path = EXTRACTED_DIR
    CHUNKS_PATH: Path = CHUNKS_FILE
    CHUNK_SUMMARY_FILE: Path = CHUNK_SUMMARY_FILE
    DATASETS_PATH: Path = DATASETS_DIR
    REPORTS_PATH: Path = REPORTS_DIR

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Fallback: if GEMINI_API_KEY is not set via pydantic_settings, try os.getenv
if not settings.GEMINI_API_KEY:
    settings.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
