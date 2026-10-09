import { apiClient } from './client';
import type { PatientListResponse, PatientProfile } from '../types';

export async function getPatients(): Promise<PatientListResponse> {
  return apiClient<PatientListResponse>('/api/v1/patients');
}

export async function getPatientById(id: string): Promise<PatientProfile> {
  return apiClient<PatientProfile>(`/api/v1/patients/${id}`);
}
