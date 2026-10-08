export type DiseaseType = 'diabetes' | 'respiratory_viral_infection' | '';

export interface PatientProfile {
  id: string;
  name: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  disease: 'diabetes' | 'respiratory_viral_infection';
  diseaseLabel: string;
  presentation: string;
  clinicalQuery: string;
}

export interface GuidelineDocument {
  id: string;
  name: string;
  diseaseCategory: string;
  uploadedAt: string;
  chunksIndexed: number;
  status: 'Indexed' | 'Staged' | 'Processing';
  description?: string;
}

export interface GenerationSource {
  chunk_id: string;
  document_name: string;
  disease?: string;
  section?: string;
  page?: number | null;
  rank?: number;
  distance?: number;
}

export interface GenerationResult {
  query: string;
  disease?: string;
  answer: string;
  sources: GenerationSource[];
  limitations?: string;
  model?: string;
  status: 'success' | 'partial' | 'error' | 'insufficient_context';
  error?: string;
  notice?: string;
}
