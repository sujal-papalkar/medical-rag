import React from 'react';
import { User, Activity, FileText } from 'lucide-react';
import type { PatientProfile } from '../../types';

interface PatientSelectorProps {
  patients: PatientProfile[];
  selectedPatientId: string;
  onSelectPatient: (patientId: string) => void;
  isLoading?: boolean;
  clinicalQuery?: string;
  onQueryChange?: (query: string) => void;
  showQueryInput?: boolean;
}

export const PatientSelector: React.FC<PatientSelectorProps> = ({
  patients,
  selectedPatientId,
  onSelectPatient,
  isLoading = false,
  clinicalQuery,
  onQueryChange,
  showQueryInput = false,
}) => {
  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  return (
    <div className="patient-context-section" id="patient-context-container">
      {/* Patient Selector Dropdown Form Control */}
      <div className="clinical-form-group">
        <label htmlFor="patient-dropdown" className="clinical-label">
          <User size={15} className="text-slate-500" />
          <span>Select Verified Clinical Profile:</span>
        </label>
        <select
          id="patient-dropdown"
          value={selectedPatientId}
          onChange={(e) => onSelectPatient(e.target.value)}
          disabled={isLoading}
          className="clinical-select"
        >
          <option value="">-- Choose a patient profile from registry --</option>
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.age}y, {p.gender}) — {p.disease_label || p.disease}: {p.presentation}
            </option>
          ))}
        </select>
      </div>

      {/* Selected Patient Details Summary Panel */}
      {selectedPatient && (
        <div className="patient-summary-panel" id="selected-patient-panel">
          <div className="patient-header-bar">
            <div className="patient-name-group">
              <div className="patient-avatar">
                <User size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                  {selectedPatient.name}
                </h3>
                <span style={{ fontSize: '13px', color: '#0284c7', fontWeight: 600 }}>
                  {selectedPatient.disease_label || (selectedPatient.disease === 'diabetes' ? 'Diabetes Mellitus (Prameha)' : 'Respiratory Viral Infection')}
                </span>
              </div>
            </div>
            <span className="status-badge primary" style={{ fontSize: '12px' }}>
              Patient ID: {selectedPatient.id}
            </span>
          </div>

          <div className="patient-info-grid">
            <div className="patient-info-item">
              <span className="patient-info-label">Patient Name</span>
              <span className="patient-info-val">{selectedPatient.name}</span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Age & Sex</span>
              <span className="patient-info-val">
                {selectedPatient.age} years • {selectedPatient.gender}
              </span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Clinical ID</span>
              <span className="patient-info-val" style={{ fontFamily: 'var(--font-mono)' }}>
                {selectedPatient.id}
              </span>
            </div>

            <div className="patient-info-item">
              <span className="patient-info-label">Primary Diagnosis</span>
              <span className="patient-info-val" style={{ color: '#0284c7' }}>
                {selectedPatient.disease_label || selectedPatient.disease}
              </span>
            </div>
          </div>

          <div className="patient-info-item" style={{ marginTop: '4px' }}>
            <span className="patient-info-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Activity size={13} style={{ color: '#0284c7' }} />
              Clinical Presentation & Diagnostic Symptoms:
            </span>
            <div className="patient-presentation-box">
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
    </div>
  );
};
