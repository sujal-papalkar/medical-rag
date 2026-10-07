export type DiseaseType = 'diabetes' | 'respiratory_viral_infection';

export interface TestCase {
  test_id: string;
  disease: DiseaseType;
  title: string;
  question: string;
  relevant_chunk_ids: string[];
  expected_pages: number[];
  document_name?: string;
  section?: string;
  key_ground_truth_terms?: string[];
  verified: boolean;
  verification_notes?: string;
}

export interface QueryMetrics {
  mrr: number;
  first_relevant_rank: number | null;
  'hit@1': number;
  'hit@3': number;
  'hit@5': number;
  'hit@10': number;
  'precision@1': number;
  'precision@3': number;
  'precision@5': number;
  'precision@10': number;
  'recall@1': number;
  'recall@3': number;
  'recall@5': number;
  'recall@10': number;
  'f1@5': number;
  'f1@10': number;
  pass: boolean;
  pass_criteria: string;
}

export interface RetrievedChunk {
  rank: number;
  distance: number;
  chunk_id: string;
  document_name: string;
  page: number | null;
  disease: string;
  content_type: string;
  section?: string;
  content: string;
  is_relevant?: boolean;
  page_matches?: boolean;
}

export interface GroundTruthStatus {
  chunk_id: string;
  retrieved: boolean;
  rank: number | null;
  distance: number | null;
  page?: number | null;
  snippet?: string;
}

export interface TestCaseResult {
  test_id: string;
  title: string;
  disease: DiseaseType;
  question: string;
  relevant_chunk_ids: string[];
  expected_pages: number[];
  document_name?: string;
  section?: string;
  verified: boolean;
  metrics: QueryMetrics;
  ground_truth_status: GroundTruthStatus[];
  retrieved_chunks: RetrievedChunk[];
  total_retrieved: number;
}

export interface MetricSummary {
  count: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  mrr: number;
  'hit@1': number;
  'hit@3': number;
  'hit@5': number;
  'hit@10': number;
  'precision@1': number;
  'precision@3': number;
  'precision@5': number;
  'precision@10': number;
  'recall@1': number;
  'recall@3': number;
  'recall@5': number;
  'recall@10': number;
  'f1@5': number;
  'f1@10': number;
}

export interface EvaluationReport {
  metadata: {
    status: string;
    description: string;
    version: string;
    is_draft: boolean;
    last_updated?: string;
    total_test_cases: number;
    evaluation_top_k?: number;
    pass_k_threshold?: number;
    eval_timestamp?: string;
  };
  summary: {
    overall: MetricSummary;
    by_disease: Record<string, MetricSummary>;
    total_test_cases: number;
  };
  case_results: TestCaseResult[];
}
