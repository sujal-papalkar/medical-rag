import React, { useState } from 'react';
import { Sparkles, Loader2, AlertCircle, RefreshCw, BookOpen, User, FileText, Pill } from 'lucide-react';
import { useDocuments } from '../hooks/useDocuments';
import { usePatients } from '../hooks/usePatients';
import { usePrescription } from '../hooks/usePrescription';
import { DocumentUpload } from '../components/documents/DocumentUpload';
import { DocumentList } from '../components/documents/DocumentList';
import { DocumentViewModal } from '../components/documents/DocumentViewModal';
import { PatientSelector } from '../components/patients/PatientSelector';
import { PrescriptionView } from '../components/prescription/PrescriptionView';
import type { GuidelineDocument } from '../types';

export const PrescriptionPage: React.FC = () => {
  const { documents, addDocument } = useDocuments();
  const {
    patients,
    selectedPatientId,
    selectedPatient,
    clinicalQuery,
    setClinicalQuery,
    handleSelectPatient,
  } = usePatients();
  const { prescription, isLoading, error, generate, reset } = usePrescription();
  const [viewingDocument, setViewingDocument] = useState<GuidelineDocument | null>(null);

  const handleGenerate = () => {
    generate(selectedPatient, clinicalQuery);
  };

  const handleConfirmOverride = () => {
    generate(selectedPatient, clinicalQuery, true);
  };

  return (
    <main className="clinical-main-container" id="prescription-main-page">
      {/* ====================================================================
          1. Guideline Knowledge Base Card
          ==================================================================== */}
      <section className="clinical-card" id="guideline-library-section">
        <div className="clinical-card-header">
          <div>
            <h2 className="clinical-card-title">
              <BookOpen size={20} style={{ color: '#0284c7' }} />
              <span>1. Guideline Knowledge Base</span>
            </h2>
            <p className="clinical-card-subtitle">
              Authoritative clinical guideline repository indexed for grounded semantic and lexical retrieval
            </p>
          </div>
          <span className="status-badge neutral" id="indexed-docs-count-badge">
            {documents.length} {documents.length === 1 ? 'Document' : 'Documents'} Indexed
          </span>
        </div>

        <DocumentUpload onDocumentUploaded={addDocument} />
        <DocumentList documents={documents} onViewDocument={setViewingDocument} />
      </section>

      {/* ====================================================================
          2. Patient Context Card
          ==================================================================== */}
      <section className="clinical-card" id="patient-context-section">
        <div className="clinical-card-header">
          <div>
            <h2 className="clinical-card-title">
              <User size={20} style={{ color: '#0284c7' }} />
              <span>2. Patient Context</span>
            </h2>
            <p className="clinical-card-subtitle">
              Select verified clinical profile to evaluate against guideline protocols
            </p>
          </div>
        </div>

        <PatientSelector
          patients={patients}
          selectedPatientId={selectedPatientId}
          onSelectPatient={(id) => {
            reset();
            handleSelectPatient(id);
          }}
          isLoading={isLoading}
        />
      </section>

      {/* ====================================================================
          3. Clinical Query Card
          ==================================================================== */}
      <section className="clinical-card" id="clinical-query-section">
        <div className="clinical-card-header">
          <div>
            <h2 className="clinical-card-title">
              <FileText size={20} style={{ color: '#0284c7' }} />
              <span>3. Clinical Query</span>
            </h2>
            <p className="clinical-card-subtitle">
              Physician clinical query specifying symptoms, stage, and parameters
            </p>
          </div>
        </div>

        <div className="clinical-form-group">
          <label htmlFor="clinical-query-textarea" className="clinical-label">
            Clinical Query / Guideline Parameters:
          </label>
          <textarea
            id="clinical-query-textarea"
            value={clinicalQuery}
            onChange={(e) => setClinicalQuery(e.target.value)}
            disabled={isLoading}
            className="clinical-textarea"
            placeholder="Select a patient profile above or type a clinical question (e.g. In diabetic nephropathy Stage 3 complications with GFR 30-59%, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?)..."
          />
          <span style={{ fontSize: '13px', color: '#64748b' }}>
            Pre-populated from the active patient profile; you can edit parameters or query specific symptoms.
          </span>
        </div>
      </section>

      {/* ====================================================================
          4. Generate Prescription Card
          ==================================================================== */}
      <section className="clinical-card" id="generate-prescription-section">
        <div className="clinical-card-header">
          <div>
            <h2 className="clinical-card-title">
              <Pill size={20} style={{ color: '#0284c7' }} />
              <span>4. Generate Grounded Prescription</span>
            </h2>
            <p className="clinical-card-subtitle">
              Executes the composite 70% Semantic + 30% Lexical reranker and Gemini grounding
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <button
            type="button"
            id="generate-prescription-btn"
            onClick={handleGenerate}
            disabled={isLoading || !selectedPatientId}
            className="clinical-btn-primary"
            style={{ width: '100%', padding: '16px 24px', fontSize: '16px' }}
          >
            {isLoading ? (
              <>
                <Loader2 size={18} className="clinical-spinner" />
                <span>Retrieving guideline evidence and generating grounded prescription...</span>
              </>
            ) : (
              <>
                <Sparkles size={18} />
                <span>Generate Grounded Prescription</span>
              </>
            )}
          </button>

          {!selectedPatientId && (
            <p style={{ fontSize: '13px', textAlign: 'center', color: '#64748b', margin: 0 }}>
              Please select a clinical patient profile in step 2 to enable prescription generation.
            </p>
          )}

          {/* Error Banner */}
          {error && (
            <div className="clinical-error-banner" id="generation-error-box">
              <AlertCircle size={20} className="shrink-0" style={{ color: '#dc2626', marginTop: '2px' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                <strong className="clinical-error-title">Prescription Generation Failure</strong>
                <p className="clinical-error-msg">{error}</p>
                <div>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    className="clinical-btn-ghost"
                    style={{ color: '#991b1b', padding: '2px 0', marginTop: '4px' }}
                  >
                    <RefreshCw size={13} />
                    <span>Retry Generation</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ====================================================================
          5. Prescription Results (Only displayed when generated)
          ==================================================================== */}
      {prescription && (
        <section id="prescription-output-section">
          <PrescriptionView
            prescription={prescription}
            documents={documents}
            onConfirmOverride={handleConfirmOverride}
            isOverriding={isLoading}
          />
        </section>
      )}

      {/* Document View Modal */}
      <DocumentViewModal
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
      />
    </main>
  );
};
