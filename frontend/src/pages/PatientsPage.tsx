import React from 'react';
import { usePatients } from '../hooks/usePatients';
import { PatientSelector } from '../components/patients/PatientSelector';
import { UserCheck, Activity, FileText } from 'lucide-react';

interface PatientsPageProps {
  onProceedToPrescription?: () => void;
}

export const PatientsPage: React.FC<PatientsPageProps> = ({ onProceedToPrescription }) => {
  const {
    patients,
    selectedPatientId,
    selectedPatient,
    clinicalQuery,
    setClinicalQuery,
    handleSelectPatient,
  } = usePatients();

  return (
    <main className="clinical-main-container" id="patients-main-page">
      <div className="flex flex-col gap-1">
        <h1 className="clinical-card-title" style={{ fontSize: '24px' }}>
          <span>👥 Patient Directory & Clinical Profiles</span>
        </h1>
        <p className="clinical-card-subtitle">
          Select or review patient clinical profiles for evidence-grounded prescription generation.
        </p>
      </div>

      {/* Patient Selector Component */}
      <section id="select-patient-section">
        <PatientSelector
          patients={patients}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handleSelectPatient}
          clinicalQuery={clinicalQuery}
          onQueryChange={setClinicalQuery}
          isLoading={false}
        />
      </section>

      {/* Selected Patient Details Card */}
      {selectedPatient && (
        <section className="clinical-card" id="patient-details-card">
          <div className="clinical-card-header">
            <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <UserCheck size={16} className="text-blue-600" />
              <span>Active Patient Summary: {selectedPatient.name}</span>
            </h2>
            <span className="badge badge-primary text-xs">
              {selectedPatient.id}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
              <div className="font-semibold text-slate-700 flex items-center gap-1.5">
                <Activity size={14} className="text-slate-500" />
                <span>Demographics & Classification</span>
              </div>
              <div className="text-slate-600 space-y-1">
                <p><span className="font-medium text-slate-700">Age / Gender:</span> {selectedPatient.age} yrs • {selectedPatient.gender}</p>
                <p><span className="font-medium text-slate-700">Category:</span> {selectedPatient.diseaseLabel || selectedPatient.disease}</p>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
              <div className="font-semibold text-slate-700 flex items-center gap-1.5">
                <FileText size={14} className="text-slate-500" />
                <span>Clinical Presentation</span>
              </div>
              <p className="text-slate-600 leading-relaxed">
                {selectedPatient.presentation}
              </p>
            </div>
          </div>

          {onProceedToPrescription && (
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={onProceedToPrescription}
                className="btn btn-primary text-xs py-2 px-4 rounded-md font-semibold cursor-pointer"
              >
                Proceed to Prescription Generation &rarr;
              </button>
            </div>
          )}
        </section>
      )}
    </main>
  );
};

export default PatientsPage;
