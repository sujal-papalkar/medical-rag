import { apiClient } from './client';
import type { StructuredPrescriptionResponse, PrescriptionGenerateRequest } from '../types';

export async function generatePrescription(
  payload: PrescriptionGenerateRequest
): Promise<StructuredPrescriptionResponse> {
  return apiClient<StructuredPrescriptionResponse>('/api/v1/prescriptions/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
