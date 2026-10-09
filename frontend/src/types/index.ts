export * from './document';
export * from './patient';
export * from './retrieval';
export * from './prescription';

export type DiseaseType = 'diabetes' | 'respiratory_viral_infection' | '';

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

// Legacy dashboard types for backward compatibility with unused modal components
export interface MetricSummary {
  hit1?: number;
  hit3?: number;
  hit5?: number;
  hit10?: number;
  mrr?: number;
  [key: string]: any;
}

export interface TestCaseResult {
  test_id: string;
  disease?: string;
  question?: string;
  metrics?: any;
  [key: string]: any;
}

export interface RetrievedChunk {
  chunk_id: string;
  content?: string;
  document_name?: string;
  page?: number;
  [key: string]: any;
}

export interface QueryMetrics {
  [key: string]: any;
}

export interface EvaluationReport {
  [key: string]: any;
}
