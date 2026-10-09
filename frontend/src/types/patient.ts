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
}

export interface PatientListResponse {
  total: number;
  patients: PatientProfile[];
}
