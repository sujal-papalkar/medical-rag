import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2, AlertTriangle, ShieldAlert, ArrowRight, Loader2, FlaskConical } from 'lucide-react';
import type { StructuredPrescriptionResponse, GuidelineDocument, ResolvedMedicineCitation } from '../../types';
import { MedicineTable } from './MedicineTable';
import { EvidencePanel } from './EvidencePanel';

interface PrescriptionViewProps {
  prescription: StructuredPrescriptionResponse;
  documents?: GuidelineDocument[];
  onConfirmOverride?: () => void;
  isOverriding?: boolean;
}

export const PrescriptionView: React.FC<PrescriptionViewProps> = ({
  prescription,
  documents = [],
  onConfirmOverride,
  isOverriding = false,
}) => {
  const { medicines, evidence_sources, validation_status, requires_confirmation, conflicts, patient } = prescription;
  const isBenchmarkCase = Boolean(patient?.patient_id?.startsWith('TC-'));
  const isTestPatient = Boolean(patient?.patient_id?.startsWith('TEST-')) || isBenchmarkCase;

  // Evidence modal state for on-demand verification
  const [evidencePanelOpen, setEvidencePanelOpen] = useState(false);
  const [panelMedicineName, setPanelMedicineName] = useState<string>('');
  const [panelCitations, setPanelCitations] = useState<ResolvedMedicineCitation[]>([]);
  const [panelCitationIndex, setPanelCitationIndex] = useState<number>(0);

  const handleOpenEvidencePanel = (
    medicineName: string,
    citations: ResolvedMedicineCitation[],
    citationIndex: number = 0
  ) => {
    setPanelMedicineName(medicineName);
    setPanelCitations(citations);
    setPanelCitationIndex(citationIndex);
    setEvidencePanelOpen(true);
  };

  return (
    <div className="clinical-card" id="prescription-results-card">
      {/* 1. Header: Prescription Results */}
      <div className="clinical-card-header">
        <div>
          <h2 className="clinical-card-title">
            Prescription Results
          </h2>
          <p className="clinical-card-subtitle">
            Evidence-grounded Ayurvedic formulations with verified document and page provenance
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isBenchmarkCase ? (
            <span
              className="status-badge"
              style={{
                backgroundColor: '#ede9fe',
                color: '#6d28d9',
                border: '1px solid #ddd6fe',
                fontSize: '12px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
              id="prescription-benchmark-badge"
            >
              <FlaskConical size={13} />
              <span>RAG EVALUATION RUN</span>
            </span>
          ) : isTestPatient ? (
            <span
              className="status-badge"
              style={{
                backgroundColor: '#fef3c7',
                color: '#b45309',
                border: '1px solid #fde68a',
                fontSize: '12px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
              id="prescription-test-badge"
            >
              <FlaskConical size={13} />
              <span>UNVERIFIED TEST DATA</span>
            </span>
          ) : null}

          {requires_confirmation ? (
            <span className="status-badge" style={{ backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fde68a' }} id="prescription-status-badge">
              <AlertTriangle size={14} />
              <span>Conflict Pending Confirmation</span>
            </span>
          ) : (
            <span
              className={`status-badge ${validation_status === 'valid' ? 'online' : 'primary'}`}
              id="prescription-status-badge"
            >
              {validation_status === 'valid' ? (
                <>
                  <ShieldCheck size={14} />
                  <span>Grounded & Validated</span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={14} />
                  <span>Clinical Regimen</span>
                </>
              )}
            </span>
          )}
          <span className="status-badge neutral">
            {medicines.length} {medicines.length === 1 ? 'Formulation' : 'Formulations'}
          </span>
        </div>
      </div>

      {/* 2. Clinical Conflict Alert Box (When confirmation is required) */}
      {requires_confirmation && (
        <div
          id="clinical-conflict-alert"
          style={{
            marginTop: '16px',
            padding: '20px',
            backgroundColor: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '10px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <AlertTriangle size={24} style={{ color: '#d97706', marginTop: '2px', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#92400e', margin: '0 0 6px 0' }}>
                Clinical Conflict Detected — Physician Confirmation Required
              </h3>
              <p style={{ fontSize: '14px', color: '#b45309', margin: 0, lineHeight: 1.5 }}>
                The verified patient profile is authoritative for demographics and registered comorbidities.
                Parameters in your clinical query conflict with the verified patient record.
                Prescription generation has been paused without guessing or overwriting the registered record.
              </p>
            </div>
          </div>

          {/* Conflict Details Table */}
          {conflicts && conflicts.length > 0 && (
            <div style={{ overflowX: 'auto', border: '1px solid #fde68a', borderRadius: '6px' }}>
              <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse', backgroundColor: '#ffffff' }}>
                <thead>
                  <tr style={{ backgroundColor: '#fef3c7', textAlign: 'left', color: '#92400e' }}>
                    <th style={{ padding: '10px 12px', borderBottom: '1px solid #fde68a' }}>Parameter</th>
                    <th style={{ padding: '10px 12px', borderBottom: '1px solid #fde68a' }}>Verified Patient Record (Authoritative)</th>
                    <th style={{ padding: '10px 12px', borderBottom: '1px solid #fde68a' }}>Physician Query (Requested)</th>
                    <th style={{ padding: '10px 12px', borderBottom: '1px solid #fde68a' }}>Conflict Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {conflicts.map((c, i) => (
                    <tr key={i} style={{ borderBottom: i < conflicts.length - 1 ? '1px solid #fef3c7' : 'none' }}>
                      <td style={{ padding: '10px 12px', fontWeight: 600, color: '#334155' }}>
                        {c.parameter.toUpperCase()}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#166534', fontWeight: 500 }}>
                        {String(c.registered_value)}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#b91c1c', fontWeight: 500 }}>
                        {String(c.query_value)}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#475569' }}>
                        {c.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Confirmation Action Button */}
          {onConfirmOverride && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '14px', paddingTop: '8px' }}>
              <span style={{ fontSize: '13px', color: '#78350f' }}>
                Confirming override applies the query clinical scenario without modifying the registered patient database.
              </span>
              <button
                type="button"
                id="confirm-conflict-override-btn"
                onClick={onConfirmOverride}
                disabled={isOverriding}
                className="clinical-btn-primary"
                style={{ backgroundColor: '#d97706', borderColor: '#b45309', padding: '10px 18px', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isOverriding ? (
                  <>
                    <Loader2 size={16} className="clinical-spinner" />
                    <span>Applying override & generating...</span>
                  </>
                ) : (
                  <>
                    <span>Confirm Override & Generate Regimen</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* 3. Clinical Override Active Banner (When override was confirmed) */}
      {!requires_confirmation && conflicts && conflicts.length > 0 && (
        <div
          id="clinical-override-active-notice"
          style={{
            marginTop: '12px',
            marginBottom: '12px',
            padding: '10px 16px',
            backgroundColor: '#eff6ff',
            border: '1px solid #bfdbfe',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
            color: '#1e40af'
          }}
        >
          <ShieldAlert size={16} style={{ color: '#2563eb', flexShrink: 0 }} />
          <span>
            <strong>Physician Clinical Override Active:</strong> Prescriptions grounded in confirmed query parameters ({conflicts.map(c => c.parameter).join(', ')}). Authoritative patient profile remains intact.
          </span>
        </div>
      )}

      {/* 4. Display the Medicines Table if not pending confirmation */}
      {!requires_confirmation && (
        <div style={{ marginTop: '12px' }}>
          {isBenchmarkCase ? (
            <div
              id="prescription-benchmark-case-notice"
              style={{
                marginBottom: '14px',
                padding: '12px 16px',
                backgroundColor: '#f5f3ff',
                border: '1px solid #ddd6fe',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '13px',
                color: '#5b21b6',
              }}
            >
              <FlaskConical size={16} className="text-purple-600 shrink-0" />
              <span>
                <strong>Benchmark Test Execution:</strong> Prescriptions and citations generated for evaluation case <code style={{ fontFamily: 'var(--font-mono)' }}>{patient?.patient_id}</code> ({patient?.name || 'Evaluation Scenario'}). Inspect actual prescribed formulations, dosages, and source citations below to compare against benchmark expected behavior.
              </span>
            </div>
          ) : isTestPatient ? (
            <div
              id="prescription-test-profile-notice"
              style={{
                marginBottom: '14px',
                padding: '10px 14px',
                backgroundColor: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '13px',
                color: '#92400e',
              }}
            >
              <FlaskConical size={16} className="text-amber-600 shrink-0" />
              <span>
                <strong>Evaluation Notice:</strong> Prescribed formulations and clinical guidance were generated for temporary test profile <code style={{ fontFamily: 'var(--font-mono)' }}>{patient?.patient_id}</code> ({patient?.name || 'Test Patient'}). Results are strictly for testing query variations; verified clinical records are unaltered.
              </span>
            </div>
          ) : null}

          <MedicineTable
            medicines={medicines}
            evidenceSources={evidence_sources}
            knownDocs={documents}
            onInspectEvidence={handleOpenEvidencePanel}
          />
        </div>
      )}

      {/* 5. On-Demand Evidence Details Modal (shown only upon user click) */}
      <EvidencePanel
        key={`${panelMedicineName}-${panelCitationIndex}`}
        isOpen={evidencePanelOpen}
        onClose={() => setEvidencePanelOpen(false)}
        medicineName={panelMedicineName}
        citations={panelCitations}
        initialCitationIndex={panelCitationIndex}
      />
    </div>
  );
};

