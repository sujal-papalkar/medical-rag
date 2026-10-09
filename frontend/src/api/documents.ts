import { API_BASE_URL, apiClient } from './client';
import type { DocumentListResponse, DocumentUploadResponse } from '../types';

export async function getDocuments(): Promise<DocumentListResponse> {
  return apiClient<DocumentListResponse>('/api/v1/documents');
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const url = `${API_BASE_URL}/api/v1/documents/upload?filename=${encodeURIComponent(file.name)}`;
  const buffer = await file.arrayBuffer();

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-Filename': file.name,
    },
    body: buffer,
  });

  if (!response.ok) {
    const errorJson = await response.json().catch(() => ({}));
    throw new Error(errorJson.detail || `Upload failed: ${response.statusText}`);
  }

  return response.json();
}
