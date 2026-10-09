"""
Document Ingestion Pipeline Orchestrator.

Coordinates:
Upload -> Extraction (Docling) -> Chunking (Structure-Aware) -> Embedding (Gemini) -> ChromaDB
"""

import os
import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from google import genai

from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_collection

logger = get_logger("ingestion-pipeline")


def ingest_file_to_pipeline(source_file: Path) -> Dict[str, Any]:
    """
    Ingests a newly uploaded PDF/DOCX file:
    1. Stages file in data/uploads/
    2. Runs Docling extraction to data/extracted/
    3. Triggers structure-aware chunking
    4. Embeds new chunks and updates ChromaDB collection 'medical_guidelines'
    """
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    target_upload_path = settings.UPLOADS_PATH / source_file.name
    if source_file.resolve() != target_upload_path.resolve():
        shutil.copy2(source_file, target_upload_path)

    logger.info(f"Staged {source_file.name} to {target_upload_path}")

    # Note: Full Docling conversion and embedding can be triggered via CLI script
    # or background task. For immediate status return:
    return {
        "status": "staged",
        "file_name": source_file.name,
        "destination": str(target_upload_path),
        "message": f"Document {source_file.name} successfully staged in guideline repository."
    }
