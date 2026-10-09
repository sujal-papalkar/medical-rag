import type { PatientProfile } from '../types';

export const CLINICAL_PATIENTS: PatientProfile[] = [
  {
    id: 'PAT-DM-001',
    name: 'Rajesh Sharma',
    age: 54,
    gender: 'Male',
    disease: 'diabetes',
    diseaseLabel: 'Diabetes Mellitus (Prameha)',
    presentation: 'Type 2 Diabetes presenting with Trushna (Polydipsia) and Aruchi (Impaired Taste)',
    clinicalQuery:
      'A patient with diabetes mellitus presents with Trushna (polydipsia) and Aruchi (impaired taste). According to the guideline, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?',
  },
  {
    id: 'PAT-DM-002',
    name: 'Sunita Patil',
    age: 48,
    gender: 'Female',
    disease: 'diabetes',
    diseaseLabel: 'Diabetes Mellitus (Prameha)',
    presentation: 'High-risk pre-diabetes, Overweight with BMI >= 25 and strong family history of Diabetes Mellitus',
    clinicalQuery:
      'What are the primary prevention guidelines and recommended Rasayana medications for high-risk individuals with family history of diabetes mellitus or overweight (BMI >= 25)?',
  },
  {
    id: 'PAT-DM-003',
    name: 'Ramesh Gupta',
    age: 62,
    gender: 'Male',
    disease: 'diabetes',
    diseaseLabel: 'Diabetes Mellitus (Prameha)',
    presentation: 'Diabetic Nephropathy Stage 3 complications (GFR 30-59%, Creatinine 4-6) with Shoth (edema) and Agnimandya',
    clinicalQuery:
      'In diabetic nephropathy Stage 3 complications with GFR 30-59% and creatinine 4 to 6 presenting with Shoth and Agnimandya, what are the prescribed medicines, Matra, Sahpaan, and Aushadh Kal?',
  },
  {
    id: 'PAT-RESP-001',
    name: 'Priya Kulkarni',
    age: 32,
    gender: 'Female',
    disease: 'respiratory_viral_infection',
    diseaseLabel: 'Respiratory Viral Infection (Kasa / Jwara)',
    presentation: 'Mild respiratory viral infection with HRCT score 0 to 8 and SpO2 above 94% without dyspnea',
    clinicalQuery:
      'For a patient presenting with mild respiratory viral infection (HRCT score 0 to 8, SpO2 above 94%) without severe dyspnea, what are the recommended Rasayana formulations, dosages, and Sahpaan?',
  },
  {
    id: 'PAT-RESP-002',
    name: 'Amit Deshmukh',
    age: 58,
    gender: 'Male',
    disease: 'respiratory_viral_infection',
    diseaseLabel: 'Respiratory Viral Infection (Kasa / Jwara)',
    presentation: 'Adult with respiratory viral infection presenting with Diabetes Mellitus comorbidity (Udakvah srotas vyadhi) and SpO2 > 94%',
    clinicalQuery:
      'For an adult patient with respiratory viral infection who has diabetes mellitus comorbidity (Udakvah srotas vyadhi) and mild HRCT score 0 to 8 with SpO2 above 94, what are the recommended medicines and doses?',
  },
  {
    id: 'PAT-RESP-003',
    name: 'Anjali Verma',
    age: 41,
    gender: 'Female',
    disease: 'respiratory_viral_infection',
    diseaseLabel: 'Respiratory Viral Infection (Kasa / Jwara)',
    presentation: 'Post-viral convalescence with persistent fatigue, dry cough, and reduced vital capacity',
    clinicalQuery:
      'What are the recommended post-recovery Rasayana and restorative formulations for patients recovering from acute respiratory viral infection?',
  },
];
