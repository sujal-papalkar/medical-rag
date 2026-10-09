import type { EvidenceSource } from './retrieval';

export interface ResolvedMedicineCitation {
  chunk_id: string;
  document_name: string;
  page: number | null;
  page_display: string;
  has_verified_page: boolean;
  section?: string | null;
  content?: string | null;
  rank?: number;
  distance?: number;
}

export interface MedicineItem {
  medicine: string;
  dose?: string | null;
  dosage_form?: string | null;
  route?: string | null;
  frequency?: string | null;
  timing?: string | null;
  duration?: string | null;
  anupana?: string | null;
  special_instructions?: string | null;
  supporting_chunk_ids?: string[];
  citations?: ResolvedMedicineCitation[];
}

export interface ClinicalGuidance {
  condition: string;
  severity_or_stage?: string | null;
  guidance_summary: string;
  key_recommendations?: string[];
}

export interface PatientInfo {
  patient_id?: string | null;
  name?: string | null;
  age?: number | null;
  gender?: string | null;
  disease?: string | null;
  presentation?: string | null;
}

export interface ClinicalConflict {
  parameter: string;
  registered_value: any;
  query_value: any;
  conflict_type: string;
  message: string;
}

export interface StructuredPrescriptionResponse {
  patient: PatientInfo;
  clinical_guidance: ClinicalGuidance;
  medicines: MedicineItem[];
  prescription?: MedicineItem[];
  evidence_sources: EvidenceSource[];
  evidence?: EvidenceSource[];
  limitations: string[];
  conflicts?: ClinicalConflict[];
  requires_confirmation?: boolean;
  status: 'success' | 'partial_success' | 'insufficient_context' | 'conflict_detected' | 'validation_error' | string;
  validation_status: 'valid' | 'conflict_pending_confirmation' | 'validation_fallback' | string;
  model?: string | null;
  query: string;
  raw_answer?: string | null;
}

export interface PrescriptionGenerateRequest {
  patient_id?: string | null;
  query: string;
  disease?: string | null;
  top_k?: number;
  confirm_override?: boolean;
}
