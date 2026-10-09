export interface EvidenceSource {
  chunk_id: string;
  document_name: string;
  disease?: string;
  section?: string;
  page?: number | null;
  rank?: number;
  distance?: number;
  content?: string;
}

export interface RetrievalResponse {
  query: string;
  disease?: string;
  top_k: number;
  retrieved_chunks: EvidenceSource[];
  total_retrieved: number;
  metrics?: Record<string, any>;
}
