# Medical RAG Retrieval Evaluation System
## Phase 1: Disease-Specific Retrieval Benchmarking

An evaluation module and modern frontend dashboard for benchmarking retrieval performance on clinical guideline documents without modifying the underlying ingestion, chunking, embedding, ChromaDB, or retrieval pipelines.

---

### Key Capabilities

1. **DRAFT Golden Dataset (10 Test Cases)**:
   - 5 Diabetes Mellitus cases (from `DM RR.md`)
   - 5 Respiratory Viral Infection cases (from `Respiratory Viral Infection Management protocol`)
   - Generated strictly from actual existing chunks in `backend/chunked_output/chunks.json`.
   - Each case includes `test_id`, `question`, `disease`, `relevant_chunk_ids`, and `expected_pages`.
   - Flagged with `status: "DRAFT"` to support manual expert verification before signing off.

2. **Deterministic IR Metrics (No LLM Judging)**:
   - **Hit@1, @3, @5, @10**: Whether at least one ground-truth chunk is retrieved in top $K$.
   - **Recall@1, @3, @5, @10**: Fraction of ground-truth chunks retrieved in top $K$.
   - **Precision@1, @3, @5, @10**: Fraction of top $K$ retrieved chunks that belong to ground truth.
   - **MRR (Mean Reciprocal Rank)**: $1 / \text{rank}$ of the first relevant chunk.
   - **F1@5 and F1@10**: Harmonic mean of Precision and Recall at cutoffs 5 and 10.
   - Aggregated metrics across overall dataset and split by disease (Diabetes vs Respiratory).

3. **FastAPI Backend Evaluation API**:
   - `GET /api/dataset`: Fetch golden dataset with verification flags.
   - `PUT /api/dataset/verify`: Update test case verification status or ground-truth chunk IDs.
   - `POST /api/evaluate/run`: Run evaluation across all 10 test cases or filtered subset.
   - `POST /api/evaluate/custom`: Run custom clinical question retrieval and instant evaluation.
   - `GET /api/evaluate/latest`: Fetch the latest cached evaluation report.
   - `GET /api/chunks/{chunk_id}`: Inspect full chunk content from `chunks.json`.

4. **React + TypeScript + Vite Dashboard**:
   - High-contrast clinical obsidian dark theme with glassmorphism cards.
   - Summary Metric Cards (Pass Rate, MRR, Hit@k, Recall@k, F1@5/10).
   - Disease Comparison module (Diabetes vs Respiratory side-by-side).
   - Filterable Test Case List (by disease and pass/fail status).
   - Ground Truth vs Retrieved Chunks Inspector modal with rank, cosine distance, document, page, and full text.
   - Interactive Query Playground to test any arbitrary clinical question in real-time.
   - Export evaluation report to JSON.

---

### Project Structure

```
prescription/
├── backend/
│   ├── chunked_output/
│   │   └── chunks.json             # 147 guideline chunks (79 diabetes, 68 respiratory)
│   ├── chroma_db/                  # ChromaDB vector store
│   ├── evaluation/                 # Separate evaluation module
│   │   ├── __init__.py
│   │   ├── draft_golden_dataset.json # 10 test cases with draft metadata
│   │   ├── metrics.py              # Recall, Precision, Hit, MRR, F1 calculations
│   │   ├── retrieval_service.py    # Reuses pipeline retrieval without pipeline modification
│   │   ├── evaluator.py            # Orchestrator & report generator
│   │   ├── api.py                  # FastAPI REST endpoints
│   │   └── run_eval.py             # CLI runner script
│   ├── retrieval_results/
│   │   └── evaluation_report.json  # Exported evaluation run
│   └── ... (existing pipeline files untouched)
│
├── frontend/                       # React + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── DraftBanner.tsx
│   │   │   ├── MetricCards.tsx
│   │   │   ├── DiseaseComparison.tsx
│   │   │   ├── TestCasesList.tsx
│   │   │   ├── TestCaseDetailModal.tsx
│   │   │   ├── InteractivePlayground.tsx
│   │   │   └── RawReportModal.tsx
│   │   ├── types.ts
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── main.tsx
│   └── package.json
│
├── package.json                    # Root proxy package.json
└── README.md
```

---

### Quick Start Guide

#### 1. Run Evaluation from the Command Line (CLI)

To run the benchmark directly in your terminal and view the formatted metrics table:

```powershell
# From project root
.\.venv\Scripts\python.exe backend/evaluation/run_eval.py
```

Options:
- `--top-k 10`: Set retrieval depth (default 10)
- `--pass-k 5`: Set pass threshold cutoff (default 5)
- `--disease diabetes`: Filter by disease (`diabetes` or `respiratory_viral_infection`)

---

#### 2. Start the Backend API Server

```powershell
# Option A: From backend folder
cd backend
..\.venv\Scripts\python.exe -m uvicorn evaluation.api:app --host 127.0.0.1 --port 8000 --reload

# Option B: From project root
.\.venv\Scripts\python.exe -m uvicorn backend.evaluation.api:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at:
- **API URL**: `http://127.0.0.1:8000`
- **Swagger Documentation**: `http://127.0.0.1:8000/docs`

---

#### 3. Start the Frontend Dashboard

```powershell
# From project root:
npm run dev

# Or from frontend folder:
cd frontend
npm run dev
```

Open your browser at:
`http://localhost:5173`

---

### Golden Dataset Test Cases Summary

| Test ID | Disease | Topic | Ground Truth Chunk ID | Page |
|---|---|---|---|---|
| **TC-DM-001** | Diabetes | Trushna (Polydipsia) & Aruchi Treatment | `DOC-5FFD839CD910-0021-3901824EC224` | 8 |
| **TC-DM-002** | Diabetes | Primary Prevention (BMI ≥ 25 & Family History) | `DOC-5FFD839CD910-0015-AE0DE713004C` | 6 |
| **TC-DM-003** | Diabetes | Diabetic Nephropathy with Hypertension | `DOC-5FFD839CD910-0041-39E7EECCDCBF` | 15 |
| **TC-DM-004** | Diabetes | Pramehaj Moorcha with Ketonuria | `DOC-5FFD839CD910-0058-22A9ECE2800D` | 19 |
| **TC-DM-005** | Diabetes | Diabetic Retinopathy (Early Stage) | `DOC-5FFD839CD910-0062-98492745B15B` | 20 |
| **TC-RESP-001** | Respiratory | Prophylaxis for Chronic Diabetes Comorbidity | `DOC-FC76496810AB-0023-B1552BEA40E2` | 8 |
| **TC-RESP-002** | Respiratory | Prophylaxis for Asthma/COPD on Inhalers | `DOC-FC76496810AB-0028-90983034990E` | 10 |
| **TC-RESP-003** | Respiratory | Pediatric Protocol (3–15 Years) | `DOC-FC76496810AB-0034-F189E813F7AB` | 13 |
| **TC-RESP-004** | Respiratory | Moderate Disease with Cardiac Comorbidity | `DOC-FC76496810AB-0038-BBE53C846B04`<br>`DOC-FC76496810AB-0039-D83493FAC8AF` | 15 |
| **TC-RESP-005** | Respiratory | Symptom Management (Tachycardia & High BP) | `DOC-FC76496810AB-0060-E039CFB9FEE7` | 22 |

> **Note on Verification**: All 10 cases are initialized in `DRAFT` status so you can review and sign off each question-to-chunk mapping directly from the UI or via `draft_golden_dataset.json`.
