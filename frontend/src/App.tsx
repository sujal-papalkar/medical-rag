import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { GuidelineLibraryCard } from './components/GuidelineLibraryCard';
import { SelectPatientCard } from './components/SelectPatientCard';
import { GeneratePrescriptionCard } from './components/GeneratePrescriptionCard';
import { GeneratedGuidanceCard } from './components/GeneratedGuidanceCard';
import { DocumentViewModal } from './components/DocumentViewModal';
import { CLINICAL_PATIENTS } from './data/patients';
import type { GuidelineDocument, GenerationResult, GenerationSource } from './types';

const API_BASE = 'http://localhost:8000';

const INITIAL_GUIDELINE_DOCUMENTS: GuidelineDocument[] = [
  {
    id: 'DOC-5FFD839CD910',
    name: 'DM RR.pdf',
    diseaseCategory: 'Diabetes',
    uploadedAt: '2026-10-06 11:30 AM',
    chunksIndexed: 50,
    status: 'Indexed',
    description:
      'Official Ayurvedic clinical protocol for the management of Diabetes Mellitus (Prameha), pre-diabetes, and complications.',
  },
  {
    id: 'DOC-FC76496810AB',
    name: 'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf',
    diseaseCategory: 'Respiratory Viral Infection',
    uploadedAt: '2026-10-06 11:30 AM',
    chunksIndexed: 81,
    status: 'Indexed',
    description:
      'National Ayurvedic clinical protocol for the management of Respiratory Viral Infections categorized by CT score, disease severity, and comorbidities.',
  },
];

export function App() {
  const [documents, setDocuments] = useState<GuidelineDocument[]>(INITIAL_GUIDELINE_DOCUMENTS);
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [clinicalQuery, setClinicalQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewingDocument, setViewingDocument] = useState<GuidelineDocument | null>(null);
  const [backendConnected, setBackendConnected] = useState<boolean>(true);

  // Ping backend health on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((res) => {
        if (res.ok) setBackendConnected(true);
      })
      .catch(() => {
        setBackendConnected(false);
      });
  }, []);

  // When a patient is chosen, populate the query and reset generation state
  const handleSelectPatient = (patientId: string) => {
    setSelectedPatientId(patientId);
    setError(null);
    setResult(null);

    const found = CLINICAL_PATIENTS.find((p) => p.id === patientId);
    if (found) {
      setClinicalQuery(found.clinicalQuery);
    } else {
      setClinicalQuery('');
    }
  };

  // Upload handler for adding documents
  const handleUploadDocument = (file: File) => {
    const newDoc: GuidelineDocument = {
      id: `DOC-NEW-${Date.now().toString(36).toUpperCase()}`,
      name: file.name,
      diseaseCategory: file.name.toLowerCase().includes('respir')
        ? 'Respiratory Viral Infection'
        : 'Diabetes',
      uploadedAt: new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
      chunksIndexed: 0,
      status: 'Staged',
      description: 'Uploaded guideline document staged for automated Docling chunking and vector indexing.',
    };

    setDocuments((prev) => [newDoc, ...prev]);
  };

  // Generate Prescription Action
  const handleGeneratePrescription = async () => {
    const selectedPatient = CLINICAL_PATIENTS.find((p) => p.id === selectedPatientId);
    if (!selectedPatient) return;

    const queryToUse = clinicalQuery.trim() || selectedPatient.clinicalQuery;
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      // 1. Attempt generation endpoint if available
      let is404 = false;
      try {
        const genResponse = await fetch(`${API_BASE}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: queryToUse,
            disease: selectedPatient.disease,
            top_k: 5,
          }),
        });

        if (genResponse.ok) {
          const data = await genResponse.json();
          setResult({
            query: queryToUse,
            disease: selectedPatient.disease,
            answer: data.answer || 'Guidance returned.',
            sources: (data.sources || []).map((s: any, idx: number) => ({
              chunk_id: s.chunk_id || `chunk-${idx + 1}`,
              document_name: s.document_name || 'Guideline Protocol',
              disease: s.disease || selectedPatient.disease,
              section: s.section,
              page: s.page,
              rank: s.rank ?? idx + 1,
            })),
            limitations: data.limitations,
            model: data.model || 'Gemini 2.5 Flash',
            status: data.status || 'success',
          });
          return;
        }

        if (genResponse.status === 404) {
          is404 = true;
        } else {
          const errData = await genResponse.json().catch(() => ({}));
          throw new Error(errData.detail || `Server responded with status ${genResponse.status}`);
        }
      } catch (err: any) {
        if (!is404 && err.message && !err.message.includes('Failed to fetch') && !err.message.includes('404')) {
          throw err;
        }
        is404 = true;
      }

      // 2. Fallback to existing retrieval endpoint (/api/evaluate/custom)
      if (is404) {
        const retrievalResponse = await fetch(`${API_BASE}/api/evaluate/custom`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: queryToUse,
            disease: selectedPatient.disease,
            top_k: 5,
            relevant_chunk_ids: [],
          }),
        });

        if (!retrievalResponse.ok) {
          throw new Error(
            `Backend retrieval service error (${retrievalResponse.status}): ${retrievalResponse.statusText}`
          );
        }

        const data = await retrievalResponse.json();
        const retrievedChunks = data.retrieved_chunks || [];

        const sources: GenerationSource[] = retrievedChunks.map((c: any, idx: number) => ({
          chunk_id: c.chunk_id,
          document_name:
            c.document_name ||
            (selectedPatient.disease === 'diabetes'
              ? 'DM RR.pdf'
              : 'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf'),
          disease: c.disease || selectedPatient.disease,
          section: c.section || c.heading || 'Guideline Treatment Protocol',
          page: c.page ?? null,
          rank: idx + 1,
          distance: c.distance,
        }));

        const chunkSnippets = retrievedChunks
          .map(
            (c: any, idx: number) =>
              `### ${idx + 1}. ${c.section || 'Prescribed Protocol'} (Page ${c.page ?? 'N/A'})\n` +
              `*Source Document: ${c.document_name || 'Ayurvedic Clinical Guideline'} | Chunk ID: \`${c.chunk_id}\`*\n\n` +
              `> ${c.content ? c.content.slice(0, 360) + (c.content.length > 360 ? '...' : '') : 'Guideline evidence retrieved.'}\n`
          )
          .join('\n');

        setResult({
          query: queryToUse,
          disease: selectedPatient.disease,
          answer:
            `## Grounded Ayurvedic Clinical Guidance\n\n` +
            `**Patient:** ${selectedPatient.name} (${selectedPatient.age} yrs, ${selectedPatient.gender}) — *${selectedPatient.diseaseLabel}*\n\n` +
            `**Clinical Diagnosis / Condition:** ${selectedPatient.presentation}\n\n` +
            `The retrieval & reranking pipeline retrieved **${sources.length} authoritative guideline chunks** grounded in verified clinical protocols:\n\n` +
            chunkSnippets,
          sources,
          limitations:
            'Guideline evidence was retrieved and reranked using the 70% semantic + 30% lexical pipeline. Direct LLM generation is implemented in backend/generation.py and awaiting FastAPI endpoint registration.',
          notice:
            'Evidence retrieved from active ChromaDB vectorstore via POST /api/evaluate/custom. Full LLM generation is configured in backend/generation.py.',
          model: 'ChromaDB + Gemini Text Embedding 004 Reranker',
          status: 'partial',
        });
      }
    } catch (err: any) {
      console.error('Generation error:', err);
      setError(
        err.message ||
          'Failed to connect to backend clinical RAG service. Ensure backend server is running on http://localhost:8000.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="clinical-app-wrapper">
      {/* Header */}
      <Header backendConnected={backendConnected} />

      {/* Main Single-Column Stacked Cards */}
      <main className="clinical-main-container">
        {/* 1. Guideline Library */}
        <GuidelineLibraryCard
          documents={documents}
          onUploadDocument={handleUploadDocument}
          onViewDocument={(doc) => setViewingDocument(doc)}
        />

        {/* 2. Select Patient */}
        <SelectPatientCard
          patients={CLINICAL_PATIENTS}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handleSelectPatient}
          clinicalQuery={clinicalQuery}
          onQueryChange={setClinicalQuery}
          isLoading={isLoading}
        />

        {/* 3. Generate Prescription */}
        <GeneratePrescriptionCard
          onGenerate={handleGeneratePrescription}
          isLoading={isLoading}
          isPatientSelected={Boolean(selectedPatientId)}
        />

        {/* 4. Generated Clinical Guidance (Appears after generation or during loading/error) */}
        <GeneratedGuidanceCard
          isLoading={isLoading}
          result={result}
          error={error}
          onRetry={handleGeneratePrescription}
        />
      </main>

      {/* Document View Modal */}
      <DocumentViewModal
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
      />
    </div>
  );
}

export default App;
