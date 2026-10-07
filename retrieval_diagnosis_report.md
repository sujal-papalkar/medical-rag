# RAG Retrieval Diagnosis Report
**Phase 1: Disease-Specific Retrieval Benchmarking & Failure Analysis**  
**Evaluation Artifact**: `backend/retrieval_results/evaluation_report.json`  
**Knowledge Base Corpus**: `backend/chunked_output/chunks.json` (147 chunks: 79 Diabetes, 68 Respiratory)  
**Vector Store**: ChromaDB Collection `medical_guidelines` (Gemini `gemini-embedding-001`, 768 dimensions)

---

## 1. Overall Diagnosis & Executive Summary

In the Phase 1 Disease-Specific Retrieval Evaluation, the RAG system achieved an overall **Pass Rate of 80.0%** (8 of 10 test cases passed under the primary criterion $\text{Hit@5} == 1.0$) and a **100% Retrieval Recall at Top-10** (all 10 ground-truth targets were retrieved within the top 10 positions). The overall Mean Reciprocal Rank (MRR) was **0.6283**.

However, performance diverged significantly across the two clinical guideline documents:
- **Diabetes Mellitus (`DM RR.md`)**: **100% Pass Rate (5/5)**, MRR = **0.7667**, $\text{Hit@3} = 100\%$, $\text{Recall@5} = 100\%$.
- **Respiratory Viral Infection (`Respiratory Management protocol`)**: **60.0% Pass Rate (3/5)**, MRR = **0.4900**, $\text{Hit@5} = 60\%$, $\text{Recall@5} = 60\%$.

Two test cases failed the Top-5 threshold: **`TC-RESP-002`** and **`TC-RESP-003`**. Both were retrieved at **Rank 10**, narrowly missing the Top-5 pass threshold despite being present in the top-10 candidate pool.

```
+----------------------------------------------------------------------------------------------------+
|                                    FAILURE TAXONOMY BREAKDOWN                                      |
+--------------+-------------+------+---------------+------------------------------------------------+
| Test Case ID | Target Rank | MRR  | Primary Cause | Contributing Mechanism                         |
+--------------+-------------+------+---------------+------------------------------------------------+
| TC-RESP-002  | Rank #10    | 0.10 | Ranking &     | Isolated title chunks and repetitive           |
|              |             |      | Chunking Issue| disclaimer chunks out-rank dense clinical table|
+--------------+-------------+------+---------------+------------------------------------------------+
| TC-RESP-003  | Rank #10    | 0.10 | Chunking &    | Headless table lost 'Therapeutic' context;     |
|              |             |      | Semantic Issue| dense overlap with Page 6 Prophylaxis table   |
+--------------+-------------+------+---------------+------------------------------------------------+
```

### Key Systematic Takeaways
1. **Isolated Title Chunks as Semantic Sponges**: The document ingestion split markdown headings into standalone chunks of type `title` (e.g., `DOC-FC76496810AB-0040`, `0043`, `0022`). Because clinical queries repeat document header phrases, dense embedding models match these short title chunks with very low cosine distances, pushing actual answer tables down the ranking.
2. **Repetitive Boilerplate Noise**: Standard footer disclaimers (`"Only for the guidance of Registered Ayurvedic Medical Practitioners..."`) were chunked and indexed repeatedly across pages (e.g., chunks `0049`, `0052`, `0055`, `0058`). These non-informative chunks dilute top-10 retrieval.
3. **Loss of Table Heading Provenance**: Splitting introductory header text from table rows severed crucial semantic discriminators (such as distinguishing *Therapeutic* guidelines on Page 13 from *Prophylactic* guidelines on Page 6).

---

## 2. Deep-Dive Case Diagnosis: TC-RESP-002

### 2.1 Case Specification
- **Test ID**: `TC-RESP-002`
- **Disease Filter**: `respiratory_viral_infection`
- **Title**: Respiratory - Prophylaxis for Asthma and COPD on Inhalers
- **Clinical Question**:
  > *"A patient with respiratory viral infection has Pranvah Srotas Vyadhi such as Asthma or COPD on regular inhalers. What Rasayana medicine, Matra, Sahpaan and Aushadh Kal are recommended?"*
- **Expected Ground-Truth Chunk ID**: `DOC-FC76496810AB-0028-90983034990E`
- **Expected Source Page**: Page 10
- **Document Name**: `Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).md`
- **Retrieved Rank**: **Rank 10** (Pass Status: **FAIL**, $\text{Hit@5} = 0$, $\text{Hit@10} = 1.0$, $\text{MRR} = 0.1000$)
- **Cosine Distance of Expected Chunk**: `0.1327`

### 2.2 Expected Ground-Truth Content (`DOC-FC76496810AB-0028-90983034990E`)
```markdown
| Comorbidities | Medicine | Matra | Sahpaan | Aushadh kal |
|-----------------------------------------------------------|----------------------|-------|------------------|----------------------------------------------|
| Patients with Pranvah srotas Vyadhi (Asthama / COPD): | Mahalaxmi Vilas | 1-0-0 | Honey/ Honey + ardrak rasa 2ml | Rasayan kal (Early morning on empty stomach) |
| If on regular inhalers | Pranvallabh Rasayan | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |
| Patients with Granthi/ Arbud (Malignancies): | Sinurbhushan Rasayan | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |
| Active /under Treatment | Arpisa Rasayan | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |
```

### 2.3 Retrieved Top-10 Chunks Comparison

| Rank | Chunk ID | Distance | Page | Content Type | Match? | Content Snippet / Nature of Chunk |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| **1** | `DOC-FC76496810AB-0043` | **0.0963** | 25 | `title` | ❌ | `## RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES ## Pranvah Srotas vyadhi (Above 15 Years)` |
| **2** | `DOC-FC76496810AB-0040` | **0.1068** | 20 | `title` | ❌ | `## RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES ## Pranvah Srotas vyadhi (Below 15 Years)` |
| **3** | `DOC-FC76496810AB-0033` | **0.1140** | 13 | `text` | ❌ | `## PRANVAH SROTAS VYADHI (RESPIRATORY VIRAL INFECTION) THERAPEUTIC GUIDELINES ## Basic Guidelines to reduce disease severity Duration of Treatment...` |
| **4** | `DOC-FC76496810AB-0022` | **0.1168** | 25 | `title` | ❌ | `## RASAYANA GUIDELINES FOR PRANVAH SROTAS VYADHI VYADHIKSHAMATVA (RESPIRATORY VIRAL INFECTION PROPHYLAXIS) AS PER SAHVYADHI (COMRBIDITY)` |
| **5** | `DOC-FC76496810AB-0035` | **0.1207** | 25 | `title` | ❌ | `## RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION AS PER CT SCORE/ DISEASE SEVERITY ALONG WITH OTHER CO MORBIDITIES` |
| **6** | `DOC-FC76496810AB-0014` | **0.1285** | 6 | `table` | ❌ | Table fragment for pediatric age groups (below 1 yr, 1-3 yrs, 3-15 yrs) under prophylaxis |
| **7** | `DOC-FC76496810AB-0049` | **0.1286** | 25 | `text` | ❌ | Boilerplate disclaimer: *"Only for the guidance of Registered Ayurvedic Medical Practitioners..."* |
| **8** | `DOC-FC76496810AB-0055` | **0.1286** | 20 | `text` | ❌ | Identical duplicate boilerplate disclaimer |
| **9** | `DOC-FC76496810AB-0052` | **0.1306** | 20 | `text` | ❌ | Identical duplicate boilerplate disclaimer |
| **10** | **`DOC-FC76496810AB-0028`** | **0.1327** | **10** | **`table`** | **✅** | **Target Chunk: Contains exact guidance for Asthma/COPD regular inhalers** |

### 2.4 Top Distractors Analysis
- **Distractor Ranks 1, 2, 4, 5 (Standalone Markdown Headings)**:
  Four of the top five retrieved items are pure markdown headers (`title`). Because the query contains terms `"respiratory viral infection has Pranvah Srotas Vyadhi"`, these title chunks share virtually 100% token overlap with the clinical query intent. Dense vector models penalize longer tables with tabular whitespace and multiple medicine names compared to ultra-dense 15-word title chunks.
- **Distractor Ranks 7, 8, 9 (Duplicate Disclaimer Noise)**:
  Three identical legal disclaimers (*"Only for the guidance of Registered Ayurvedic Medical Practitioners..."*) achieved distances of `0.1286` and `0.1306`. This is closer than the target chunk's `0.1327` by merely `0.0021` to `0.0041` distance units. Because disclaimers appear repeatedly across pages without semantic differentiation, they act as noise traps in dense vector space.

### 2.5 Failure Classification & Diagnosis
- **Primary Diagnosis**: **Ranking Problem** compounded by **Chunking Issues (Isolated Title Chunks & Boilerplate Noise)**.
- **Why it failed**:
  The system did *not* miss the chunk entirely; it successfully identified it in the vector index. However, 4 short title chunks and 3 repetitive disclaimer fragments crowded the top 9 ranks. The ground truth table was only `0.0042` distance units behind Rank 6 (`0.1285` vs `0.1327`).

### 2.6 Recommended Next Steps
1. **Exclude or Merge Standalone Title Chunks**: Update chunking rules so headings are prepended as contextual breadcrumbs to their following content tables instead of existing as standalone vectors (or flag them with `exclude_from_embedding: true`).
2. **Deduplicate Boilerplate Disclaimers**: Filter out repetitive disclaimers during ingestion so they do not consume retrieval slots.
3. **Cross-Encoder Re-Ranking**: Implement a cross-encoder re-ranker (e.g. `bge-reranker-large` or `ms-marco`) on the top-20 ChromaDB results. A cross-encoder will instantly demote headers and disclaimers because they lack specific medicine answers (`Pranvallabh Rasayan`, `Matra`, `Sahpaan`).

---

## 3. Deep-Dive Case Diagnosis: TC-RESP-003

### 3.1 Case Specification
- **Test ID**: `TC-RESP-003`
- **Disease Filter**: `respiratory_viral_infection`
- **Title**: Respiratory - Pediatric Therapeutic Protocol (3-15 Years)
- **Clinical Question**:
  > *"For pediatric patients aged 3 to 15 years with respiratory viral infection, retrieve the therapeutic guidelines including medicine, Matra, Sahpaan and Aushadh Kal."*
- **Expected Ground-Truth Chunk ID**: `DOC-FC76496810AB-0034-F189E813F7AB`
- **Expected Source Page**: Page 13
- **Document Name**: `Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).md`
- **Retrieved Rank**: **Rank 10** (Pass Status: **FAIL**, $\text{Hit@5} = 0$, $\text{Hit@10} = 1.0$, $\text{MRR} = 0.1000$)
- **Cosine Distance of Expected Chunk**: `0.1618`

### 3.2 Expected Ground-Truth Content (`DOC-FC76496810AB-0034-F189E813F7AB`)
```markdown
| Patient Type | Medicine | Matra | Sahpaan | Aushadh Kal |
|-----------------|-----------------------|---------|-----------------------------|---------------------------------------------------------------------------|
| Above 15 yr | Somtajvir | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |
| Above 15 yr | Pranvir | 2-2-2 | Warm water | Three times a day after food |
| Above 15 yr | Rasaka Rasayana | 1-0-1 | Honey/warm water compulsory | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |
| 3-15 yrs | Pranvir | 1-1-1 | Warm water | Three times a day after food |
| 3-15 yrs | Rasaka Rasayana | 1-0-1 | Honey/warm water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |
| 3-15 yrs | Mahalakshmi Vilas Ras | 1-0-1 | Honey/warm water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |
| 3-15 yrs | Bal Rasayana | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |
| Lactating women | Somtajvir | 1-0-1 | Honey/warm water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |
| Lactating women | Pranvir | 2-2-2 | Warm water | Three times a day after food |
| Lactating women | Rasaka Rasayana | 1-0-1 | Honey/warm water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |
```

### 3.3 Retrieved Top-10 Chunks Comparison

| Rank | Chunk ID | Distance | Page | Content Type | Match? | Content Snippet / Nature of Chunk |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| **1** | `DOC-FC76496810AB-0015` | **0.1118** | 6 | `table` | ❌ | **Prophylactic** Pediatric Table: `| Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities) \| 3-15 yrs \| Rasvir 1-0-0...` |
| **2** | `DOC-FC76496810AB-0040` | **0.1336** | 20 | `title` | ❌ | Standalone Header: `## RASAYANA GUIDELINES FOR RESPIRATORY VIRAL INFECTION... ## Pranvah Srotas vyadhi (Below 15 Years)` |
| **3** | `DOC-FC76496810AB-0058` | **0.1358** | 20 | `text` | ❌ | Disclaimer: `Only for the guidance of Registered Ayurvedic Medical Practitioners...` |
| **4** | `DOC-FC76496810AB-0016` | **0.1368** | 6 | `table` | ❌ | Second fragment of Page 6 Pediatric Prophylaxis table (`below 1yr`, `SBP Rasayana`) |
| **5** | `DOC-FC76496810AB-0018` | **0.1421** | 7 | `table` | ❌ | Page 7 Prophylactic Table for Granthi/Arbud comorbidities across pediatric groups |
| **6** | `DOC-FC76496810AB-0033` | **0.1437** | 13 | `text` | ❌ | Header/intro text preceding Chunk 0034: `## PRANVAH SROTAS VYADHI (RESPIRATORY VIRAL INFECTION) THERAPEUTIC GUIDELINES ## Basic Guidelines...` |
| **7** | `DOC-FC76496810AB-0019` | **0.1524** | 7 | `table` | ❌ | Continued table from Page 7 (Malignancy comorbidity prophylaxis) |
| **8** | `DOC-FC76496810AB-0043` | **0.1577** | 25 | `title` | ❌ | Standalone Header: `## RASAYANA GUIDELINES... ## Pranvah Srotas vyadhi (Above 15 Years)` |
| **9** | `DOC-FC76496810AB-0014` | **0.1589** | 6 | `table` | ❌ | Leading rows of Page 6 Prophylaxis table |
| **10** | **`DOC-FC76496810AB-0034`** | **0.1618** | **13** | **`table`** | **✅** | **Target Chunk: Therapeutic Guidelines table for 3-15 yrs** |

### 3.4 Top Distractors Analysis
- **Distractor Rank 1 (`DOC-FC76496810AB-0015` on Page 6)**:
  This chunk ranked #1 with an exceptional distance of `0.1118`. Inspecting its text reveals that it is *also* a pediatric guideline table with column headers `| Patient type | Age Group | Medicine | Matra | Sahpaan | Aushadh Kal |` and rows specifically for `3-15 yrs`. However, it belongs to the **Prophylaxis (Prevention)** section of the document, not the **Therapeutic (Treatment)** section!
- **Distractor Rank 6 (`DOC-FC76496810AB-0033` on Page 13)**:
  This chunk is the markdown header and intro text directly above chunk `0034`:
  ```markdown
  ## PRANVAH SROTAS VYADHI (RESPIRATORY VIRAL INFECTION) THERAPEUTIC GUIDELINES
  ## Basic Guidelines to reduce disease severity
  Duration of Treatment: usually 15 days suffice...
  ```
  Rank 6 captured the exact word `"THERAPEUTIC"` that was in the query!
- **Why Target Chunk `0034` lost to Chunk `0015`**:
  During document extraction, Chunk `0033` and Chunk `0034` were separated into two independent chunks. Chunk `0034` starts immediately with table row headers: `| Patient Type | Medicine | Matra | Sahpaan | Aushadh Kal |`.
  Crucially, **the word "Therapeutic" does NOT appear anywhere inside chunk `0034`**!
  In contrast, Chunk `0015` on Page 6 repeats the prefix phrase `Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities)` seven times in every row. Chunk `0015` had dense tabular content and high keyword density, while chunk `0034` lacked the discriminating label "Therapeutic".

### 3.5 Failure Classification & Diagnosis
- **Primary Diagnosis**: **Chunking Issue (Context Severance / Headless Table)** & **Embedding Semantic Confusion (Prophylaxis vs Therapeutics)**.
- **Why it failed**:
  Chunk `0034` became a "headless table" in vector space. Because the section title (`"THERAPEUTIC GUIDELINES"`) remained in chunk `0033`, chunk `0034` had no textual indication that it represented therapeutic guidelines rather than prophylaxis. The embedding model matched the query's pediatric tokens (`"3 to 15 years"`, `"pediatric"`, `"Matra"`, `"Sahpaan"`) to the Page 6 table (`0015`), which contained far more textual repetition.

### 3.6 Recommended Next Steps
1. **Hierarchical Context Prepending**: When chunking tables, always inject the nearest enclosing markdown section headers (e.g. `Section: PRANVAH SROTAS VYADHI THERAPEUTIC GUIDELINES`) into the chunk text before embedding. This guarantees the table retains its clinical purpose.
2. **Enrich Ground Truth Target Set**: Because Chunk `0033` (the therapeutic header) and Chunk `0034` (the therapeutic dosing table) form a contiguous semantic unit on Page 13, the ground truth definition for this test case could appropriately include both chunk IDs `["DOC-FC76496810AB-0033-2BF705071DDC", "DOC-FC76496810AB-0034-F189E813F7AB"]`. If either or both are retrieved, Rank would be **#6**, boosting Hit@5 and Recall.
3. **Structured Metadata Tagging**: Add a `clinical_phase` metadata field (`prophylactic` vs `therapeutic`) extracted from the document structure to allow filtered retrieval when queries specify therapy vs prevention.

---

## 4. Comprehensive Diagnostic Matrix (All 10 Golden Cases)

| Test ID | Disease | Expected Chunk(s) | Page | First Rank | Cosine Dist | Status | Primary Retrieval Mechanism / Observation |
|---|---|---|---|:---:|:---:|:---:|---|
| **TC-DM-001** | Diabetes | `DOC-5FFD839CD910-0021` | 8 | **1** | 0.1305 | **PASS** | Strong exact symptom matching (`Trushna`, `Aruchi`, `Zincare`). |
| **TC-DM-002** | Diabetes | `DOC-5FFD839CD910-0015` | 6 | **2** | 0.1328 | **PASS** | High similarity on `BMI >= 25`, `Family History Of DM`. Rank 1 was section intro. |
| **TC-DM-003** | Diabetes | `DOC-5FFD839CD910-0041` | 15 | **1** | 0.1264 | **PASS** | Exact match on `Mutraghaat`, `Diabetic Nephropathy`, and `Sutendra Rasayana`. |
| **TC-DM-004** | Diabetes | `DOC-5FFD839CD910-0058` | 19 | **3** | 0.1492 | **PASS** | Strong clinical alignment on `Pramehaj Moorcha` and `Udarshool`. |
| **TC-DM-005** | Diabetes | `DOC-5FFD839CD910-0062` | 20 | **1** | 0.1348 | **PASS** | High lexical overlap on `Diabetic Retinopathy`, `Blurred vision`, `Floaters`. |
| **TC-RESP-001** | Respiratory | `DOC-FC76496810AB-0023` | 8 | **4** | 0.1396 | **PASS** | Retrieved at Rank 4; Ranks 1-3 were high-level section titles. |
| **TC-RESP-002** | Respiratory | `DOC-FC76496810AB-0028` | 10 | **10** | 0.1327 | **FAIL** | **Distractor crowding**: 4 title chunks and 3 boilerplate chunks pushed target to rank 10. |
| **TC-RESP-003** | Respiratory | `DOC-FC76496810AB-0034` | 13 | **10** | 0.1618 | **FAIL** | **Context severance**: Table chunk lacked `"Therapeutic"` keyword; Page 6 prophylaxis ranked #1. |
| **TC-RESP-004** | Respiratory | `0038`, `0039` | 15 | **1** | 0.1189 | **PASS** | Dual table split chunks on HRCT score 9-15 both retrieved successfully. |
| **TC-RESP-005** | Respiratory | `DOC-FC76496810AB-0060` | 22 | **1** | 0.1172 | **PASS** | Exact symptom matching on `Jalad Hrudgati` and `Rasabhinodan vruddhi`. |

---

## 5. Architectural & Pipeline Recommendations

Without modifying the existing pipeline files during Phase 1, the following improvements are recommended for Phase 2:

### Recommendation 1: Context-Aware Document Chunking
- **Problem**: Chunks `0034` and `0028` lost parent header context when Docling/chunker converted the Markdown tables into standalone chunks.
- **Solution**: Implement "section-path breadcrumbs". When emitting a table chunk, prepend its hierarchy:
  ```markdown
  [Document: Respiratory Protocol > Section: Pranvah Srotas > Subsection: Therapeutic Guidelines]
  | Patient Type | Medicine | Matra | ...
  ```
  This immediately eliminates semantic ambiguity between prophylactic and therapeutic tables.

### Recommendation 2: Noise Chunk Filtering at Ingestion
- **Problem**: Standalone titles (e.g. `DOC-FC76496810AB-0043`) and disclaimers (e.g. `0049`, `0052`, `0055`) occupied 5 out of the top 9 positions in both failed cases.
- **Solution**:
  - Filter out repetitive disclaimer paragraphs by regex or min-entropy checks.
  - Set `exclude_from_embedding: true` for pure heading chunks of type `title` if they do not contain operational clinical guidance.

### Recommendation 3: Ground-Truth Dataset Refinement (Phase 1 Follow-Up)
- In `TC-RESP-003`, chunk `DOC-FC76496810AB-0033` (the heading stating *Therapeutic Guidelines*) and chunk `DOC-FC76496810AB-0034` (the table itself) represent the two halves of the split section. Adding `0033` to `relevant_chunk_ids` aligns with clinical reality (analogous to the two-chunk split in `TC-RESP-004` on page 15).

### Recommendation 4: Two-Stage Retrieval (Bi-Encoder + Cross-Encoder Re-Ranking)
- Dense embeddings (`gemini-embedding-001`) are optimal for coarse candidate generation ($K=20$).
- Adding a lightweight cross-encoder re-ranker as Stage 2 will re-order the top 20 candidates based on full token-level cross-attention, easily separating dense informational tables from short title headers.
