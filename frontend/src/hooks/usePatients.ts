import { useState, useEffect } from 'react';
import { getPatients } from '../api/patients';
import { CLINICAL_PATIENTS as FALLBACK_PATIENTS } from '../utils/fallbackPatients';
import type { PatientProfile } from '../types';

export function usePatients() {
  const [patients, setPatients] = useState<PatientProfile[]>(FALLBACK_PATIENTS as unknown as PatientProfile[]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [clinicalQuery, setClinicalQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const res = await getPatients();
        if (res.patients && res.patients.length > 0) {
          setPatients(res.patients);
        }
      } catch (err: any) {
        console.warn('Could not fetch patients from API, using fallback patient profiles:', err.message);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const handleSelectPatient = (id: string) => {
    setSelectedPatientId(id);
    const found = patients.find((p) => p.id === id);
    if (found) {
      setClinicalQuery(found.clinical_query || (found as any).clinicalQuery || '');
    } else {
      setClinicalQuery('');
    }
  };

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  return {
    patients,
    selectedPatientId,
    selectedPatient,
    clinicalQuery,
    setClinicalQuery,
    handleSelectPatient,
    isLoading
  };
}
