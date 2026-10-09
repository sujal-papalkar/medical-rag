export interface GuidelineDocument {
  id: string;
  name: string;
  disease_category?: string;
  diseaseCategory?: string;
  uploaded_at?: string;
  uploadedAt?: string;
  chunks_indexed?: number;
  chunksIndexed?: number;
  status: 'Indexed' | 'Staged' | 'Processing';
  description?: string;
}

export interface DocumentUploadResponse {
  status: string;
  message: string;
  document: GuidelineDocument;
}

export interface DocumentListResponse {
  total: number;
  documents: GuidelineDocument[];
}
