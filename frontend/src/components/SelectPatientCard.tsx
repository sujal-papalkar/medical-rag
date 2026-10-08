import React from 'react';
import { User, Activity, AlertCircle, Edit3 } from 'lucide-react';
import type { PatientProfile } from '../types';

interface SelectPatientCardProps {
  patients: PatientProfile[];
  selectedPatientId: string;
  onSelectPatient: (patientId: string) => void;
  clinicalQuery: string;
  onQueryChange: (query: string) => void;
  isLoading: boolean;
}

export const SelectPatientCard: React.FC<SelectPatientCardProps> = ({
  patients,
  selectedPatientId,
  onSelectPatient,
  clinicalQuery,
  onQueryChange,
  isLoading,
}) => {
  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  return (
    <div className="card" id="select-patient-card">
      {/* Card Header */}
      <div className="card-header pb-3 border-b border-slate-200">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>👤 2. Select Patient</span>
        </h2>
      </div>

      <div className="pt-4 space-y-4">
        {/* Dropdown Selector */}
        <div className="form-group">
          <label htmlFor="patient-dropdown" className="text-xs font-semibold text-slate-700 block mb-1.5">
            Select a patient:
          </label>
          <select
            id="patient-dropdown"
            value={selectedPatientId}
            onChange={(e) => onSelectPatient(e.target.value)}
            disabled={isLoading}
            className="form-select w-full text-sm font-normal py-2 px-3 border border-slate-300 rounded-lg bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">-- Select a patient --</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.age}{p.gender === 'Male' ? 'M' : 'F'}) — {p.diseaseLabel}: {p.presentation}
              </option>
            ))}
          </select>
        </div>

        {/* Selected Patient Details Preview */}
        {selectedPatient ? (
          <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">
                  <User size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {selectedPatient.name}{' '}
                    <span className="text-xs font-normal text-slate-500">
                      ({selectedPatient.age} yrs, {selectedPatient.gender})
                    </span>
                  </h3>
                  <p className="text-xs text-blue-700 font-medium">
                    {selectedPatient.diseaseLabel}
                  </p>
                </div>
              </div>
              <span className="badge badge-primary text-[11px] font-semibold">
                ID: {selectedPatient.id}
              </span>
            </div>

            {/* Clinical Presentation */}
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 mb-1">
                <Activity size={13} className="text-blue-600" />
                <span>Clinical Presentation:</span>
              </div>
              <p className="text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200 leading-relaxed">
                {selectedPatient.presentation}
              </p>
            </div>

            {/* Editable Clinical Query Textarea */}
            <div>
              <div className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span className="flex items-center gap-1.5">
                  <Edit3 size={13} className="text-slate-600" />
                  <span>Clinical Query / Guideline Parameters:</span>
                </span>
                <span className="text-[11px] font-normal text-slate-400">
                  Editable for custom physician inputs
                </span>
              </div>
              <textarea
                rows={3}
                value={clinicalQuery}
                onChange={(e) => onQueryChange(e.target.value)}
                disabled={isLoading}
                placeholder="Enter patient information or clinical query..."
                className="w-full text-xs text-slate-800 p-2.5 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-sans leading-relaxed"
              />
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500 p-3 bg-slate-50 rounded-lg border border-dashed border-slate-200 flex items-center gap-2">
            <AlertCircle size={14} className="text-slate-400 shrink-0" />
            <span>Select a patient from the dropdown above to view clinical presentation and proceed to prescription generation.</span>
          </div>
        )}
      </div>
    </div>
  );
};
