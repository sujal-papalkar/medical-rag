import { apiClient } from './client';
import type { PatientListResponse, PatientProfile, TestCaseListResponse } from '../types';

export async function getPatients(): Promise<PatientListResponse> {
  return apiClient<PatientListResponse>('/api/v1/patients');
}

export async function getTestCases(): Promise<TestCaseListResponse> {
  return apiClient<TestCaseListResponse>('/api/v1/patients/test-cases');
}

export async function getPatientById(id: string): Promise<PatientProfile> {
  return apiClient<PatientProfile>(`/api/v1/patients/${id}`);
}
