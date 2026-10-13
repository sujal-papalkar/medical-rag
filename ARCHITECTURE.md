# System Architecture: Grounded Ayurvedic Clinical Prescription RAG

This document details the end-to-end system architecture of the **Ayurvedic Clinical Prescription RAG** platform. The system is designed to provide registered Ayurvedic physicians with clinical decision support and strictly grounded prescription formulation derived from verified medical guidelines, with zero tolerance for clinical hallucinations.

---

## 1. High-Level System Architecture

The system follows a modular architecture separating presentation, API routing, safety verification, retrieval, grounded LLM generation, and persistent vector storage.

```mermaid
flowchart TD
    subgraph ClientLayer ["1. Presentation Layer (Frontend)"]
        UI_Rx["Prescription Workbench<br/>(PrescriptionPage.tsx)"]
        UI_Patients["Patient Profiles & Scenarios<br/>(PatientsPage.tsx)"]
        UI_Docs["Knowledge Base Manager<br/>(DocumentsPage.tsx)"]
        UI_Header["Clinical Navigation & Status<br/>(Header.tsx)"]
    end

    subgraph APILayer ["2. API & Routing Gateway (FastAPI)"]
        Router["Aggregated API v1 Router<br/>(router.py)"]
        EP_Rx["/api/v1/prescriptions<br/>(prescriptions.py)"]
        EP_Patients["/api/v1/patients<br/>(patients.py)"]
        EP_Docs["/api/v1/documents<br/>(documents.py)"]
        EP_Ret["/api/v1/retrieval<br/>(retrieval.py)"]
        EP_Health["/api/v1/health<br/>(health.py)"]
    end

    subgraph SafetyLayer ["3. Clinical Intelligence & Safety Gating"]
        ConflictEngine["Universal Conflict Resolver<br/>(conflict_resolver.py)"]
        ClinicalMatcher["Biomarker & Table Matcher<br/>(clinical_matcher.py)"]
        GroundingRules["14 Negative Clinical Rules<br/>(grounding.py)"]
    end

    subgraph RAGLayer ["4. Retrieval & Generation Pipeline"]
        RetService["Candidate Retrieval Service<br/>(retrieval.py)"]
        Reranker["Composite Reranker<br/>70% Semantic + 30% Lexical<br/>(reranking.py)"]
        GenEngine["Multi-Candidate Generator<br/>(generation.py)"]
        PydanticValidator["Pydantic v2 Schema Validator<br/>(schemas/prescriptions.py)"]
    end

    subgraph StorageLayer ["5. Storage & Knowledge Base"]
        ChromaDB[("ChromaDB Vector Store<br/>collection: 'medical_guidelines'<br/>(chroma_db/)")]
        DocRepo["Document & Chunk Repositories<br/>(data/chunks/chunks.json)"]
        PatientRepo["Verified Patient Store<br/>(repositories.py)"]
    end

    subgraph ExternalServices ["6. Foundation Model APIs"]
        GeminiEmbed["Google Gemini Embeddings<br/>(gemini-embedding-001 / 768d)"]
        GeminiLLM["Google Gemini Generative Models<br/>(gemini-3.5-flash-lite + Cascade)"]
    end

    %% User Interactions
    UI_Rx --> Router
    UI_Patients --> Router
    UI_Docs --> Router

    %% Routing
    Router --> EP_Rx
    Router --> EP_Patients
    Router --> EP_Docs
    Router --> EP_Ret
    Router --> EP_Health

    %% Prescription Flow
    EP_Rx --> ConflictEngine
    EP_Patients --> PatientRepo
    EP_Docs --> DocRepo

    ConflictEngine -->|Parameters Verified| ClinicalMatcher
    ConflictEngine -->|Conflict Detected & Unconfirmed| EP_Rx
    ClinicalMatcher --> RetService

    %% Retrieval Subsystem
    RetService --> GeminiEmbed
    RetService -->|Query Vector + Metadata Filter| ChromaDB
    ChromaDB -->|Top-20 Candidates| Reranker
    Reranker -->|Top-K Evidence Chunks| GenEngine

    %% Generation Subsystem
    ClinicalMatcher -->|Isolated Table Context| GenEngine
    GroundingRules --> GenEngine
    GenEngine --> GeminiLLM
    GeminiLLM -->|Candidate Responses| PydanticValidator
    PydanticValidator -->|StructuredPrescriptionResponse| EP_Rx
```

---

## 2. End-to-End Clinical Prescription Lifecycle

This diagram illustrates the clinical dataflow from physician interaction to validated prescription delivery, including safety gating and grounded generation.

```mermaid
sequenceDiagram
    autonumber
    actor Physician as Ayurvedic Physician
    participant UI as React Frontend
    participant API as FastAPI (/api/v1/prescriptions)
    participant Conflict as Conflict Resolver
    participant Matcher as Clinical Matcher
    participant Retrieval as Retrieval Service
    participant Chroma as ChromaDB Persistent Store
    participant Reranker as Composite Reranker (70/30)
    participant Gemini as Gemini LLM Service
    participant Validator as Pydantic Validator

    Physician->>UI: Selects Patient (or inputs clinical query)
    UI->>API: POST /generate {query, patient_id, confirm_override}
    API->>Conflict: resolve_clinical_context(patient_record, query)

    alt Parameter Conflict Detected & confirm_override == False
        Conflict-->>API: Return ClinicalConflict (demographic, comorbidity, severity)
        API-->>UI: 200 OK {has_conflict: true, conflicts: [...], requires_confirmation: true}
        UI-->>Physician: Displays Conflict Interlock Modal (Demands explicit confirmation)
    else Parameters Aligned or confirm_override == True
        Conflict-->>API: Conflict Resolution Approved
        API->>Matcher: extract_clinical_profile(query, patient_record)
        Matcher->>Matcher: Extract biomarkers (Age, HRCT, SpO2, Comorbidities)
        
        API->>Retrieval: retrieve_evidence(query, disease, top_k=20)
        Retrieval->>Chroma: Dense query (gemini-embedding-001 vector, where={'disease': disease})
        Chroma-->>Retrieval: Return Top-20 candidate chunks
        
        Retrieval->>Reranker: rerank_candidates(candidates, query)
        Reranker->>Reranker: Compute S_semantic (distance) + S_lexical (unigrams, bigrams, clinical terms)
        Reranker->>Reranker: S_final = 0.70 * S_semantic + 0.30 * S_lexical
        Reranker-->>Retrieval: Top-5 highest ranked evidence chunks
        
        Retrieval->>Matcher: prioritize_and_isolate_chunks(top_chunks, clinical_profile)
        Matcher-->>Retrieval: Filtered & table-isolated evidence context
        
        Retrieval->>Gemini: Prompt with context + 14 strict negative grounding rules
        Gemini-->>Validator: Raw candidate JSON outputs (up to 3 candidates)
        
        Validator->>Validator: Validate schema (MedicineItem, ClinicalGuidance, Citations)
        Validator->>Matcher: sanitize_prescribed_medicines(validated_prescription)
        Matcher-->>Validator: Verified Matra, Sahpaan, Aushadh Kal & Page Citations
        
        Validator-->>API: StructuredPrescriptionResponse
        API-->>UI: 200 OK (Prescription, Evidence Sources, Limitations, Conflicts)
        UI-->>Physician: Render Clinical Guidance, Medicine Cards, Exact Page Citations
    end
```

---

## 3. Document Ingestion & Knowledge Indexing Pipeline

The offline and asynchronous guideline ingestion pipeline transforms heterogeneous clinical documents into persistent, structured vector embeddings while preserving physical page provenance.

```mermaid
flowchart LR
    subgraph InputStage ["1. Document Ingestion"]
        DocPDF["Clinical Guideline PDF<br/>(Respiratory Protocol)"]
        DocDOCX["Clinical Guideline DOCX<br/>(DM RR.docx)"]
    end

    subgraph PreprocessingStage ["2. Preprocessing & Extraction"]
        LibreOffice["Headless LibreOffice<br/>(soffice --convert-to pdf)"]
        Docling["Docling Parser<br/>(DocumentConverter)"]
        ProvTracker["Physical Page Provenance<br/>(item.prov.page_no -> markers)"]
        TableExtractor["Tabular Matrix Parser<br/>(DataFrames with headers)"]
    end

    subgraph ChunkingStage ["3. Structure-Aware Chunking"]
        HeadingSplitter["Section & Subsection Splitter"]
        TableRowChunker["Table Row Splitter<br/>(Preserves Column Headers)"]
        BreadcrumbInjector["Breadcrumb Prepending<br/>[Doc > Section > Subsection]"]
        BoilerplateCleaner["Boilerplate & Noise Filter<br/>(Strips repetitive disclaimers)"]
        HashIdGen["Deterministic ID Generator<br/>(DOC-hash-index-contenthash)"]
    end

    subgraph IndexingStage ["4. Storage & Vector Indexing"]
        JSONOutput[("Structured JSON Files<br/>chunks.json & chunk_summary.json")]
        EmbedAPI["Google GenAI Embeddings<br/>gemini-embedding-001 (768d)"]
        ChromaStore[("Persistent ChromaDB<br/>collection: medical_guidelines")]
    end

    DocDOCX --> LibreOffice
    LibreOffice --> DocPDF
    DocPDF --> Docling

    Docling --> ProvTracker
    Docling --> TableExtractor

    ProvTracker --> HeadingSplitter
    TableExtractor --> TableRowChunker

    HeadingSplitter --> BreadcrumbInjector
    TableRowChunker --> BreadcrumbInjector
    BreadcrumbInjector --> BoilerplateCleaner
    BoilerplateCleaner --> HashIdGen

    HashIdGen --> JSONOutput
    JSONOutput --> EmbedAPI
    EmbedAPI --> ChromaStore
```

---

## 4. Two-Stage Hybrid Retrieval & Reranking Architecture

The retrieval system addresses the *"semantic sponge"* vulnerability (where short section titles or repetitive footers outrank dense informational tables in pure bi-encoder dense space) by utilizing a two-stage hybrid retrieval strategy.

```mermaid
flowchart TD
    Query["Physician Clinical Query<br/>+ Patient Disease Context"] --> EmbedQuery["Gemini Embeddings<br/>gemini-embedding-001"]
    
    subgraph Stage1 ["Stage 1: Dense Vector Retrieval (Over-fetching)"]
        EmbedQuery --> ChromaQuery["ChromaDB Vector Query<br/>where={'disease': disease}<br/>n_results = 20"]
        ChromaQuery --> CandidatePool["20 Candidate Evidence Chunks"]
    end

    subgraph Stage2 ["Stage 2: Deterministic Composite Reranking (CPU-Friendly)"]
        CandidatePool --> ScoreSem["Semantic Score Calculation<br/>S_semantic = 1.0 / (1.0 + max(distance, 0.0))"]
        CandidatePool --> ScoreLex["Composite Lexical Scoring<br/>S_lexical = 0.45*unigrams + 0.35*bigrams + 0.20*phrases"]
        
        ScoreSem --> WeightedFormula["Hybrid Score Interpolation<br/>S_final = 0.70 * S_semantic + 0.30 * S_lexical"]
        ScoreLex --> WeightedFormula
        
        WeightedFormula --> TieBreaker["Deterministic Tie-Breaking<br/>Sort key: (-S_final, distance, chunk_id)"]
    end

    subgraph OutputStage ["Stage 3: Evidence Selection & Grounding Context"]
        TieBreaker --> TopKSlice["Top-K Candidate Selection<br/>(Top-5 for Generation, Top-10 for Evaluation)"]
        TopKSlice --> GroundedContext["Authoritative Grounding Context Block"]
    end
```

### Reranking Scoring Formulas

$$\text{Semantic Score} = \frac{1.0}{1.0 + \max(\text{cosine\_distance}, 0.0)}$$

$$\text{Lexical Score} = 0.45 \cdot \text{Unigram Overlap} + 0.35 \cdot \text{Bigram Overlap} + 0.20 \cdot \text{Clinical Phrase Matches}$$

$$\text{Final Score} = 0.70 \cdot \text{Semantic Score} + 0.30 \cdot \text{Lexical Score}$$

*Benchmark Performance*: Achieved **100% Hit@5**, **100% Recall@5**, and **1.0000 MRR** across the 20 benchmark clinical scenarios with sub-5ms CPU latency.

---

## 5. Universal Clinical Conflict Detection & Safety Gating

The conflict engine prevents medical hallucination or silent profile overwrites by treating registered patient profiles as authoritative for patient demographics while treating the physician query as the desired presentation.

```mermaid
stateDiagram-v2
    [*] --> ParseInputs: Request Received (query, patient_id)

    ParseInputs --> CompareParameters: Extract Age, Disease, Severity, Comorbidities
    
    state CompareParameters {
        [*] --> CheckDemographics
        CheckDemographics --> CheckDisease
        CheckDisease --> CheckSeverity
        CheckSeverity --> CheckComorbidities
    }

    CompareParameters --> NoConflictFound: Parameters Match
    CompareParameters --> ConflictIdentified: Parameter Discrepancy Found

    state ConflictIdentified {
        [*] --> DemographicMismatch
        [*] --> DiseaseMismatch
        [*] --> SeverityContradiction
        [*] --> UnregisteredComorbidity
    }

    ConflictIdentified --> CheckOverrideFlag: Inspect confirm_override Flag

    CheckOverrideFlag --> BlockExecution: confirm_override == False
    BlockExecution --> [*]: Return 200 OK with conflicts & suggested resolution

    CheckOverrideFlag --> LogAndProceed: confirm_override == True
    LogAndProceed --> AuditLog: Record Physician Override in Audit Trail
    AuditLog --> NoConflictFound: Resolved Parameters Passed to Pipeline

    NoConflictFound --> ExecuteRAG: Proceed to Retrieval & Generation
    ExecuteRAG --> [*]: Return Validated Prescription
```

---

## 6. Evaluation & Benchmarking Architecture

The project features automated, deterministic evaluation pipelines for both Information Retrieval (IR) and Grounded Generation, without reliance on subjective LLM-as-a-judge scoring.

```mermaid
flowchart TD
    subgraph BenchmarkInputs ["Golden Benchmark Datasets"]
        RetDataset["retrieval_golden_dataset.json<br/>(20 Clinical Scenarios)"]
        GenGroundTruth["generation_ground_truth.json<br/>(Clinical Ground Truth Prescriptions)"]
    end

    subgraph IREvalEngine ["Information Retrieval (IR) Evaluator"]
        RunnerIR["retrieval_evaluator.py"]
        MetricHit["Hit@1, Hit@3, Hit@5, Hit@10"]
        MetricRecall["Recall@1, Recall@3, Recall@5, Recall@10"]
        MetricPrecision["Precision@1, Precision@3, Precision@5, Precision@10"]
        MetricMRR["MRR (Mean Reciprocal Rank)"]
        MetricF1["F1@5 and F1@10"]
    end

    subgraph GenEvalEngine ["Grounded Generation Evaluator"]
        RunnerGen["generation_evaluator.py"]
        MetricComp["Component Completeness<br/>(Medicine, Matra, Sahpaan, Aushadh Kal)"]
        MetricClaim["Claim-Level Grounding<br/>(Verifies claims against source chunks)"]
        MetricHallucination["Hallucination Detection<br/>(Zero tolerance for ungrounded formulations)"]
        MetricSource["Source & Page Citation Accuracy"]
        MetricAbsence["Absence Verification<br/>(Limits statements for missing data)"]
    end

    subgraph EvaluationReports ["Exported Evaluation Artifacts"]
        ReportRet["evaluation_report.json<br/>(IR Benchmark Performance)"]
        ReportDiag["retrieval_diagnosis_report.md<br/>(Systematic Failure Taxonomy)"]
        ReportGen["generation_eval_report.json<br/>(Generation Adherence Summary)"]
    end

    RetDataset --> RunnerIR
    RunnerIR --> MetricHit & MetricRecall & MetricPrecision & MetricMRR & MetricF1
    MetricHit & MetricRecall & MetricPrecision & MetricMRR & MetricF1 --> ReportRet
    ReportRet --> ReportDiag

    GenGroundTruth --> RunnerGen
    RunnerGen --> MetricComp & MetricClaim & MetricHallucination & MetricSource & MetricAbsence
    MetricComp & MetricClaim & MetricHallucination & MetricSource & MetricAbsence --> ReportGen
```

---

## 7. Component & Directory Mapping

The table below maps each architectural layer to its corresponding codebase implementation, technologies, and responsibilities.

| Layer | Codebase Location | Primary Technologies | Key Responsibilities |
|---|---|---|---|
| **Presentation (UI)** | [`frontend/src/`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/frontend/src) | React 19, TypeScript, Vite, Tailwind/Vanilla CSS | Physician prescription workbench, patient profile picker, document management, and evaluation dashboard. |
| **API Gateway** | [`backend/app/api/v1/`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/api/v1) | FastAPI, Pydantic v2, Uvicorn | REST routing for `/prescriptions`, `/patients`, `/documents`, `/retrieval`, and `/health`. |
| **Configuration** | [`backend/app/core/config.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/core/config.py) | Pydantic Settings, `python-dotenv` | Centralized absolute filesystem path resolution and environment variable management. |
| **Document Processing** | [`backend/app/rag/extraction.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/extraction.py) | Docling, LibreOffice headless | High-fidelity extraction of PDF and DOCX guidelines with bounding box page provenance. |
| **Structure Chunking** | [`backend/app/rag/chunking.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/chunking.py) | Python regex, `hashlib` | Structure-aware chunking preserving tables, prepending breadcrumbs, and filtering boilerplate. |
| **Vector Storage** | [`backend/app/database/connection.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/database/connection.py) | ChromaDB PersistentClient | Singleton management for persistent vector collection `medical_guidelines`. |
| **Retrieval Service** | [`backend/app/rag/retrieval.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/retrieval.py) | Google GenAI SDK (`gemini-embedding-001`) | Query embedding, over-fetched Top-20 vector search, disease partition filtering. |
| **Composite Reranker** | [`backend/app/rag/reranking.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/reranking.py) | Rank-BM25, Python Standard Math | 70% Semantic + 30% Lexical scoring with deterministic tie-breaking. |
| **Clinical Matcher** | [`backend/app/rag/clinical_matcher.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/clinical_matcher.py) | Regular Expressions, Dataclasses | Objective biomarker parsing (SpO2, HRCT, Age), table isolation, and medicine sanitization. |
| **Conflict Resolver** | [`backend/app/rag/conflict_resolver.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/conflict_resolver.py) | Pydantic v2 | Universal clinical parameter conflict detection and physician confirmation gating. |
| **Grounded Generation** | [`backend/app/rag/generation.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/generation.py) | Gemini GenAI API (`gemini-3.5-flash-lite`) | Multi-candidate LLM generation with exponential backoff and model fallback cascade. |
| **Grounding Rules** | [`backend/app/rag/grounding.py`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/app/rag/grounding.py) | Prompt Engineering | 14 strict negative clinical constraints preventing medical hallucination. |
| **Evaluation Suite** | [`backend/evaluation/`](file:///c:/Users/Sujal Papalkar/Desktop/prescription/backend/evaluation) | Custom Python evaluators, JSON datasets | Deterministic IR metrics (Recall, Precision, Hit, MRR) and claim-level generation evaluation. |

---

## 8. Technology Stack Summary

```
+-----------------------------------------------------------------------------------------+
|                                    TECHNOLOGY STACK                                     |
+-------------------+---------------------------------------------------------------------+
| Frontend          | React 19.2, TypeScript 6, Vite 8, Lucide React, Oxlint, Vanilla CSS |
| Backend API       | Python 3.10+, FastAPI 0.110+, Uvicorn 0.28+, Pydantic v2 2.6+       |
| Document Parsing  | Docling 2.0+, LibreOffice (soffice headless), pandas                |
| Vector Store      | ChromaDB 0.4.22+ (Persistent embedded storage)                      |
| Embedding Model   | Google GenAI gemini-embedding-001 (768 dimensions)                  |
| Generation Models | Google GenAI gemini-3.5-flash-lite (Primary)                        |
|                   | Fallbacks: gemini-3.8-flash, gemini-3.7-flash, gemini-3.1-flash-lite|
| Lexical Search    | Rank-BM25 (BM25Okapi with unigram/bigram tokenization)              |
| Testing & Bench   | Python unittest, custom deterministic IR & claim-level evaluators   |
+-------------------+---------------------------------------------------------------------+
```
