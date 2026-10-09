"""
Pydantic Schemas for Retrieval and Reranking.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EvidenceSource(BaseModel):
    chunk_id: str
    document_name: str
    disease: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    rank: Optional[int] = None
    distance: Optional[float] = None
    content: Optional[str] = None


class RetrievalQueryRequest(BaseModel):
    question: str = Field(..., description="Clinical query string")
    disease: Optional[str] = Field(None, description="'diabetes' or 'respiratory_viral_infection'")
    top_k: int = Field(5, ge=1, le=50, description="Top-K results after reranking")
    relevant_chunk_ids: Optional[List[str]] = Field(default_factory=list)
    expected_pages: Optional[List[int]] = Field(default_factory=list)
    pass_k_threshold: int = Field(5, description="Pass/fail cutoff for evaluation")


class RetrievalResponse(BaseModel):
    query: str
    disease: Optional[str] = None
    top_k: int
    retrieved_chunks: List[EvidenceSource]
    total_retrieved: int
    metrics: Optional[Dict[str, Any]] = None
