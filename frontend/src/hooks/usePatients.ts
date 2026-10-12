import { useState, useEffect, useMemo } from 'react';
import { getPatients, getTestCases } from '../api/patients';
import { CLINICAL_PATIENTS as FALLBACK_PATIENTS } from '../utils/fallbackPatients';
import type { PatientProfile } from '../types';

const STORAGE_KEY = 'ayurrag_test_patients';

function loadStoredTestPatients(): PatientProfile[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch (err) {
    console.warn('Failed to parse test patients from session storage:', err);
  }
  return [];
}

export function usePatients() {
  const [registeredPatients, setRegisteredPatients] = useState<PatientProfile[]>(
    FALLBACK_PATIENTS as unknown as PatientProfile[]
  );
  const [benchmarkTestCases, setBenchmarkTestCases] = useState<PatientProfile[]>([]);
  const [customTestPatients, setCustomTestPatients] = useState<PatientProfile[]>(loadStoredTestPatients);
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [clinicalQuery, setClinicalQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const [patientsRes, testCasesRes] = await Promise.allSettled([
          getPatients(),
          getTestCases(),
        ]);
        if (patientsRes.status === 'fulfilled' && patientsRes.value.patients?.length > 0) {
          setRegisteredPatients(patientsRes.value.patients);
        }
        if (testCasesRes.status === 'fulfilled' && testCasesRes.value.test_cases?.length > 0) {
          setBenchmarkTestCases(testCasesRes.value.test_cases);
        }
      } catch (err: any) {
        console.warn('Could not fetch patients or test cases:', err.message);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  // Combined patients: registered profiles first, followed by benchmark test scenarios, then custom test profiles
  const patients = useMemo(() => {
    return [...registeredPatients, ...benchmarkTestCases, ...customTestPatients];
  }, [registeredPatients, benchmarkTestCases, customTestPatients]);

  const handleSelectPatient = (id: string) => {
    setSelectedPatientId(id);
    const found = patients.find((p) => p.id === id);
    if (found) {
      setClinicalQuery(found.clinical_query || (found as any).clinicalQuery || '');
    } else {
      setClinicalQuery('');
    }
  };

  const handleAddTestPatient = (newTestPatient: PatientProfile) => {
    setCustomTestPatients((prev) => {
      const updated = [newTestPatient, ...prev];
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (e) {
        console.warn('Could not save test patient to sessionStorage:', e);
      }
      return updated;
    });

    // Auto-select the newly added test patient
    setSelectedPatientId(newTestPatient.id);
    setClinicalQuery(newTestPatient.clinical_query || (newTestPatient as any).clinicalQuery || '');
  };

  const handleRemoveTestPatient = (id: string) => {
    setCustomTestPatients((prev) => {
      const updated = prev.filter((p) => p.id !== id);
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (e) {
        console.warn('Could not update test patients in sessionStorage:', e);
      }
      return updated;
    });

    if (selectedPatientId === id) {
      setSelectedPatientId('');
      setClinicalQuery('');
    }
  };

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  return {
    patients,
    registeredPatients,
    benchmarkTestCases,
    testPatients: customTestPatients,
    selectedPatientId,
    selectedPatient,
    clinicalQuery,
    setClinicalQuery,
    handleSelectPatient,
    handleAddTestPatient,
    handleRemoveTestPatient,
    isLoading,
  };
}

