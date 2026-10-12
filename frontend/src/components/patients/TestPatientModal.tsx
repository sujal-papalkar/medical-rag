import React, { useState } from 'react';
import { X, FlaskConical, Sparkles, Check, Info } from 'lucide-react';
import type { PatientProfile } from '../../types';

interface TestPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddTestPatient: (patient: PatientProfile) => void;
}

interface TestPreset {
  label: string;
  name: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  disease: 'diabetes' | 'respiratory_viral_infection';
  symptoms: string;
  clinical_parameters: string;
  comorbidities: string;
}

const PRESETS: TestPreset[] = [
  {
    label: 'Mild Respiratory (Adult, SpO₂ 96%, HRCT 3)',
    name: 'Test - Mild Respiratory Viral Infection',
    age: 34,
    gender: 'Female',
    disease: 'respiratory_viral_infection',
    symptoms: 'Mild dry cough, low-grade fever, throat irritation, fatigue',
    clinical_parameters: 'HRCT score 3 (range 0 to 8), SpO2 96% on room air',
    comorbidities: 'None',
  },
  {
    label: 'Moderate Respiratory (Adult, SpO₂ 92%, HRCT 12)',
    name: 'Test - Moderate Respiratory Viral Infection',
    age: 52,
    gender: 'Male',
    disease: 'respiratory_viral_infection',
    symptoms: 'Productive cough, continuous fever, mild dyspnea on exertion',
    clinical_parameters: 'HRCT score 12 (range 9 to 15), SpO2 92% on room air',
    comorbidities: 'Hypertension (controlled)',
  },
  {
    label: 'Diabetic Nephropathy Stage 3 (GFR 45)',
    name: 'Test - Diabetic Nephropathy Stage 3',
    age: 60,
    gender: 'Male',
    disease: 'diabetes',
    symptoms: 'Bilateral pedal edema (Shoth), Agnimandya (impaired digestion), fatigue',
    clinical_parameters: 'GFR 45 ml/min (Stage 3), Serum Creatinine 2.1 mg/dL, HbA1c 8.2%',
    comorbidities: 'Hypertension, Stage 3 Diabetic Kidney Disease',
  },
  {
    label: 'Pediatric Respiratory (<15 years)',
    name: 'Test - Pediatric Respiratory Viral Infection',
    age: 9,
    gender: 'Male',
    disease: 'respiratory_viral_infection',
    symptoms: 'Acute dry cough, nasal congestion, mild fever for 2 days',
    clinical_parameters: 'SpO2 98% on room air, RR 22/min, chest clear',
    comorbidities: 'None',
  },
  {
    label: 'Pre-Diabetes High Risk (BMI 28)',
    name: 'Test - High-Risk Pre-Diabetes',
    age: 45,
    gender: 'Female',
    disease: 'diabetes',
    symptoms: 'General lethargy, mild polydipsia, high caloric intake',
    clinical_parameters: 'Fasting Plasma Glucose 118 mg/dL, HbA1c 6.2%, BMI 28.4 kg/m²',
    comorbidities: 'Strong family history of Type 2 Diabetes, Overweight',
  },
];

export const TestPatientModal: React.FC<TestPatientModalProps> = ({
  isOpen,
  onClose,
  onAddTestPatient,
}) => {
  const [name, setName] = useState('Test Patient - Scenario A');
  const [age, setAge] = useState<number | ''>(34);
  const [gender, setGender] = useState<'Male' | 'Female' | 'Other'>('Female');
  const [disease, setDisease] = useState<'diabetes' | 'respiratory_viral_infection'>('respiratory_viral_infection');
  const [symptoms, setSymptoms] = useState('Mild dry cough, low-grade fever, throat irritation');
  const [clinicalParameters, setClinicalParameters] = useState('HRCT score 3 (range 0 to 8), SpO2 96% on room air');
  const [comorbidities, setComorbidities] = useState('None');
  const [errors, setErrors] = useState<{ [key: string]: string }>({});

  if (!isOpen) return null;

  const handleApplyPreset = (preset: TestPreset) => {
    setName(preset.name);
    setAge(preset.age);
    setGender(preset.gender);
    setDisease(preset.disease);
    setSymptoms(preset.symptoms);
    setClinicalParameters(preset.clinical_parameters);
    setComorbidities(preset.comorbidities);
    setErrors({});
  };

  const validate = (): boolean => {
    const errs: { [key: string]: string } = {};

    if (!name.trim()) {
      errs.name = 'Patient name or test label is required.';
    }

    if (age === '' || isNaN(Number(age))) {
      errs.age = 'Age is required.';
    } else if (Number(age) < 1 || Number(age) > 120) {
      errs.age = 'Age must be between 1 and 120.';
    }

    if (!gender) {
      errs.gender = 'Gender must be selected.';
    }

    if (!disease) {
      errs.disease = 'Primary disease category is required.';
    }

    if (!symptoms.trim()) {
      errs.symptoms = 'Clinical symptoms must be specified.';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const ageNum = Number(age);
    const diseaseLabel =
      disease === 'diabetes'
        ? 'Diabetes Mellitus (Prameha)'
        : 'Respiratory Viral Infection (Kasa / Jwara)';

    // Build synthesized clinical presentation
    const presentationParts: string[] = [symptoms.trim()];
    if (clinicalParameters.trim()) {
      presentationParts.push(`Parameters: ${clinicalParameters.trim()}`);
    }
    if (comorbidities.trim() && comorbidities.trim().toLowerCase() !== 'none') {
      presentationParts.push(`Comorbidities: ${comorbidities.trim()}`);
    }
    const fullPresentation = presentationParts.join(' • ');

    // Formulate initial clinical query
    const diseaseShort = disease === 'diabetes' ? 'diabetes mellitus' : 'respiratory viral infection';
    const initialQuery = `For a ${ageNum}-year-old ${gender.toLowerCase()} presenting with ${diseaseShort}: symptoms of ${symptoms.trim()}${clinicalParameters.trim() ? `, ${clinicalParameters.trim()}` : ''}${comorbidities.trim() && comorbidities.trim().toLowerCase() !== 'none' ? `, comorbidity: ${comorbidities.trim()}` : ''}. According to Ayurvedic clinical guidelines, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?`;

    const uniqueId = `TEST-TMP-${Math.floor(1000 + Math.random() * 9000)}`;

    const newTestPatient: PatientProfile = {
      id: uniqueId,
      name: name.trim(),
      age: ageNum,
      gender,
      disease,
      disease_label: diseaseLabel,
      diseaseLabel,
      presentation: fullPresentation,
      clinical_query: initialQuery,
      clinicalQuery: initialQuery,
      is_test: true,
      symptoms: symptoms.trim(),
      clinical_parameters: clinicalParameters.trim(),
      comorbidities: comorbidities.trim(),
    };

    onAddTestPatient(newTestPatient);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs"
      id="test-patient-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        id="test-patient-modal-card"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-amber-50/60">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-lg bg-amber-100 text-amber-800 border border-amber-200">
              <FlaskConical size={18} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-base">Add Temporary Test Patient</h3>
                <span className="status-badge" style={{ backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fde68a', fontSize: '11px', padding: '2px 8px' }}>
                  Unverified Test Profile
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Define custom patient parameters to evaluate RAG retrieval and query variations without altering registry records.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-sm" style={{ maxHeight: 'calc(92vh - 130px)' }}>
          {/* Quick Presets Section */}
          <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-200">
            <div className="flex items-center gap-1.5 mb-2 font-semibold text-xs text-slate-700">
              <Sparkles size={14} className="text-amber-600" />
              <span>Quick Test Presets (Click to Auto-Fill):</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleApplyPreset(p)}
                  className="px-2.5 py-1 text-xs font-medium bg-white hover:bg-amber-50 text-slate-700 hover:text-amber-800 border border-slate-300 hover:border-amber-400 rounded-md transition-all shadow-xs"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <form id="test-patient-form" onSubmit={handleSubmit} className="space-y-4">
            {/* 1. Profile Label */}
            <div className="clinical-form-group">
              <label htmlFor="test-patient-name" className="clinical-label text-xs">
                <span>Test Profile Name / Scenario Label:</span>
                <span className="text-red-500">*</span>
              </label>
              <input
                id="test-patient-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Test Patient - 34yo Mild Respiratory"
                className="clinical-select"
                style={{ cursor: 'text' }}
              />
              {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name}</p>}
            </div>

            {/* 2. Demographics Row (Age, Gender, Disease) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Age */}
              <div className="clinical-form-group">
                <label htmlFor="test-patient-age" className="clinical-label text-xs">
                  <span>Age (Years):</span>
                  <span className="text-red-500">*</span>
                </label>
                <input
                  id="test-patient-age"
                  type="number"
                  min="1"
                  max="120"
                  value={age}
                  onChange={(e) => setAge(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                  placeholder="e.g. 34"
                  className="clinical-select"
                  style={{ cursor: 'text' }}
                />
                {errors.age && <p className="text-xs text-red-600 mt-1">{errors.age}</p>}
              </div>

              {/* Gender */}
              <div className="clinical-form-group">
                <label htmlFor="test-patient-gender" className="clinical-label text-xs">
                  <span>Gender:</span>
                  <span className="text-red-500">*</span>
                </label>
                <select
                  id="test-patient-gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value as any)}
                  className="clinical-select"
                >
                  <option value="Female">Female</option>
                  <option value="Male">Male</option>
                  <option value="Other">Other</option>
                </select>
                {errors.gender && <p className="text-xs text-red-600 mt-1">{errors.gender}</p>}
              </div>

              {/* Disease */}
              <div className="clinical-form-group">
                <label htmlFor="test-patient-disease" className="clinical-label text-xs">
                  <span>Disease Category:</span>
                  <span className="text-red-500">*</span>
                </label>
                <select
                  id="test-patient-disease"
                  value={disease}
                  onChange={(e) => setDisease(e.target.value as any)}
                  className="clinical-select"
                >
                  <option value="respiratory_viral_infection">Respiratory Viral Infection</option>
                  <option value="diabetes">Diabetes Mellitus</option>
                </select>
                {errors.disease && <p className="text-xs text-red-600 mt-1">{errors.disease}</p>}
              </div>
            </div>

            {/* 3. Symptoms */}
            <div className="clinical-form-group">
              <label htmlFor="test-patient-symptoms" className="clinical-label text-xs">
                <span>Clinical Symptoms & Presentation:</span>
                <span className="text-red-500">*</span>
              </label>
              <textarea
                id="test-patient-symptoms"
                rows={2}
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                placeholder="e.g. Dry cough, low-grade fever, sore throat, fatigue"
                className="clinical-textarea"
                style={{ minHeight: '68px' }}
              />
              {errors.symptoms && <p className="text-xs text-red-600 mt-1">{errors.symptoms}</p>}
            </div>

            {/* 4. Diagnostic & Clinical Parameters */}
            <div className="clinical-form-group">
              <label htmlFor="test-patient-parameters" className="clinical-label text-xs">
                <span>Clinical Parameters (HRCT Score, SpO₂, GFR, Blood Sugar, BMI):</span>
              </label>
              <input
                id="test-patient-parameters"
                type="text"
                value={clinicalParameters}
                onChange={(e) => setClinicalParameters(e.target.value)}
                placeholder="e.g. HRCT score 0 to 8, SpO2 above 94%, GFR 45 ml/min"
                className="clinical-select"
                style={{ cursor: 'text' }}
              />
              <span className="text-[12px] text-slate-500">
                Used by RAG clinical table matching (e.g. mild 0–8 HRCT vs moderate 9–15 HRCT vs GFR Stage 3).
              </span>
            </div>

            {/* 5. Comorbidities */}
            <div className="clinical-form-group">
              <label htmlFor="test-patient-comorbidities" className="clinical-label text-xs">
                <span>Comorbidities:</span>
              </label>
              <input
                id="test-patient-comorbidities"
                type="text"
                value={comorbidities}
                onChange={(e) => setComorbidities(e.target.value)}
                placeholder="e.g. None, Hypertension, Diabetes Mellitus, Bronchial Asthma"
                className="clinical-select"
                style={{ cursor: 'text' }}
              />
              <span className="text-[12px] text-slate-500">
                Type &ldquo;None&rdquo; if no comorbidities. Comorbidities trigger comorbidity-specific guideline isolation.
              </span>
            </div>

            {/* Safety & Notice Banner */}
            <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
              <Info size={16} className="text-amber-700 shrink-0 mt-0.5" />
              <div>
                <strong>Isolation Guarantee:</strong> This test profile will be maintained in your current session for testing RAG query variations. The authoritative seven registered patient profiles remain permanent and immutable.
              </div>
            </div>
          </form>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="clinical-btn-secondary"
            style={{ padding: '8px 16px', fontSize: '13px' }}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="test-patient-form"
            className="clinical-btn-primary"
            style={{ padding: '8px 20px', fontSize: '13px', backgroundColor: '#d97706', borderColor: '#b45309' }}
            id="save-test-patient-btn"
          >
            <Check size={16} />
            <span>Create & Select Test Patient</span>
          </button>
        </div>
      </div>
    </div>
  );
};
