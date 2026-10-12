import { useState } from 'react';
import { generatePrescription as apiGeneratePrescription } from '../api/prescriptions';
import type { StructuredPrescriptionResponse, PatientProfile } from '../types';

export function usePrescription() {
  const [prescription, setPrescription] = useState<StructuredPrescriptionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async (
    patient: PatientProfile | null,
    query: string,
    confirmOverride: boolean = false
  ) => {
    if (!patient && !query.trim()) {
      setError('Please select a patient or enter a clinical query.');
      return;
    }

    const queryToUse = query.trim() || patient?.clinical_query || (patient as any)?.clinicalQuery || '';
    if (!queryToUse) {
      setError('Clinical query cannot be empty.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiGeneratePrescription({
        patient_id: patient?.id,
        patient_info: patient
          ? {
              patient_id: patient.id,
              name: patient.name,
              age: patient.age,
              gender: patient.gender,
              disease: patient.disease,
              presentation: patient.presentation,
            }
          : undefined,
        query: queryToUse,
        disease: patient?.disease,
        top_k: 5,
        confirm_override: confirmOverride,
      });

      setPrescription(response);
    } catch (err: any) {
      console.error('Prescription generation failed:', err);
      setError(
        err.message ||
          'Failed to connect to prescription generation backend. Ensure FastAPI server is running on http://localhost:8000.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const reset = () => {
    setPrescription(null);
    setError(null);
  };

  return {
    prescription,
    isLoading,
    error,
    generate,
    reset,
  };
}
