"""
Pydantic Schemas for Document Ingestion and Management.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    id: str
    name: str
    disease_category: str
    uploaded_at: str
    chunks_indexed: int = 0
    status: str = "Indexed"  # Indexed | Staged | Processing
    description: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    status: str
    message: str
    document: DocumentInfo


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentInfo]
