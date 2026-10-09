"""
Retrieval & Vector Search API Endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException

from app.rag.retrieval import get_retrieval_service
from app.schemas.retrieval import (
    RetrievalQueryRequest,
    RetrievalResponse,
    EvidenceSource
)

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])
retrieval_service = get_retrieval_service()


@router.post("/search", response_model=RetrievalResponse)
def search_evidence(payload: RetrievalQueryRequest):
    """
    Retrieves and reranks Top-K guideline chunks using the 70% Semantic + 30% Lexical pipeline.
    """
    try:
        chunks = retrieval_service.retrieve(
            query=payload.question,
            disease=payload.disease,
            top_k=payload.top_k
        )

        evidence_sources = [
            EvidenceSource(
                chunk_id=c.get("chunk_id", ""),
                document_name=c.get("document_name", ""),
                disease=c.get("disease"),
                section=c.get("section"),
                page=c.get("page"),
                rank=c.get("rank"),
                distance=c.get("distance"),
                content=c.get("content")
            )
            for c in chunks
        ]

        return RetrievalResponse(
            query=payload.question,
            disease=payload.disease,
            top_k=payload.top_k,
            retrieved_chunks=evidence_sources,
            total_retrieved=len(evidence_sources)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(exc)}")


@router.get("/chunks/{chunk_id}")
def get_chunk_detail(chunk_id: str):
    """Retrieves full chunk metadata and content by ID."""
    chunk = retrieval_service.get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found in knowledge base.")
    return chunk
