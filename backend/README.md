# Ayurvedic Clinical Prescription RAG Backend

Production-oriented Retrieval-Augmented Generation (RAG) backend for Ayurvedic clinical decision support and grounded prescription formulation.

## Target Architecture

```
backend/
├── app/
│   ├── main.py                     # Modular FastAPI application entrypoint
│   ├── api/v1/                     # Versioned API routes (health, documents, patients, retrieval, prescriptions)
│   ├── core/                       # Centralized configuration (config.py) and structured logging (logging.py)
│   ├── rag/                        # Ingestion, extraction, chunking, retrieval, 70/30 reranking, generation, grounding
│   ├── database/                   # ChromaDB connection singleton and repositories
│   └── schemas/                    # Strict Pydantic schemas (MedicineItem, ClinicalGuidance, StructuredPrescriptionResponse)
│
├── evaluation/
│   ├── datasets/                   # Golden benchmark datasets (retrieval_golden_dataset, generation_ground_truth)
│   ├── evaluators/                 # Retrieval and generation evaluators
│   ├── metrics.py                  # Standard IR & generation evaluation metrics
│   └── reports/                    # Benchmark JSON reports
│
├── tests/
│   ├── unit/                       # Unit tests (extraction, chunking, retrieval, reranking, grounding, generation)
│   └── integration/                # Integration tests (ingestion, retrieval pipeline, prescription pipeline)
│
├── scripts/
│   ├── ingest_documents.py         # Batch guideline ingestion CLI
│   ├── run_retrieval_eval.py       # 20-case retrieval evaluation runner
│   └── run_generation_eval.py      # Generation evaluation runner
│
├── data/
│   ├── uploads/                    # Uploaded guideline documents
│   ├── extracted/                  # Docling extracted markdown / JSON
│   └── chunks/                     # Structured chunk outputs
│
├── chroma_db/                      # Persistent vector store (131 vectors in 'medical_guidelines')
└── logs/                           # Runtime service logs
```

## Retrieval Pipeline

1. **Embedding**: `gemini-embedding-001` (768 dimensions).
2. **ChromaDB**: Top-20 candidate retrieval from collection `medical_guidelines`.
3. **Composite Reranker**:
   - `semantic_score = 1.0 / (1.0 + max(distance, 0.0))`
   - `lexical_score = 0.45 * overlap + 0.35 * bigrams + 0.20 * phrase_matches`
   - `final_score = 0.70 * semantic_score + 0.30 * lexical_score`
   - Achieves 100% Hit@5, 100% Recall@5, and 1.0000 MRR on the 20 golden scenarios.
4. **Grounded Generation**: Gemini LLM constrained by 14 strict negative clinical grounding rules, producing strictly validated Pydantic JSON responses.

## Quickstart

```bash
# Run unit and integration tests
python -m unittest discover -s tests/unit
python -m unittest discover -s tests/integration

# Run 20-case retrieval evaluation benchmark
python scripts/run_retrieval_eval.py --top-k 5

# Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
