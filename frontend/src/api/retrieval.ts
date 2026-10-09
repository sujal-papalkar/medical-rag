import { apiClient } from './client';
import type { RetrievalResponse, EvidenceSource } from '../types';

export async function searchRetrieval(
  question: string,
  disease?: string,
  top_k = 5
): Promise<RetrievalResponse> {
  return apiClient<RetrievalResponse>('/api/v1/retrieval/search', {
    method: 'POST',
    body: JSON.stringify({ question, disease, top_k }),
  });
}

export async function getChunkDetail(chunkId: string): Promise<EvidenceSource> {
  return apiClient<EvidenceSource>(`/api/v1/retrieval/chunks/${chunkId}`);
}
