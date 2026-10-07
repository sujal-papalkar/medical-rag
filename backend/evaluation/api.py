"""
FastAPI Server for RAG Retrieval Evaluation Dashboard.
Exposes endpoints for running evaluations, querying test cases, managing the draft golden dataset,
and testing custom questions with disease-specific retrieval.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure imports resolve cleanly
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.evaluator import RAGEvaluator, DATASET_PATH, DEFAULT_OUTPUT_PATH
from evaluation.retrieval_service import get_retrieval_service
from evaluation.metrics import calculate_query_metrics

app = FastAPI(
    title="RAG Retrieval Evaluation API",
    description="Phase 1: Disease-Specific Retrieval Evaluation for Medical Guidelines RAG Knowledge Base",
    version="1.0.0"
)

# Enable CORS for frontend Vite dev server (and common local ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluator = RAGEvaluator()
retrieval_service = get_retrieval_service()


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class CustomQueryRequest(BaseModel):
    question: str = Field(..., description="The query string to retrieve chunks for")
    disease: Optional[str] = Field(None, description="Disease filter: 'diabetes' or 'respiratory_viral_infection'")
    top_k: int = Field(10, ge=1, le=50, description="Number of results to retrieve")
    relevant_chunk_ids: Optional[List[str]] = Field(default_factory=list, description="Ground truth chunk IDs for evaluation")
    expected_pages: Optional[List[int]] = Field(default_factory=list, description="Ground truth expected pages")
    pass_k_threshold: int = Field(5, description="K cutoff for pass/fail (default: 5)")


class EvaluateRunRequest(BaseModel):
    top_k: int = Field(10, ge=1, le=50, description="Top K chunks to retrieve (default: 10)")
    disease: Optional[str] = Field(None, description="Optional filter by disease")
    pass_k_threshold: int = Field(5, description="K cutoff for pass/fail (default: 5)")


class VerifyTestCaseRequest(BaseModel):
    test_id: str
    verified: bool
    verification_notes: Optional[str] = None
    relevant_chunk_ids: Optional[List[str]] = None
    expected_pages: Optional[List[int]] = None


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "phase": 1,
        "module": "disease_specific_retrieval_evaluation",
        "collection": "medical_guidelines",
        "model": "gemini-embedding-001"
    }


@app.get("/api/dataset")
def get_dataset():
    """Returns the DRAFT Golden Dataset and its metadata."""
    try:
        data = evaluator.load_dataset()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/dataset/verify")
def update_test_case_verification(payload: VerifyTestCaseRequest):
    """Updates verification status and optional ground truth notes for a test case."""
    try:
        data = evaluator.load_dataset()
        cases = data.get("test_cases", [])
        target = None
        for c in cases:
            if c["test_id"] == payload.test_id:
                target = c
                break

        if not target:
            raise HTTPException(status_code=404, detail=f"Test case {payload.test_id} not found")

        target["verified"] = payload.verified
        if payload.verification_notes is not None:
            target["verification_notes"] = payload.verification_notes
        if payload.relevant_chunk_ids is not None:
            target["relevant_chunk_ids"] = payload.relevant_chunk_ids
        if payload.expected_pages is not None:
            target["expected_pages"] = payload.expected_pages

        # Check if all verified
        all_verified = all(c.get("verified", False) for c in cases)
        if all_verified:
            data["metadata"]["status"] = "VERIFIED"
            data["metadata"]["is_draft"] = False
        else:
            data["metadata"]["status"] = "DRAFT"
            data["metadata"]["is_draft"] = True

        with DATASET_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        evaluator.dataset = data
        return {"status": "success", "test_case": target, "dataset_status": data["metadata"]["status"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/evaluate/run")
def run_evaluation(payload: EvaluateRunRequest):
    """
    Executes full retrieval evaluation across the Golden Dataset.
    Calculates Recall@1,3,5,10, Precision@1,3,5,10, Hit@1,3,5,10, MRR, F1@5, F1@10.
    Returns overall metrics, disease breakdown, and full test cases with retrieved chunks.
    """
    try:
        report = evaluator.evaluate_all(
            top_k=payload.top_k,
            disease_filter=payload.disease,
            pass_k_threshold=payload.pass_k_threshold
        )
        evaluator.save_report(report)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.get("/api/evaluate/latest")
def get_latest_evaluation():
    """Returns the most recently saved evaluation report if available, else runs evaluation."""
    if DEFAULT_OUTPUT_PATH.exists():
        try:
            with DEFAULT_OUTPUT_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # If not yet saved or corrupt, run fresh
    return run_evaluation(EvaluateRunRequest(top_k=10, pass_k_threshold=5))


@app.post("/api/evaluate/custom")
def evaluate_custom_query(payload: CustomQueryRequest):
    """
    Accepts any test question, applies disease-specific retrieval logic,
    and returns retrieved chunks with rank, distance, chunk_id, document_name,
    page, disease, content_type, and content.
    If ground truth chunk IDs are provided, calculates exact IR metrics.
    """
    try:
        retrieved_chunks = retrieval_service.retrieve(
            query=payload.question,
            disease=payload.disease,
            top_k=payload.top_k
        )

        relevant_set = set(payload.relevant_chunk_ids or [])
        expected_pages = payload.expected_pages or []

        # Annotate retrieved
        annotated = []
        for c in retrieved_chunks:
            c_dict = dict(c)
            c_dict["is_relevant"] = c_dict["chunk_id"] in relevant_set if relevant_set else None
            c_dict["page_matches"] = c_dict.get("page") in expected_pages if expected_pages else None
            annotated.append(c_dict)

        metrics = None
        if relevant_set:
            retrieved_ids = [c["chunk_id"] for c in retrieved_chunks]
            metrics = calculate_query_metrics(
                retrieved_chunk_ids=retrieved_ids,
                relevant_chunk_ids=payload.relevant_chunk_ids,
                pass_k_threshold=payload.pass_k_threshold
            )

        return {
            "question": payload.question,
            "disease": payload.disease,
            "top_k": payload.top_k,
            "relevant_chunk_ids": payload.relevant_chunk_ids,
            "expected_pages": payload.expected_pages,
            "metrics": metrics,
            "retrieved_chunks": annotated,
            "total_retrieved": len(annotated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chunks/{chunk_id}")
def get_chunk_detail(chunk_id: str):
    """Retrieves full chunk details and metadata by ID."""
    chunk = retrieval_service.get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found in knowledge base")
    return chunk


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("evaluation.api:app", host="0.0.0.0", port=8000, reload=True)
