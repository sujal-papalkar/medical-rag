export interface PatientProfile {
  id: string;
  name: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  disease: 'diabetes' | 'respiratory_viral_infection';
  disease_label?: string;
  diseaseLabel?: string;
  presentation: string;
  clinical_query?: string;
  clinicalQuery?: string;
  is_test?: boolean;
  symptoms?: string;
  clinical_parameters?: string;
  comorbidities?: string;
  test_number?: number;
  expected_behavior?: string;
  supporting_source_page?: number;
  pass_status?: string;
  failure_reason?: string;
}

export interface PatientListResponse {
  total: number;
  patients: PatientProfile[];
}

export interface TestCaseListResponse {
  total: number;
  test_cases: PatientProfile[];
}
