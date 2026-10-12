import React, { useState } from 'react';
import { User, Activity, FileText, FlaskConical, ShieldCheck, AlertTriangle, Trash2, CheckCircle2 } from 'lucide-react';
import type { PatientProfile } from '../../types';
import { TestPatientModal } from './TestPatientModal';

interface PatientSelectorProps {
  patients: PatientProfile[];
  selectedPatientId: string;
  onSelectPatient: (patientId: string) => void;
  isLoading?: boolean;
  clinicalQuery?: string;
  onQueryChange?: (query: string) => void;
  showQueryInput?: boolean;
  onAddTestPatient?: (patient: PatientProfile) => void;
  onRemoveTestPatient?: (patientId: string) => void;
}

export const PatientSelector: React.FC<PatientSelectorProps> = ({
  patients,
  selectedPatientId,
  onSelectPatient,
  isLoading = false,
  clinicalQuery,
  onQueryChange,
  showQueryInput = false,
  onAddTestPatient,
  onRemoveTestPatient,
}) => {
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;
  const registeredPatients = patients.filter((p) => !p.is_test);
  const benchmarkCases = patients.filter((p) => p.is_test && p.test_number !== undefined);
  const customTestPatients = patients.filter((p) => p.is_test && p.test_number === undefined);

  return (
    <div className="patient-context-section" id="patient-context-container">
      {/* Patient Selector Dropdown Form Control */}
      <div className="clinical-form-group">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <label htmlFor="patient-dropdown" className="clinical-label">
            <User size={15} className="text-slate-500" />
            <span>Select Patient Profile:</span>
          </label>

          {onAddTestPatient && (
            <button
              type="button"
              id="add-test-patient-btn"
              onClick={() => setIsTestModalOpen(true)}
              disabled={isLoading}
              className="clinical-btn-secondary"
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                borderColor: '#f59e0b',
                color: '#b45309',
                backgroundColor: '#fffbeb',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontWeight: 600,
              }}
              title="Add a temporary test patient to test RAG query variations"
            >
              <FlaskConical size={14} className="text-amber-600" />
              <span>+ Add Test Patient</span>
            </button>
          )}
        </div>

        <select
          id="patient-dropdown"
          value={selectedPatientId}
          onChange={(e) => onSelectPatient(e.target.value)}
          disabled={isLoading}
          className="clinical-select"
        >
          <option value="">-- Choose a patient profile from registry or test cases --</option>

          <optgroup label="── Registered Clinical Records (Verified) ──">
            {registeredPatients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.age}y, {p.gender}) — {p.disease_label || p.disease}: {p.presentation}
              </option>
            ))}
          </optgroup>

          {benchmarkCases.length > 0 && (
            <optgroup label="── RAG Evaluation Test Scenarios (Cases 1–15) ──">
              {benchmarkCases.map((p) => (
                <option key={p.id} value={p.id}>
                  [{p.id}] {p.name.replace(/^TC-\d+:\s*/, '')} {p.pass_status ? `[${p.pass_status}]` : ''}
                </option>
              ))}
            </optgroup>
          )}

          {customTestPatients.length > 0 && (
            <optgroup label="── Custom Temporary Test Profiles ──">
              {customTestPatients.map((p) => (
                <option key={p.id} value={p.id}>
                  [CUSTOM TEST] {p.name} ({p.age}y, {p.gender}) — {p.disease_label || p.disease}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>

      {/* Selected Patient Details Summary Panel */}
      {selectedPatient && (
        <div
          className="patient-summary-panel"
          id="selected-patient-panel"
          style={
            selectedPatient.test_number
              ? { border: '1px solid #c7d2fe', backgroundColor: '#fcfdff' }
              : selectedPatient.is_test
              ? { border: '1px solid #fde68a', backgroundColor: '#fffdfa' }
              : undefined
          }
        >
          {/* Header Bar with Distinct Badges */}
          <div className="patient-header-bar">
            <div className="patient-name-group">
              <div
                className="patient-avatar"
                style={
                  selectedPatient.test_number
                    ? { backgroundColor: '#ede9fe', color: '#6d28d9', border: '1px solid #ddd6fe' }
                    : selectedPatient.is_test
                    ? { backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fde68a' }
                    : undefined
                }
              >
                {selectedPatient.test_number ? <FlaskConical size={20} /> : selectedPatient.is_test ? <FlaskConical size={20} /> : <User size={20} />}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                    {selectedPatient.name}
                  </h3>
                  {selectedPatient.test_number ? (
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor: '#ede9fe',
                        color: '#6d28d9',
                        border: '1px solid #ddd6fe',
                        fontSize: '11px',
                        padding: '2px 8px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                      id="patient-verification-badge"
                    >
                      <CheckCircle2 size={12} />
                      <span>EVALUATION TEST CASE #{selectedPatient.test_number}</span>
                    </span>
                  ) : selectedPatient.is_test ? (
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor: '#fef3c7',
                        color: '#b45309',
                        border: '1px solid #fde68a',
                        fontSize: '11px',
                        padding: '2px 8px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                      id="patient-verification-badge"
                    >
                      <FlaskConical size={12} />
                      <span>UNVERIFIED TEST PROFILE</span>
                    </span>
                  ) : (
                    <span
                      className="status-badge online"
                      style={{ fontSize: '11px', padding: '2px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      id="patient-verification-badge"
                    >
                      <ShieldCheck size={12} />
                      <span>VERIFIED CLINICAL RECORD</span>
                    </span>
                  )}
                </div>
                <span style={{ fontSize: '13px', color: selectedPatient.test_number ? '#6d28d9' : selectedPatient.is_test ? '#b45309' : '#0284c7', fontWeight: 600 }}>
                  {selectedPatient.disease_label ||
                    (selectedPatient.disease === 'diabetes'
                      ? 'Diabetes Mellitus (Prameha)'
                      : 'Respiratory Viral Infection')}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                className="status-badge"
                style={{
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  backgroundColor: selectedPatient.test_number ? '#ede9fe' : selectedPatient.is_test ? '#fffbeb' : '#f1f5f9',
                  color: selectedPatient.test_number ? '#6d28d9' : selectedPatient.is_test ? '#b45309' : '#334155',
                  border: selectedPatient.test_number ? '1px solid #ddd6fe' : selectedPatient.is_test ? '1px solid #fde68a' : '1px solid #cbd5e1',
                }}
              >
                ID: {selectedPatient.id}
              </span>

              {selectedPatient.is_test && !selectedPatient.test_number && onRemoveTestPatient && (
                <button
                  type="button"
                  onClick={() => onRemoveTestPatient(selectedPatient.id)}
                  className="clinical-btn-ghost"
                  style={{ color: '#dc2626', padding: '4px 8px', fontSize: '12px' }}
                  title="Discard this test patient"
                  id="remove-test-patient-btn"
                >
                  <Trash2 size={13} />
                  <span>Remove Test Profile</span>
                </button>
              )}
            </div>
          </div>

          {/* Test Profile Notice Banner or Benchmark Specification Banner */}
          {selectedPatient.test_number ? (
            <div
              id="benchmark-test-banner"
              style={{
                padding: '12px 16px',
                backgroundColor: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: 700, color: '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={16} className="text-green-600 shrink-0" />
                  <span>RAG Evaluation Benchmark: Test Case {selectedPatient.test_number} of 15</span>
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {selectedPatient.supporting_source_page && (
                    <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px', backgroundColor: '#e0f2fe', color: '#0369a1', border: '1px solid #bae6fd' }}>
                      Guideline Provenance: Page {selectedPatient.supporting_source_page}
                    </span>
                  )}
                  <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #86efac' }}>
                    Status: {selectedPatient.pass_status || 'PASS'}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: '13px', color: '#14532d', lineHeight: 1.5 }}>
                <strong>Expected Clinical Behavior:</strong> {selectedPatient.expected_behavior}
              </div>
            </div>
          ) : selectedPatient.is_test ? (
            <div
              id="test-profile-notice-box"
              style={{
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
              <AlertTriangle size={16} className="text-amber-600 shrink-0" />
              <span>
                <strong>Temporary Test Profile:</strong> Unverified synthetic data for clinical guideline & RAG evaluation only. Kept strictly isolated from registered clinical records.
              </span>
            </div>
          ) : null}

          {/* Patient Details Grid */}
          <div className="patient-info-grid">
            <div className="patient-info-item">
              <span className="patient-info-label">Patient / Scenario Name</span>
              <span className="patient-info-val">{selectedPatient.name}</span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Age & Sex</span>
              <span className="patient-info-val">
                {selectedPatient.age} years • {selectedPatient.gender}
              </span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Record Type</span>
              <span className="patient-info-val" style={{ color: selectedPatient.test_number ? '#6d28d9' : selectedPatient.is_test ? '#b45309' : '#059669' }}>
                {selectedPatient.test_number ? `RAG Evaluation Case #${selectedPatient.test_number}` : selectedPatient.is_test ? 'Unverified Test Data' : 'Authoritative Registry'}
              </span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Primary Diagnosis</span>
              <span className="patient-info-val" style={{ color: '#0284c7' }}>
                {selectedPatient.disease_label || selectedPatient.disease}
              </span>
            </div>
          </div>

          {/* Clinical Presentation Box */}
          <div className="patient-info-item" style={{ marginTop: '4px' }}>
            <span className="patient-info-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Activity size={13} style={{ color: selectedPatient.is_test ? '#d97706' : '#0284c7' }} />
              Clinical Presentation & Diagnostic Symptoms:
            </span>
            <div
              className="patient-presentation-box"
              style={
                selectedPatient.is_test
                  ? { borderColor: '#fde68a', backgroundColor: '#ffffff' }
                  : undefined
              }
            >
              {selectedPatient.presentation}
            </div>
          </div>

          {/* Optional inline query input if explicitly enabled */}
          {showQueryInput && onQueryChange && clinicalQuery !== undefined && (
            <div className="clinical-form-group" style={{ marginTop: '8px' }}>
              <label htmlFor="patient-inline-query" className="clinical-label">
                <FileText size={14} className="text-slate-500" />
                <span>Clinical Query / Guideline Parameters:</span>
              </label>
              <textarea
                id="patient-inline-query"
                value={clinicalQuery}
                onChange={(e) => onQueryChange(e.target.value)}
                disabled={isLoading}
                rows={3}
                className="clinical-textarea"
                placeholder="Enter clinical query..."
              />
            </div>
          )}
        </div>
      )}

      {/* Test Patient Creation Modal */}
      {onAddTestPatient && (
        <TestPatientModal
          isOpen={isTestModalOpen}
          onClose={() => setIsTestModalOpen(false)}
          onAddTestPatient={onAddTestPatient}
        />
      )}
    </div>
  );
};
