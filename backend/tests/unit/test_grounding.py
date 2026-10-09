"""
Unit tests for Hallucination Detection in GenerationEvaluator.
Verifies:
1. The 6 known false positive strings from the 20-case evaluation are NOT extracted as medicines.
2. Legitimate Ayurvedic formulations (e.g. Somtajvir, Shamani Tail, Jyeshta Ghrita, Pranvallabh Rasayan) ARE extracted cleanly.
3. Limitation statements under '### 3. Limitations & Missing Information' do not produce spurious medicine entities.
4. Real hallucinations (fabricated medicine names or unsupported dosages) ARE properly extracted and flagged.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import unittest
from evaluation.evaluators.generation_evaluator import (
    extract_prescribed_medicines,
    clean_medicine_candidate,
    GenerationEvaluator,
    normalize_text
)


class TestHallucinationEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = GenerationEvaluator()

    # ------------------------------------------------------------------
    # 1. Tests for the 6 Known False Positives from the 20-Case Evaluation
    # ------------------------------------------------------------------

    def test_tc02_sev02_intro_rasayana_not_extracted(self):
        """TC-02-SEV-02: 'the guideline provides the following therapeutic Rasayana' must not be extracted."""
        text = (
            "### 1. Clinical Guidance\n"
            "For patients above 15 years with Pranvah Srotas vyadhi presenting with severe "
            "respiratory viral infection (HRCT score > 15 and SpO2 below 90), the guideline "
            "provides the following therapeutic Rasayana protocol:\n"
            "| Medicine | Matra |\n"
            "| Somtajvir | 1-1-1 |\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("the guideline provides the following therapeutic Rasayana", meds)
        self.assertNotIn("therapeutic Rasayana", meds)
        self.assertIn("Somtajvir", meds)

    def test_tc03_com02_intro_prophylactic_rasayana_not_extracted(self):
        """TC-03-COM-02: 'the following prophylactic Rasayana' must not be extracted."""
        text = (
            "### 1. Clinical Guidance\n"
            "For patients with a past history of malignancy or active/under treatment Granthi/Arbud "
            "(Malignancies), the following prophylactic Rasayana options are specified in the guidelines:\n"
            "* Past history of malignancy: Sinurbhushan Rasayan (Matra: 1-0-0)\n"
            "* Active / under treatment: Arpisa Rasayan (Matra: 1-0-0)\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("the following prophylactic Rasayana", meds)
        self.assertNotIn("prophylactic Rasayana", meds)
        self.assertIn("Sinurbhushan Rasayan", meds)
        self.assertIn("Arpisa Rasayan", meds)

    def test_tc05_int02_sahpaan_for_shamani_tail_not_extracted(self):
        """TC-05-INT-02: 'Sahpaan for Shamani Tail' in limitations must not be extracted as a medicine entity."""
        text = (
            "### 1. Clinical Guidance\n"
            "* If Vatadhikya: Shamani Tail nasya, 2 Drops, Pratimarsha nasya kal\n"
            "### 3. Limitations & Missing Information\n"
            "* The vehicle/Sahpaan for Shamani Tail nasya is not specified in the provided guideline.\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("Sahpaan for Shamani Tail", meds)
        self.assertIn("Shamani Tail", meds)

    def test_tc06_sym02_matra_for_jyeshta_ghrita_not_extracted(self):
        """TC-06-SYM-02: 'The Matra for Jyeshta Ghrita' in limitations must not be extracted as a medicine entity."""
        text = (
            "### 1. Clinical Guidance\n"
            "* Medicine: Jyeshta Ghrita\n"
            "### 3. Limitations & Missing Information\n"
            "* The Matra for Jyeshta Ghrita in the management of Mukhshushkata is not specified in the provided guideline.\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("The Matra for Jyeshta Ghrita", meds)
        self.assertIn("Jyeshta Ghrita", meds)

    def test_tc07_med01_prophylactic_rasayana_not_extracted(self):
        """TC-07-MED-01: 'the prophylactic Rasayana' must not be extracted."""
        text = (
            "### 1. Clinical Guidance\n"
            "For a patient with respiratory viral infection who has Asthma or COPD and is on regular "
            "inhalers, the prophylactic Rasayana guideline specifies the following recommendation:\n"
            "| Comorbidities | Medicine | Matra |\n"
            "| Asthama / COPD | Pranvallabh Rasayan | 1-0-0 |\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("the prophylactic Rasayana", meds)
        self.assertNotIn("prophylactic Rasayana", meds)
        self.assertIn("Pranvallabh Rasayan", meds)

    def test_tc09_mis02_following_rasayana_not_extracted(self):
        """TC-09-MIS-02: 'the following Rasayana' must not be extracted."""
        text = (
            "### 1. Clinical Guidance\n"
            "For people with no significant comorbidities during seasonal or epidemic viral infections, "
            "the following Rasayana options are recommended for prophylactic use (Nitya Rasayan Sevan):\n"
            "- Pranvir (Matra: 2-0-2)\n"
            "- Rasaka Rasayana (Matra: 1-0-0)\n"
        )
        meds = extract_prescribed_medicines(text)
        self.assertNotIn("the following Rasayana", meds)
        self.assertNotIn("following Rasayana", meds)
        self.assertIn("Pranvir", meds)
        self.assertIn("Rasaka Rasayana", meds)

    # ------------------------------------------------------------------
    # 2. Candidate Cleaner Unit Tests
    # ------------------------------------------------------------------

    def test_clean_medicine_candidate(self):
        self.assertIsNone(clean_medicine_candidate("the guideline provides the following therapeutic Rasayana"))
        self.assertIsNone(clean_medicine_candidate("the following prophylactic Rasayana"))
        self.assertIsNone(clean_medicine_candidate("therapeutic Rasayana"))
        self.assertIsNone(clean_medicine_candidate("prophylactic Rasayana"))
        self.assertIsNone(clean_medicine_candidate("Rasayana"))
        self.assertIsNone(clean_medicine_candidate("Ghrita"))

        self.assertEqual(clean_medicine_candidate("The Matra for Jyeshta Ghrita"), "Jyeshta Ghrita")
        self.assertEqual(clean_medicine_candidate("Sahpaan for Shamani Tail"), "Shamani Tail")
        self.assertEqual(clean_medicine_candidate("Add Sutendra Rasayana"), "Sutendra Rasayana")
        self.assertEqual(clean_medicine_candidate("Somtajvir 1-1-1"), "Somtajvir")
        self.assertEqual(clean_medicine_candidate("Pranvallabh Rasayan"), "Pranvallabh Rasayan")

    # ------------------------------------------------------------------
    # 3. Real Hallucinations ARE Properly Detected
    # ------------------------------------------------------------------

    def test_real_hallucination_invented_medicine_detected(self):
        """Verifies that an invented medicine NOT in retrieved context is flagged as hallucination."""
        fake_answer = (
            "### 1. Clinical Guidance\n"
            "For this condition, the physician should prescribe Fakevir Rasayan 1-0-1 with warm water.\n"
            "### 2. Evidence from Retrieved Guidelines\n"
            "Citing retrieved guidelines.\n"
        )
        context = "Somtajvir 1-1-1 with warm water. Pranvir 2-2-2 with warm water."
        query = "What is the recommended treatment?"

        res = self.evaluator.evaluate_hallucination(fake_answer, context, query)
        self.assertTrue(res["hallucination_detected"], "Invented medicine Fakevir Rasayan should be flagged!")
        self.assertIn("Fakevir Rasayan", res["hallucinated_entities"])

    def test_real_hallucination_unsupported_dosage_detected(self):
        """Verifies that a fabricated dosage schedule for a valid medicine is flagged."""
        fabricated_dose_answer = (
            "### 1. Clinical Guidance\n"
            "| Medicine | Matra |\n"
            "| Somtajvir | 5-5-5 |\n"
        )
        # Context has Somtajvir with 1-1-1, NOT 5-5-5
        context = "Somtajvir 1-1-1 with honey/warm water."
        query = "What is the dose for Somtajvir?"

        res = self.evaluator.evaluate_hallucination(fabricated_dose_answer, context, query)
        self.assertTrue(res["hallucination_detected"], "Fabricated dose 5-5-5 should be flagged as unsupported detail!")
        self.assertTrue(any(u["prescribed_dose"] == "5-5-5" for u in res["unsupported_clinical_details"]))

    # ------------------------------------------------------------------
    # 5. Regression Tests for the 8 Audited Failures
    # ------------------------------------------------------------------

    def test_regression_tc04_age01(self):
        """TC-04-AGE-01: Table headers ignored and '3 to 15 years' matches '3-15 yrs'."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For prophylactic management in pediatric patients (3 to 15 years age group) without known comorbidities, the guideline recommends the following regimen:\n"
            "| Medicine | Matra (Dosage) | Sahpaan (Vehicle) | Aushadh Kal (Timing) |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **Pranvir** | 1-0-1 | Warm water | Vyanodaan kal (twice a day after food.) |\n"
            "| **Rasaka Rasayana** | 0-0-1 | Honey/ Warm Water | Nisha kal (at bedtime) |\n"
        )
        context = (
            "| Prophylactic Guidelines for General Patients without known co morbidities | 3-15 yrs | Pranvir | 1-0-1 | Warm water | Vyanodaan kal (twice a day after food.) |\n"
            "| Prophylactic Guidelines for General Patients without known co morbidities | 3-15 yrs | Rasaka Rasayana | 0-0-1 | Honey/ Warm Water | Nisha kal (at bedtime) |\n"
        )
        tc = {
            "expected_answer_elements": [
                "General patients without known comorbidities, age 3–15 years: Pranvir 1-0-1 with warm water, Vyanodaan kal twice a day after food.",
                "Rasaka Rasayana 0-0-1 with honey/warm water, Nisha kal at bedtime."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc04_age02(self):
        """TC-04-AGE-02: Table headers ignored and 'elderly / >60' matches 'More than 60 yrs'."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For elderly patients aged **more than 60 years** under the category of *\"Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities)\"*, the guidelines recommend the following prophylactic and Rasayana therapeutic regimen:\n"
            "| Medicine | Matra (Dose) | Sahpaan (Vehicle) | Aushadh Kal (Timing/Frequency) |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **Rasvir** | 1-0-0 | Honey / Warm Water | Rasayan kal (Early morning on empty stomach) |\n"
            "| **Pranvir** | 2-0-2 | Warm water | Vyanodaan kal (Twice a day after food) |\n"
            "| **Rasaka Rasayana** | 1-0-1 | Honey / Warm Water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |\n"
        )
        context = (
            "| Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities) | More than 60 yrs | Rasvir | 1-0-0 | Honey/ Warm Water | Rasayan kal (Early morning on empty stomach) |\n"
            "| Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities) | More than 60 yrs | Pranvir | 2-0-2 | Warm water | Vyanodaan kal (twice a day after food.) |\n"
            "| Prophylactic Guidelines for Patients with Pranvah Srotas Vyadhi (Respiratory Co-morbidities) | More than 60 yrs | Rasaka Rasayana | 1-0-1 | Honey/ Warm Water | Rasayan kal and Nisha kal (Early morning on empty stomach and at bedtime) |\n"
        )
        tc = {
            "expected_answer_elements": [
                "Age >60 years with Pranvah Srotas Vyadhi: Rasvir 1-0-0 with honey/warm water, Rasayan kal early morning empty stomach.",
                "Pranvir 2-0-2 with warm water, Vyanodaan kal twice a day after food.",
                "Rasaka Rasayana 1-0-1 with honey/warm water, Rasayan kal and Nisha kal."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc05_int02(self):
        """TC-05-INT-02: Scaffolding transition and table header ignored."""
        answer = (
            "### 1. Clinical Guidance\n"
            "#### A. Prevention of Rasa-raktagat saamata and raktagranthi (Thrombosis)\n"
            "To prevent Rasa-raktagat saamata and thrombosis in the post-viral phase, the patient should be prescribed:\n"
            "* **Medicines:** Pranvir and Rasak\n"
            "* **Duration:** Continue for 90 days\n"
            "#### B. Prevention of Upadrav (Other Infections e.g., Mucormycosis)\n"
            "Preventative nasal therapies (Nasya) are advised based on the patient's dominant dosha status:\n"
            "| Clinical Presentation / Condition | Treatment | Dosage | Timing / Aushadh Kal |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **If Vatadhikya** | Shamani Tail nasya | 2 Drops | Pratimarsha nasya kal |\n"
            "| **If Kaphadhikya / Pittadhikya** | Jyeshtha ghrita nasya | 3 Drops | Pratimarsha nasya kal |\n"
        )
        context = (
            "| Help to prevent Rasa-raktagat saamata and raktagranthi (Thrombosis) | Continue Pranvir and Rasak for 90 days |\n"
            "| Help to prevent Upadrav (other infections e.g mucormycosis) | If Vatadhikya | Shamani Tail nasya | 2 Drops | Pratimarsha nasya kal |\n"
            "| Help to prevent Upadrav (other infections e.g mucormycosis) | If Kaphadhik ya/ Pittadhikya | Jyeshtha ghrita nasya | 3 Drops | Pratimarsha nasya kal |\n"
        )
        tc = {
            "expected_answer_elements": [
                "To help prevent Rasa-raktagat saamata and raktagranthi (thrombosis): continue Pranvir and Rasak for 90 days.",
                "For other infections such as mucormycosis: Shamani Tail nasya 2 drops under Vatadhikya; Jyeshtha ghrita nasya 3 drops under Kaphadhikya/Pittadhikya, using Pratimarsha nasya kal."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc07_med01(self):
        """TC-07-MED-01: 'Asthma' matches 'Asthama' transliteration."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For a patient with a respiratory viral infection who has Asthma or COPD and is on regular inhalers, the prophylactic Rasayana guidelines provide the following recommendation:\n"
            "| Medicine | Matra | Sahpaan | Aushadh Kal |\n"
            "| Pranvallabh Rasayan | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |\n"
        )
        context = (
            "| Patients with Pranvah srotas Vyadhi (Asthama / COPD): |\n"
            "| If on regular inhalers | Pranvallabh Rasayan | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |\n"
        )
        tc = {
            "expected_answer_elements": [
                "Asthma/COPD on regular inhalers: Pranvallabh Rasayan 1-0-0 with honey/warm water, Rasayan kal early morning empty stomach."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc08_bnd01(self):
        """TC-08-BND-01: Inline citations stripped, 'more or equal to 24' matches '>=24'."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For a patient in the **MODERATE** state presenting with pneumonia, adolescent or adult status, clinical features of dyspnea and/or hypoxia, fever, cough, SpO2 < 94% (range 90–94%) on room air, and a respiratory rate >= 24 breaths per minute, the investigation protocol specifies the following criteria and required investigations:\n"
            "- **Criteria:** Pneumonia, adolescent or adult with presence of clinical features of dyspnea and/or hypoxia, fever, cough, SpO2 < 94% (range 90-94%) on room air, and respiratory rate more than or equal to 24 per min [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
            "- **Investigations:**\n"
            "  - CBC, RFT, LFT, RBS, ECG, ABG, ESR, CRP, S. FERRITIN, D-DIMER/LDH [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
            "  - If QTc prolongation is present in ECG, daily S. Electrolytes ionic Calcium and Magnesium [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
            "  - HRCT chest [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
            "  - Follow up CRP, D-dimer, and Sr. Ferritin every 48–72 hours (if available) [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
            "  - CBC with DLC, absolute lymphocyte count, KFT/LFT daily [DOC-FC76496810AB-0055-97B327D64EF1 | Page 24].\n"
        )
        context = (
            "| 2)MODERATE | Pneumonia, Adolescent or adult with presence of clinical features of Dyspnea and or Hypoxia, Fever, Cough, SpO2<94% (range 90-94%) on room air, Respiratory rate more or equal to 24 per min. | CBC, RFT, LFT, RBS, ECG, ABG, ESR, CRP, S. FERRITIN, D- DIMER/LDH …. * If QTc prolongation in ECG then daily S. Electrolytes ionic Calcium and Magnesium. *HRCT chest *Follow up CRP, D- dimer and Sr. Ferritin every 48-72 hrs. If available *CBC with DLC, absolute lymphocyte count KFT/LFT daily |\n"
        )
        tc = {
            "expected_answer_elements": [
                "Moderate criteria: pneumonia; adolescent/adult with dyspnea and/or hypoxia, fever, cough, SpO2 <94% (90–94% on room air), respiratory rate >=24/min.",
                "Investigations: CBC, RFT, LFT, RBS, ECG, ABG, ESR, CRP, serum ferritin, D-dimer/LDH; HRCT chest; follow-up CRP, D-dimer and serum ferritin every 48–72 hours if available; CBC with DLC/absolute lymphocyte count and KFT/LFT daily.",
                "If QTc prolongation on ECG: daily serum electrolytes, ionic calcium and magnesium."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc09_mis01(self):
        """TC-09-MIS-01: 'Investigations listed:' stripped, 'URINE -R' and 'SR. ELECTROLYTES' match."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For an Ayurvedic physician managing Prameh (Diabetes Mellitus), it is advisable to assess patients according to Ayurvedic criteria, and certain pathological investigations may be watched every 4 or 6 months or even at lesser intervals as the case may be [DOC-5FFD839CD910-0015-D2DE2A52FC13 | Page 8].\n"
            "The pathological investigations that patients generally bring and that may be used for follow-up as well are:\n"
            "- CBC, LFT, RFT, URINE -R, SR. ELECTROLYTES, SR. PHOSPHOROUS [DOC-5FFD839CD910-0016-BCE98ADED9D4 | Page 8]\n"
            "- BSL-F, PP, HbA1C, BSL-R, Lipid profile, Sr. insulin, C peptide [DOC-5FFD839CD910-0016-BCE98ADED9D4 | Page 8]\n"
        )
        context = (
            "For an ayurvedic physician, it is advisable to assess patients as per ayurvedic criteria and some pathological investigations may be watched for every 4 or 6 months or even at lesser interval as the case may be.\n"
            "CBC, LFT, RFT, URINE -R, SR. ELECRTROLYTES, SR. PHOSPHOROUS\n"
            "BSL-F, PP, HbA1C, BSL- R, Lipid profile, Sr.insulin, C peptide\n"
        )
        tc = {
            "expected_answer_elements": [
                "The guideline says some pathological investigations may be watched every 4 or 6 months or at a shorter interval as needed.",
                "Investigations listed: CBC, LFT, RFT, urine routine, serum electrolytes, serum phosphorus; BSL-F, PP, HbA1C, BSL-R, lipid profile, serum insulin and C-peptide."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc09_mis02(self):
        """TC-09-MIS-02: Regular use concept match succeeds."""
        answer = (
            "### 1. Clinical Guidance\n"
            "For people with no significant comorbidities during seasonal or epidemic viral infections, the following Nitya Rasayan Sevan prophylactic options are recommended:\n"
            "| Medicine | Matra | Sahpaan | Aushadh Kal |\n"
            "| **Pranvir** | 2-0-2 | Warm water | Vyanodaan kal (twice a day after food) |\n"
            "| **Rasaka Rasayana** | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |\n"
            "--- \n"
            "### 2. Evidence from Retrieved Guidelines\n"
            "- General Guidance: These Rasayana are safe for long-term consumption and can be administered for Nitya Sevan on a regular basis till the risk of infection is reduced significantly [DOC-FC76496810AB-0021-2F5EB5E3171A | Page 10].\n"
        )
        context = (
            "| People with no significant comorbidities: | Pranvir | 2-0-2 | Warm water | Vyanodaan kal (twice a day after food.) |\n"
            "| People with no significant comorbidities: | Rasaka Rasayana | 1-0-0 | Honey/warm water | Rasayan kal (Early morning on empty stomach) |\n"
            "It is advisable that these Rasayan should be taken on regular basis till the risk of infection is reduced significantly. All the below mentioned Rasayana are safe for long term consumption and can be administered for Nitya Sevan.\n"
        )
        tc = {
            "expected_answer_elements": [
                "People with no significant comorbidities: Pranvir 2-0-2 with warm water, Vyanodaan kal twice a day after food.",
                "Rasaka Rasayana 1-0-0 with honey/warm water, Rasayan kal early morning empty stomach.",
                "The guideline advises regular use until infection risk is significantly reduced."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    def test_regression_tc10_par02(self):
        """TC-10-PAR-02: Conversational intro ignored from claims and all 4 procedures grounded."""
        answer = (
            "### 1. Clinical Guidance\n"
            "During the active respiratory viral infection stage (sansarga), the following instructions and procedures are provided in the guidelines:\n"
            "* **Gargles:**\n"
            "  * With salt + haldi 3 times a day if Kapha doshaadhikya [DOC-FC76496810AB-0053-A4375A0D73E5 | Page 23].\n"
            "  * With yashtichurna + haldi if pittaadhikya [DOC-FC76496810AB-0053-A4375A0D73E5 | Page 23].\n"
            "* **Steam Inhalation:** With 1 or 2 drops of Eucalyptus oil in water 3 times a day [DOC-FC76496810AB-0053-A4375A0D73E5 | Page 23].\n"
            "* **Monitoring:** Monitor daily SpO2, PR, symptoms, appetite, bowel, urine and inform the treating physician [DOC-FC76496810AB-0053-A4375A0D73E5 | Page 23].\n"
            "* **Post-Infection Diet:** Avoid Viruddhashan, fish, and Adhyashan [DOC-FC76496810AB-0053-A4375A0D73E5 | Page 23].\n"
        )
        context = (
            "Gargles -with salt + haldi 3 times a day if Kapha doshaadhikya, with yashtichurna +haldi if pittaadhikya\n"
            "Steam with 1 or 2 drops of Eucalyptus oil in water 3 times a day\n"
            "Monitor daily SpO2, PR, symptoms, appetite, bowel, urine and inform to treating physician\n"
            "Post Respiratory Viral Infection diet-avoid Viruddhashan, fish, Adhyashan\n"
        )
        tc = {
            "expected_answer_elements": [
                "Gargles with salt + haldi three times a day if Kapha doshaadhikya; with yashtichurna + haldi if Pittadhikya.",
                "Steam with 1 or 2 drops of eucalyptus oil in water three times a day.",
                "Monitor daily SpO2, PR, symptoms, appetite, bowel and urine, and inform the treating physician.",
                "Post-respiratory-viral-infection diet: avoid Viruddhashan, fish and Adhyashan."
            ]
        }
        ground = self.evaluator.evaluate_groundedness(answer, context)
        comp = self.evaluator.evaluate_completeness(tc, answer)
        self.assertGreaterEqual(ground["groundedness_score"], 0.75, f"Groundedness score {ground['groundedness_score']} must be >= 0.75")
        self.assertGreaterEqual(comp["score"], 0.70, f"Completeness score {comp['score']} must be >= 0.70")

    # ------------------------------------------------------------------
    # 6. Negative Tests: Genuinely Unsupported Clinical Claims Detected
    # ------------------------------------------------------------------

    def test_negative_genuinely_unsupported_claim_detected(self):
        """Verifies that an answer containing a genuinely unsupported clinical prescription fails groundedness."""
        unsupported_answer = (
            "### 1. Clinical Guidance\n"
            "| Medicine | Matra | Sahpaan | Aushadh Kal |\n"
            "| **Ashwagandha Ghrita** | 20ml | Cow milk | Twice a day after food |\n"
            "| **Dexamethasone** | 8mg | Water | Morning |\n"
        )
        # Context has only Pranvir and Rasaka Rasayana
        context = (
            "| Prophylactic Guidelines | 3-15 yrs | Pranvir | 1-0-1 | Warm water | Vyanodaan kal |\n"
            "| Prophylactic Guidelines | 3-15 yrs | Rasaka Rasayana | 0-0-1 | Honey/ Warm Water | Nisha kal |\n"
        )
        ground = self.evaluator.evaluate_groundedness(unsupported_answer, context)
        self.assertLess(ground["groundedness_score"], 0.75, "Unsupported medicines must cause groundedness score < 0.75!")
        self.assertGreater(len(ground["ungrounded_claims"]), 0, "Ungrounded claims list must not be empty!")


if __name__ == "__main__":
    unittest.main()

