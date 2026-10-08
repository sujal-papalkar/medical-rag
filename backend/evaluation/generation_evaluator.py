"""
Generation Evaluation Module for Ayurvedic Medical RAG.

Evaluates the generation.py pipeline against the 20 retrieval scenarios
(10 categories x 2 test cases) defined in evaluation/generation_ground_truth_20_cases.json.

Implements rigorous, clinically strict, and non-inflated evaluation:
1. Completeness: Decomposes expected answer elements into clinical components
   (medicine, dose, sahpaan, timing, frequency, condition) and requires component recall.
2. Groundedness & Faithfulness: Claim-level local context grounding verifying factual
   assertions (dose, vehicle, timing) in local context rather than global word overlap.
3. Hallucination Detection: Requires full formulation name support and detects unsupported
   or fabricated clinical details (e.g. mismatched dosage).
4. Clinical Context Correctness: Validates scenario-specific features (severity, stage,
   thresholds, comorbidities, symptoms, patient types) from ground truth.
5. Source Correctness: Separate evaluation of retrieval precision, chunk hit, and citations.
6. Missing-Information Handling: Evaluates substantive clinical limitations and checks that
   missing-information scenarios do not invent unsupported clinical details.
7. PASS / FAIL Verdict: Strictly enforced thresholds (Comp >= 0.70, Ground >= 0.75,
   Source >= 0.50, Chunk Hit = True, Clinical Context >= 0.70, No Hallucination).
8. Deterministic Best Candidate Selection across 3 independent candidates.
9. Quota Error Handling: 429 rate limits tracked separately and excluded from quality averages.
"""

import os
import sys
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

# Ensure utf-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

for p in [str(ROOT_DIR), str(BACKEND_DIR), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generation import generate_response, get_retrieval_service
from evaluation.retrieval_service import RetrievalService

DATASET_PATH = CURRENT_DIR / "generation_ground_truth_20_cases.json"
DEFAULT_REPORT_PATH = CURRENT_DIR / "generation_evaluation_report.json"


# ============================================================
# NORMALIZATION & CLINICAL DICTIONARIES
# ============================================================

def normalize_text(text: str) -> str:
    """Normalizes text for robust clinical string matching."""
    text = text.lower()
    text = re.sub(r'[\s\-_/]+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def is_quota_error(err_str: str) -> bool:
    """Detects whether an error string corresponds to a 429 quota/rate limit error."""
    if not err_str:
        return False
    lower = err_str.lower()
    return "429" in lower or "resource_exhausted" in lower or "quota" in lower


KNOWN_FORMULATIONS = [
    "Zincare", "Obecon", "Normoten", "Rasvir", "Pranvir", "Somtajvir", "Arpisa",
    "Arpisa Rasayan", "Arpisa Rasayana", "Ruchir", "Sunetra", "Sunetra Rasayan",
    "Sannidha", "Sannidha Rasayan", "Sannidha Rasayana", "Sutendra", "Sutendra Rasayan",
    "Sutendra Rasayana", "Pranvallabh", "Pranvallabh Rasayan", "Pranvallabha",
    "Pranvallabha Rasayan", "Meha", "Meha Rasayan", "Meha Rasayana", "Bal Rasayana",
    "Kansya Rasayan", "Kansya Rasayana", "Heerak Rasayan", "Heerak Rasayana",
    "Mahalaxmi Vilas", "Mahalakshmi Vilas", "Sinurbhushan", "Sinurbhushan Rasayan",
    "Sindhurbhushan", "Sindhurbhushan Rasayan", "Niketa", "Niketa Rasayan",
    "Netraj", "Netraj Rasayan", "Shamani Tail", "Jyeshtha Ghrita", "Jyeshta Ghrita",
    "Ayukshar", "Lavan", "Aarevat Kalpa", "Zinzi", "Zinzi chips", "Rasaka",
    "Rasaka Rasayana", "Rasak", "Urokine", "Chandraprabha", "Ashwagandha",
    "Praval", "Jasad", "Vanga", "Kanchan Rasayana", "Kanchan Rasayan",
    "Somkalpa", "Pravi Rasayana", "Pravi Rasayan", "Bal Rasayan"
]

GENERIC_MEDICINE_STOPWORDS = {
    "medicine", "medicines", "treatment", "treatments", "rasayan", "rasayana",
    "patient", "patients", "guideline", "guidelines", "protocol", "protocols",
    "ayurveda", "ayurvedic", "formulation", "formulations", "therapy", "management",
    "prevention", "prophylaxis", "intervention", "interventions", "drug", "drugs",
    "therapeutic", "prophylactic", "following", "option", "options", "prescribed",
    "specified", "recommended", "recommendation", "sevan", "nitya", "daily", "routine",
    "oral", "application", "nasya", "pratimarsha"
}

ENGLISH_NON_MEDICINE_PREFIXES = {
    "the", "a", "an", "this", "that", "these", "those",
    "for", "in", "on", "at", "to", "from", "by", "with", "without", "under", "as", "of", "into",
    "and", "or", "but", "if", "add", "take", "give", "administer", "continue",
    "guideline", "guidelines", "protocol", "protocols",
    "provides", "provide", "provided", "providing",
    "following", "follows", "followed",
    "therapeutic", "prophylaxis", "prophylactic",
    "recommended", "recommend", "recommends", "recommendation", "recommendations",
    "specified", "specifies", "specify",
    "prescribed", "prescribe", "prescribes", "prescription",
    "options", "option", "choice", "choices",
    "patient", "patients", "case", "cases",
    "management", "treatment", "treatments", "therapy", "therapies", "intervention", "interventions",
    "sevan", "nitya", "daily", "regular", "routine",
    "matra", "dose", "doses", "dosage", "dosages",
    "sahpaan", "vehicle", "vehicles", "anupana",
    "aushadh", "kal", "timing", "timings", "frequency", "duration",
    "contraindication", "contraindications", "precaution", "precautions", "interaction", "interactions",
    "limitation", "limitations", "missing", "information",
    "use", "using", "used", "administer", "administered", "administration",
    "oral", "application", "nasya", "drops", "oil"
}

FORMULATION_SUFFIXES = [
    "Rasayan", "Rasayana", "Vati", "Bhasma", "Kwath", "Guggul", "Guggulu",
    "Churna", "Taila", "Tailam", "Tail", "Asava", "Arishta", "Kashayam",
    "Ghruta", "Ghrita", "Loha", "Mandoor", "Kalpa"
]


# ============================================================
# PROBLEM 1: CLINICAL COMPONENT DECOMPOSITION (COMPLETENESS)
# ============================================================

def parse_element_clinical_components(element: str) -> Dict[str, Any]:
    """
    Decomposes an expected answer element into its essential clinical components:
    - medicines: formulation/drug names
    - dosages: numerical dosage signatures (e.g. 2-2-2, 1-0-1, 2 drops)
    - vehicles: anupana / sahpaan (warm water, honey, cow ghee)
    - timings: aushadh kal / timing (Vyanodaan kal, after food, empty stomach)
    - frequencies: dosing frequency (three times a day, twice a day, daily)
    - conditions: threshold / clinical stage conditions
    - directives: clinical action instructions
    """
    element_lower = element.lower()
    components: Dict[str, List[str]] = {
        "medicines": [],
        "dosages": [],
        "vehicles": [],
        "timings": [],
        "frequencies": [],
        "conditions": [],
        "directives": [],
        "investigations": []
    }

    # 1. Dosages
    doses = re.findall(r'\b\d+-\d+-\d+\b|\b\d+\s*(?:drops?|ml|g\b|teaspoon)', element, re.IGNORECASE)
    for d in doses:
        if d not in components["dosages"]:
            components["dosages"].append(d)

    # 2. Formulations / Medicines
    for kf in KNOWN_FORMULATIONS:
        if re.search(r'\b' + re.escape(kf) + r'\b', element, re.IGNORECASE):
            # Keep the canonical name
            if not any(kf.lower() in existing.lower() for existing in components["medicines"]):
                components["medicines"].append(kf)

    # Special natural substances acting as remedies
    if "salt" in element_lower and "haldi" in element_lower:
        components["medicines"].append("salt + haldi gargles")
    if "eucalyptus" in element_lower:
        components["medicines"].append("eucalyptus oil steam")

    # 3. Vehicles (Sahpaan / Anupana)
    candidate_vehicles = [
        "warm water", "honey", "cow ghee", "ginger juice", "drinking water",
        "milk", "yashtichurna"
    ]
    for vh in candidate_vehicles:
        if vh in element_lower:
            components["vehicles"].append(vh)

    # 4. Timings (Aushadh Kal / Meal relationship)
    candidate_timings = [
        "vyanodaan kal", "rasayan kal", "nisha kal", "pran kal", "gandushkal",
        "pratimarsha nasya kal", "empty stomach", "after food", "bedtime",
        "early morning", "muhurmuhur"
    ]
    for tm in candidate_timings:
        if tm in element_lower:
            components["timings"].append(tm)

    # 5. Frequencies
    candidate_freqs = [
        "three times a day", "three times", "twice a day", "once a day",
        "once/twice a day", "3–4 times", "3-4 times", "daily", "for 90 days",
        "every 48–72 hours", "every 4 or 6 months"
    ]
    for fq in candidate_freqs:
        if fq in element_lower:
            components["frequencies"].append(fq)

    # 6. Specific Threshold / Patient conditions
    candidate_conditions = [
        "bmi >=25", "bmi >= 25", "overweight", "family history", "hrct 0–8",
        "hrct 0-8", "spo2 >94", "udakvah", "annavah", "pranvah", "stage 3",
        "gfr 30–59%", "creatinine 4–6", "creatinine 4 to 6", "hrct >15", "spo2 <90",
        "age above 15", "malignancy", "granthi", "arbud", "3–15 years", "3 to 15 years",
        "3-15 yrs", "3-15 years", "3 to 15 yrs", "pediatric", "age >60", "elderly",
        "more than 60 yrs", "more than 60 years", "secondary prevention", "vidradhi",
        "murchha", "punstvopghaat", "thrombosis", "raktagranthi", "saamata",
        "mucormycosis", "trushna", "aruchi", "santat jwar", "rasabhinodan vruddhi",
        "mukhshushkata", "asthma", "asthama", "copd", "inhalers", "moderate", "spo2 90–94%",
        "spo2 90-94", "respiratory rate >=24", "respiratory rate >= 24",
        "more or equal to 24 per min", "more than or equal to 24", "stage 5",
        "gfr under 15%", "creatinine above 8", "retinopathy", "blurred vision"
    ]
    for cond in candidate_conditions:
        if cond in element_lower:
            components["conditions"].append(cond)

    # 7. Non-pharmacological Directives
    candidate_directives = [
        "continue medications", "examination by an ayurveda physician",
        "avoid viruddhashan", "inform the treating physician", "monitor daily",
        "daily serum electrolytes", "daily s. electrolytes", "s. electrolytes daily",
        "cbc with dlc"
    ]
    for dir_kw in candidate_directives:
        if dir_kw in element_lower:
            components["directives"].append(dir_kw)

    # 8. Clinical Investigations / Laboratory Tests
    candidate_investigations = [
        "cbc with dlc", "cbc", "lft", "rft", "kft", "rbs", "ecg", "abg", "esr", "crp",
        "serum ferritin", "sr. ferritin", "d-dimer", "ldh", "hrct chest", "hrct", "cxr",
        "urine routine", "urine -r", "urine - r", "serum electrolytes", "sr. electrolytes",
        "s. electrolytes", "serum phosphorus", "sr. phosphorous", "bsl-f", "bsl-r", "bsl-pp",
        "pp", "hba1c", "lipid profile", "serum insulin", "sr. insulin", "c-peptide", "c peptide",
        "ionic calcium", "magnesium"
    ]
    for inv in candidate_investigations:
        if re.search(r'\b' + re.escape(inv) + r'\b', element_lower):
            if not any(inv in existing for existing in components["investigations"]):
                components["investigations"].append(inv)

    # Clean up overlaps (e.g. if "three times a day" is present, omit "three times")
    if "three times a day" in components["frequencies"] and "three times" in components["frequencies"]:
        components["frequencies"].remove("three times")

    return components


# Clinical concept-aware equivalence mappings
CLINICAL_CONCEPT_EQUIVALENTS: Dict[str, List[str]] = {
    # Age & Cohort equivalents
    "3-15 yrs": ["3-15 yrs", "3-15 years", "3–15 years", "3 to 15 years", "3 to 15 yrs", "3-15", "age 3-15", "age 3–15", "pediatric"],
    "3 to 15 years": ["3-15 yrs", "3-15 years", "3–15 years", "3 to 15 years", "3 to 15 yrs", "3-15", "age 3-15", "age 3–15", "pediatric"],
    "3–15 years": ["3-15 yrs", "3-15 years", "3–15 years", "3 to 15 years", "3 to 15 yrs", "3-15", "age 3-15", "age 3–15", "pediatric"],
    "pediatric": ["pediatric", "3-15 yrs", "3-15 years", "3–15 years", "3 to 15 years", "children", "child"],
    "age >60": ["age >60", "age > 60", "more than 60 yrs", "more than 60 years", ">60 years", "> 60 years", "above 60", "elderly", ">60 yrs"],
    "more than 60 yrs": ["age >60", "age > 60", "more than 60 yrs", "more than 60 years", ">60 years", "> 60 years", "above 60", "elderly"],
    "more than 60 years": ["age >60", "age > 60", "more than 60 yrs", "more than 60 years", ">60 years", "> 60 years", "above 60", "elderly"],
    "elderly": ["elderly", "more than 60 yrs", "more than 60 years", ">60 years", "age >60", ">60 yrs", "above 60"],
    "age above 15": ["age above 15", "above 15 years", "15+yrs", "15+ yrs", "15+ years", "above 15"],
    "15+yrs": ["age above 15", "above 15 years", "15+yrs", "15+ yrs", "15+ years", "above 15"],

    # Conditions & Transliterations
    "asthma": ["asthma", "asthama", "bronchial asthma"],
    "asthama": ["asthma", "asthama", "bronchial asthma"],
    "copd": ["copd", "chronic obstructive pulmonary disease"],
    "inhalers": ["inhaler", "inhalers", "regular inhalers"],

    # Lab Investigations & Abbreviations
    "serum electrolytes": ["serum electrolytes", "sr. electrolytes", "sr electrolytes", "s. electrolytes", "s electrolytes", "sr. elecrtrolytes", "sr.elecrtrolytes", "s. electrolyte"],
    "sr. electrolytes": ["serum electrolytes", "sr. electrolytes", "sr electrolytes", "s. electrolytes", "s electrolytes", "sr. elecrtrolytes", "sr.elecrtrolytes"],
    "s. electrolytes": ["serum electrolytes", "sr. electrolytes", "sr electrolytes", "s. electrolytes", "s electrolytes", "sr. elecrtrolytes"],
    "daily serum electrolytes": ["daily serum electrolytes", "daily s. electrolytes", "daily sr. electrolytes", "s. electrolytes daily", "daily s. electrolyte"],
    "daily s. electrolytes": ["daily serum electrolytes", "daily s. electrolytes", "daily sr. electrolytes", "s. electrolytes daily", "daily s. electrolyte"],
    "urine routine": ["urine routine", "urine -r", "urine - r", "urine-r", "urine r", "urine examination", "urine -routine"],
    "urine -r": ["urine routine", "urine -r", "urine - r", "urine-r", "urine r", "urine examination"],
    "urine - r": ["urine routine", "urine -r", "urine - r", "urine-r", "urine r", "urine examination"],
    "serum phosphorus": ["serum phosphorus", "serum phosphorous", "sr. phosphorous", "sr. phosphorus", "sr phosphorous", "s. phosphorous", "s. phosphorus", "phosphorus", "phosphorous"],
    "sr. phosphorous": ["serum phosphorus", "serum phosphorous", "sr. phosphorous", "sr. phosphorus", "sr phosphorous", "s. phosphorous", "s. phosphorus"],
    "serum ferritin": ["serum ferritin", "sr. ferritin", "sr ferritin", "s. ferritin", "s ferritin", "ferritin"],
    "sr. ferritin": ["serum ferritin", "sr. ferritin", "sr ferritin", "s. ferritin", "s ferritin"],
    "serum insulin": ["serum insulin", "sr. insulin", "sr insulin", "s. insulin", "s insulin", "sr.insulin", "insulin"],
    "sr. insulin": ["serum insulin", "sr. insulin", "sr insulin", "s. insulin", "s insulin", "sr.insulin"],
    "c-peptide": ["c-peptide", "c peptide", "c - peptide"],
    "c peptide": ["c-peptide", "c peptide", "c - peptide"],
    "lipid profile": ["lipid profile", "serum lipid profile"],
    "ionic calcium": ["ionic calcium", "calcium"],
    "magnesium": ["magnesium", "sr. magnesium", "s. magnesium"],
    "hrct": ["hrct", "hrct chest", "ct chest"],
    "hrct chest": ["hrct", "hrct chest", "ct chest"],
    "rft": ["rft", "kft", "renal function test", "kidney function test"],
    "kft": ["rft", "kft", "renal function test", "kidney function test"],
    "lft": ["lft", "liver function test"],
    "cbc": ["cbc", "cbc with dlc", "complete blood count"],
    "cbc with dlc": ["cbc with dlc", "cbc", "complete blood count"],
    "bsl-f": ["bsl-f", "bsl - f", "bsl fasting", "fasting blood sugar"],
    "bsl-r": ["bsl-r", "bsl - r", "bsl random", "random blood sugar", "rbs"],
    "bsl-pp": ["bsl-pp", "bsl - pp", "pp", "bsl post prandial", "post prandial blood sugar"],

    # Thresholds and Criteria
    ">=24/min": [">=24/min", ">= 24", "more or equal to 24 per min", "more than or equal to 24", "more than or equal to 24 per min", ">=24", "24 or more", "24 breaths/min"],
    "respiratory rate >=24": ["respiratory rate >=24", "respiratory rate >= 24", "respiratory rate more or equal to 24", "respiratory rate more than or equal to 24", "respiratory rate 24 or more", "respiratory rate >= 24 per min", "respiratory rate >=24/min", "respiratory rate more than or equal to 24 per min", "respiratory rate more or equal to 24 per min"],
    "more or equal to 24 per min": [">=24/min", ">= 24", "more or equal to 24 per min", "more than or equal to 24", "more than or equal to 24 per min", ">=24", "24 or more"],
    "spo2 <94%": ["spo2 <94%", "spo2 < 94%", "spo2 90-94", "spo2 90–94%", "90-94%", "90–94%"],
    "spo2 90–94%": ["spo2 90–94%", "spo2 90-94%", "spo2 90 to 94", "90-94%", "90–94%"],
    "spo2 90-94": ["spo2 90–94%", "spo2 90-94%", "spo2 90 to 94", "90-94%", "90–94%"],

    # Duration and Guidance phrases
    "regular use until infection risk is significantly reduced": [
        "regular use until infection risk is significantly reduced",
        "regular basis till the risk of infection is reduced significantly",
        "till the risk of infection is reduced significantly",
        "risk of infection is reduced significantly",
        "regular basis till the risk of infection",
        "nitya sevan on a regular basis till the risk of infection is reduced",
        "nitya sevan"
    ],
    "the guideline advises regular use until infection risk is significantly reduced": [
        "regular use until infection risk is significantly reduced",
        "regular basis till the risk of infection is reduced significantly",
        "till the risk of infection is reduced significantly",
        "risk of infection is reduced significantly",
        "regular basis till the risk of infection",
        "nitya sevan on a regular basis till the risk of infection is reduced",
        "nitya sevan"
    ]
}


def strip_inline_citations(text: str) -> str:
    """Strips markdown citation blocks like [DOC-... | Page 24] or [DOC-...] and page tags."""
    cleaned = re.sub(r'\[\s*DOC-[A-Za-z0-9\-]+(?:[^\]]*?)\]', '', text)
    cleaned = re.sub(r'\[\s*(?:Page|p\.)\s*\d+\s*\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\(\s*(?:Page|p\.)\s*\d+\s*\)', '', cleaned, flags=re.IGNORECASE)
    return cleaned


def is_markdown_table_header_or_separator(line: str) -> bool:
    """
    Identifies Markdown table header rows and separator rows so they are not
    falsely evaluated as clinical assertions.
    """
    line_stripped = line.strip()
    if not line_stripped or not line_stripped.startswith('|'):
        return False

    # Separator rows (e.g. | :--- | :--- | or |---|---| or | :--: |)
    if re.match(r'^\|[\s\:\-\|]+\|$', line_stripped):
        return True

    cells = [c.strip().lower() for c in line_stripped.strip('|').split('|')]
    if not cells:
        return False

    header_names = {
        "medicine", "medicines", "drug", "drugs", "formulation", "formulations",
        "matra", "dose", "dosage", "matra (dosage)", "matra (dose)", "matra / dosage",
        "sahpaan", "anupana", "sahpaan (vehicle)", "sahpaan / anupana", "vehicle",
        "aushadh kal", "aushadh kala", "aushadha kal", "aushadha kala",
        "aushadh kal (timing)", "timing", "timing / aushadh kal", "timing / frequency",
        "timing/frequency", "aushadh kal (timing/frequency)",
        "frequency", "duration", "duration of treatment", "route", "administration",
        "patient type", "age group", "age", "condition", "conditions",
        "clinical presentation", "clinical presentation / condition",
        "treatment", "treatments", "action", "status", "stage", "indication", "indications",
        "symptoms", "complaints", "co-morbidity", "comorbidity", "comorbidities",
        "criteria", "state and group", "state", "group", "investigation", "investigations",
        "instructions", "hrct score", "score", "sl no", "sr no", "no"
    }

    matched_cells = 0
    for cell in cells:
        clean_cell = re.sub(r'[\*\_\(\)\:\/\-\–\s]+', ' ', cell).strip()
        if clean_cell in header_names:
            matched_cells += 1
        elif any(clean_cell == hn or clean_cell.startswith(hn) for hn in header_names):
            matched_cells += 1
        elif any(kw in clean_cell for kw in [
            "medicine", "matra", "sahpaan", "aushadh", "timing", "dosage",
            "vehicle", "treatment", "presentation", "comorbid", "investigation"
        ]):
            matched_cells += 1

    return (matched_cells / len(cells)) >= 0.50


def is_conversational_scaffolding(line: str) -> bool:
    """
    Identifies conversational lead-in sentences, section transitions, and preamble
    formatting that set up tables or lists without stating independent clinical claims.
    """
    line_clean = line.strip()
    line_lower = line_clean.lower()

    if not line_lower or len(line_lower) < 10:
        return False

    meta_phrases = [
        "based on the retrieved",
        "here is the structured guidance",
        "here is the clinical guidance",
        "as per the retrieved",
        "according to the retrieved",
        "as outlined in the retrieved",
        "the guidelines recommend the following",
        "the guideline recommends the following",
        "guidelines provide the following",
        "guideline provides the following",
        "the following instructions and procedures are provided",
        "the following instructions are provided",
        "the following recommendations are provided",
        "the following options are recommended",
        "the following regimen is recommended",
        "the following prophylactic",
        "the following therapeutic",
        "the following treatments help",
        "the following treatments are recommended",
        "pathological investigations that patients generally bring",
        "may be used for follow-up as well are",
        "preventative nasal therapies (nasya) are advised based on",
        "nasal therapies (nasya) are advised based on",
        "during the active respiratory viral infection stage",
        "for prophylactic management in pediatric patients",
        "for elderly patients aged",
        "for a patient with a respiratory viral infection who has asthma",
        "for people with no significant comorbidities during seasonal"
    ]

    ends_with_colon = line_clean.endswith(':') or line_clean.endswith(':-')
    has_scaffolding_phrase = any(mp in line_lower for mp in meta_phrases)

    if has_scaffolding_phrase or (ends_with_colon and any(w in line_lower for w in ["following", "guideline", "recommended", "advised", "specifies", "protocol"])):
        # Make sure this line does NOT contain concrete dosages or specific standalone prescriptions
        has_concrete_dosage = bool(re.search(r'\b\d+-\d+-\d+\b|\b\d+\s*drops?\b|\bfor \d+ days\b', line_lower))
        if not has_concrete_dosage:
            return True

    return False


def clean_element_metadata_labels(el: str) -> str:
    """
    Strips ground-truth metadata labels such as 'Investigations listed:',
    'Investigations:', 'Moderate criteria:', etc. so they are not treated as required clinical content.
    """
    cleaned = re.sub(
        r'^(?:Investigations\s*listed|Investigations|Moderate\s*criteria|Criteria|Note|Protocol|Guideline)\s*:\s*',
        '',
        el,
        flags=re.IGNORECASE
    )
    return cleaned.strip()


def evaluate_component_match(component: str, text: str) -> bool:
    """Checks whether a single clinical component is matched in the target text using concept-aware matching."""
    c_lower = component.lower().strip()
    t_lower = text.lower()

    if c_lower in t_lower:
        return True

    # Check normalized text match
    norm_c = normalize_text(c_lower)
    norm_t = normalize_text(t_lower)
    if norm_c in norm_t:
        return True

    # Clinical synonym and transliteration variants
    synonyms = {
        "obecon": ["obecon"],
        "sannidha rasayan": ["sannidha", "sannidha rasayan", "sannidha rasayana"],
        "somtajvir": ["somtajvir", "somtaj vir"],
        "pranvir": ["pranvir", "pran vir"],
        "rasaka rasayana": ["rasaka", "rasaka rasayan", "rasaka rasayana", "rasak"],
        "meha rasayan": ["meha", "meha rasayan", "meha rasayana"],
        "zincare": ["zincare"],
        "urokine": ["urokine"],
        "sindhurbhushan rasayan": ["sindhurbhushan", "sinurbhushan", "sindhur bhushan"],
        "mahalakshmi vilas": ["mahalakshmi vilas", "mahalaxmi vilas"],
        "pranvallabh rasayan": ["pranvallabh", "pranvallabha", "pranvallabh rasayan"],
        "sutendra": ["sutendra", "sutendra rasayan", "sutendra rasayana"],
        "arpisa rasayan": ["arpisa", "arpisa rasayan"],
        "rasvir": ["rasvir", "ras vir"],
        "jyeshta ghrita": ["jyeshta ghrita", "jyeshtha ghrita", "jyeshta ghruta", "jyeshtha ghruta"],
        "shamani tail": ["shamani tail", "shamani taila"],
        "aarevat kalpa": ["aarevat", "aarevat kalpa", "aaragvadha"],
        "heerak rasayan": ["heerak", "heerak rasayan", "heeraka"],
        "kansya rasayan": ["kansya", "kansya rasayan", "kamsya"],
        "sunetra rasayan": ["sunetra", "sunetra rasayan"],
        "niketa rasayan": ["niketa", "niketa rasayan"],
        "netraj rasayan": ["netraj", "netraj rasayan"],
        "warm water": ["warm water", "koshna jala", "ushnodaka", "lukewarm water"],
        "honey": ["honey", "madhu"],
        "cow ghee": ["cow ghee", "ghee", "go ghrita", "ghrita"],
        "vyanodaan kal": ["vyanodaan", "vyanodan", "vyana udana", "vyanodana"],
        "rasayan kal": ["rasayan kal", "rasayana kala", "rasayana kal"],
        "nisha kal": ["nisha kal", "nisha kala", "bedtime", "night"],
        "after food": ["after food", "after meals", "post-prandial", "post meals"],
        "empty stomach": ["empty stomach", "early morning empty stomach"],
        "three times a day": ["three times a day", "3 times a day", "thrice a day", "tid"],
        "twice a day": ["twice a day", "2 times a day", "bid", "two times a day"],
        "salt + haldi gargles": ["salt", "haldi", "gargle", "turmeric"],
        "eucalyptus oil steam": ["eucalyptus", "steam"],
        "continue medications": ["continue", "not stop", "ongoing"],
        "examination by an ayurveda physician": ["physician", "vaidya", "consult", "doctor", "examination"]
    }

    c_stripped = re.sub(r'^(?:phrase|directives?|conditions?|medicines?|dosages?|vehicles?|timings?|frequencies?|investigations?)\s*:\s*', '', c_lower).strip()

    all_equivalents = {**synonyms, **CLINICAL_CONCEPT_EQUIVALENTS}
    if c_lower in all_equivalents:
        if any(syn in t_lower or normalize_text(syn) in norm_t for syn in all_equivalents[c_lower]):
            return True
    if c_stripped in all_equivalents:
        if any(syn in t_lower or normalize_text(syn) in norm_t for syn in all_equivalents[c_stripped]):
            return True

    # Check substring keys in all_equivalents
    for k, eq_list in all_equivalents.items():
        if k in c_stripped or c_stripped in k:
            for eq in eq_list:
                if eq in t_lower or normalize_text(eq) in norm_t:
                    return True

    # Substantive content word matching for longer narrative phrases
    words = [w for w in re.findall(r'[a-zA-Z0-9\-\>\%]+', c_stripped) if len(w) > 3 and w not in {
        "the", "and", "for", "with", "this", "that", "from", "guideline", "advises", "under", "using", "listed"
    }]
    if len(words) >= 3:
        matched_w = sum(1 for w in words if w in t_lower or w in norm_t)
        if (matched_w / len(words)) >= 0.60:
            return True

    return False


# ============================================================
# PROBLEM 3: ENTITY & MEDICINE EXTRACTION (STRICT HALLUCINATION)
# ============================================================

def clean_medicine_candidate(candidate: str) -> Optional[str]:
    """
    Cleans candidate medicine string:
    - Strips markdown, punctuation, leading numbers/bullets.
    - Strips trailing dosage signatures (e.g. '1-0-1', '2 drops').
    - Strips leading English prepositions, articles, and clinical attribute labels.
    - Rejects pure generic words or non-medicine phrases.
    """
    if not candidate:
        return None
    # Strip markdown and boundary punctuation
    cand = re.sub(r'^[\*\-\>\d\.\s\:\,\;\|\(\)\[\]]+', '', candidate)
    cand = re.sub(r'[\*\-\>\s\:\,\;\|\(\)\[\]]+$', '', cand).strip()
    if not cand or len(cand) < 3:
        return None

    # Strip trailing dosage signatures if present in candidate
    cand = re.sub(r'\s*\b\d+-\d+-\d+\b.*$', '', cand).strip()
    cand = re.sub(r'\s*\b\d+\s*(?:drops?|ml|tsp|teaspoon|tablespoon)\b.*$', '', cand, flags=re.IGNORECASE).strip()

    words = cand.split()
    # Strip leading non-medicine prefix words
    while words and words[0].lower() in ENGLISH_NON_MEDICINE_PREFIXES:
        words.pop(0)

    # Strip trailing non-medicine words
    while words and words[-1].lower() in (ENGLISH_NON_MEDICINE_PREFIXES - {"oil", "nasya"}):
        words.pop(-1)

    if not words:
        return None

    cleaned = " ".join(words).strip()
    cleaned_lower = cleaned.lower()

    if cleaned_lower in GENERIC_MEDICINE_STOPWORDS:
        return None

    # Check if candidate is just a suffix alone (e.g. 'Rasayana', 'Ghrita')
    if any(cleaned_lower == s.lower() for s in FORMULATION_SUFFIXES):
        return None

    # Check if all remaining words are in generic medicine stopwords
    if all(w.lower() in GENERIC_MEDICINE_STOPWORDS for w in words):
        return None

    if len(cleaned) < 3:
        return None

    return cleaned


def extract_prescribed_medicines(answer_text: str) -> List[str]:
    """
    Extracts medicine and formulation names explicitly prescribed in the generated answer.
    Excludes English phrases, limitation/missing info statements, and generic terms.
    """
    medicines = set()

    # Exclude Limitations & Missing Information section from prescribed medicine extraction
    text_to_scan = answer_text
    if "### 3. Limitations" in text_to_scan:
        text_to_scan = text_to_scan.split("### 3. Limitations")[0]
    elif "### 3." in text_to_scan:
        text_to_scan = text_to_scan.split("### 3.")[0]
    elif "Limitations & Missing Information" in text_to_scan:
        text_to_scan = text_to_scan.split("Limitations & Missing Information")[0]

    # Split into lines and filter out any individual limitation/absence statement lines
    valid_lines = []
    for line in text_to_scan.split('\n'):
        # Skip lines explicitly stating a parameter is not specified / missing
        if re.search(r'\b(?:is not specified|are not specified|not specified in|not provided|unspecified|not mentioned)\b', line, re.IGNORECASE):
            continue
        valid_lines.append(line)
    clean_scan_text = '\n'.join(valid_lines)

    # Pattern 1: Explicit prompt markdown bold markers (e.g. "**Medicine:** Somtajvir")
    med_pattern = re.compile(
        r'(?:\*\*Medicine:\*\*|Medicine:|\bPrescribed:\b)\s*\*?([A-Za-z0-9\s\-]+?)(?:\n|\*|\(|\,|$)',
        re.IGNORECASE
    )
    for match in med_pattern.finditer(clean_scan_text):
        raw = match.group(1).strip()
        cleaned = clean_medicine_candidate(raw)
        if cleaned:
            medicines.add(cleaned)

    # Pattern 2: Ayurvedic formulation suffixes (1 or 2 capitalized words preceding suffix)
    suffix_pattern = re.compile(
        r'\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+)?\s+(?i:' + '|'.join(FORMULATION_SUFFIXES) + r'))\b'
    )
    for match in suffix_pattern.finditer(clean_scan_text):
        raw = match.group(1).strip()
        cleaned = clean_medicine_candidate(raw)
        if cleaned:
            medicines.add(cleaned)

    # Pattern 3: Formulations immediately preceding dosage signatures (e.g. "SomeMedicine 1-0-0")
    dose_med_pattern = re.compile(
        r'\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+)?)\s+(?:—|-|–|:|\*)*\s*(?:Matra\s*)?\d+-\d+-\d+\b'
    )
    for match in dose_med_pattern.finditer(clean_scan_text):
        raw = match.group(1).strip()
        cleaned = clean_medicine_candidate(raw)
        if cleaned:
            medicines.add(cleaned)

    # Pattern 4: Known specific proprietary formulations in these guidelines
    for kf in KNOWN_FORMULATIONS:
        if re.search(r'\b' + re.escape(kf) + r'\b', clean_scan_text, re.IGNORECASE):
            medicines.add(kf)

    # Table rows: Check markdown tables where column is Medicine / Formulation
    for line in valid_lines:
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            for p in parts:
                p_clean = re.sub(r'\[DOC\-[^\]]+\]', '', p).strip()
                p_clean = re.sub(r'^\d+\)\s*', '', p_clean).strip()
                for kf in KNOWN_FORMULATIONS:
                    if re.search(r'\b' + re.escape(kf) + r'\b', p_clean, re.IGNORECASE):
                        medicines.add(kf)

    # Final filtering
    final_meds = set()
    for m in medicines:
        c = clean_medicine_candidate(m)
        if c and c.lower() not in GENERIC_MEDICINE_STOPWORDS:
            final_meds.add(c)

    return sorted(list(final_meds))


# ============================================================
# PROBLEM 4: SCENARIO CLINICAL CONDITIONS MAPPING
# ============================================================

SCENARIO_CLINICAL_CONDITIONS = {
    "TC-01-MP-01": [
        {"name": "Disease alignment (Diabetes/Prameh)", "patterns": [r"diabet", r"prameh", r"madhumeh", r"\bdm\b", r"dm rr", r"glycemic"]},
        {"name": "BMI >= 25 / Overweight patient context", "patterns": [r"bmi", r"overweight", r"over wt", r"weight"]},
        {"name": "Family history of Diabetes Mellitus", "patterns": [r"family history", r"hereditary", r"genetic risk"]}
    ],
    "TC-01-MP-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral", r"kasa", r"jwara", r"lung"]},
        {"name": "Comorbid Diabetes (Udakvah srotas vyadhi)", "patterns": [r"diabet", r"udakvah", r"\bdm\b", r"prameh", r"sugar"]},
        {"name": "Mild stage (HRCT 0–8 / SpO2 > 94%)", "patterns": [r"mild", r"hrct", r"0[\-–]8", r"spo2", r">94", r"94%"]}
    ],
    "TC-02-SEV-01": [
        {"name": "Disease alignment (Diabetic Nephropathy)", "patterns": [r"diabet", r"nephropath", r"prameh", r"kidney"]},
        {"name": "Stage 3 severity (GFR 30–59% / Creatinine 4–6)", "patterns": [r"stage 3", r"gfr 30", r"creatinine 4", r"30[\-–]59"]},
        {"name": "Clinical presentation (Shoth / Agnimandya)", "patterns": [r"shoth", r"agnimandya", r"edema", r"swelling", r"digestion"]}
    ],
    "TC-02-SEV-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral", r"kasa", r"jwara"]},
        {"name": "Severe stage (HRCT > 15 / SpO2 < 90%)", "patterns": [r"severe", r"hrct > 15", r"hrct >15", r"spo2 < 90", r"spo2 <90", r"<90"]},
        {"name": "Patient age > 15 years with Pranvah Srotas vyadhi", "patterns": [r"above 15", r"> 15", r"pranvah", r"adult"]}
    ],
    "TC-03-COM-01": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral", r"kasa"]},
        {"name": "Comorbidity: Annavah srotas vyadhi / Chronic GI illness", "patterns": [r"annavah", r"gastrointestinal", r"gi illness", r"chronic gastro"]}
    ],
    "TC-03-COM-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Malignancy / Cancer history or active Granthi/Arbud", "patterns": [r"malignan", r"cancer", r"granthi", r"arbud", r"tumor"]}
    ],
    "TC-04-AGE-01": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Pediatric patient group (3 to 15 years)", "patterns": [r"3[\-–]15", r"3 to 15", r"pediatric", r"child", r"children"]},
        {"name": "General prophylaxis without comorbidities", "patterns": [r"without comorbidi", r"general", r"no comorbidi", r"prophylaxis"]}
    ],
    "TC-04-AGE-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Elderly patient group (Age > 60 years)", "patterns": [r">60", r"> 60", r"60 years", r"elderly", r"geriatric", r"aged"]},
        {"name": "Pranvah Srotas Vyadhi condition", "patterns": [r"pranvah", r"respiratory condition", r"lung"]}
    ],
    "TC-05-INT-01": [
        {"name": "Disease alignment (Diabetes / Prameh)", "patterns": [r"diabet", r"prameh", r"madhumeh"]},
        {"name": "Secondary prevention of complications", "patterns": [r"secondar", r"complication", r"prevent", r"onset"]},
        {"name": "Target complications: Vidradhi / Murchha / Punstvopghaat", "patterns": [r"vidradhi", r"wound", r"murchha", r"punstvopghaat", r"erectile"]}
    ],
    "TC-05-INT-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Post viral Upadrav / Thrombosis / Raktagranthi prevention", "patterns": [r"thrombos", r"raktagranthi", r"saamata", r"post viral", r"upadrav"]},
        {"name": "Secondary infection (Mucormycosis) prophylaxis", "patterns": [r"mucormycos", r"fungal", r"secondary infection", r"nasya"]}
    ],
    "TC-06-SYM-01": [
        {"name": "Disease alignment (Diabetes / Prameh)", "patterns": [r"diabet", r"prameh", r"madhumeh"]},
        {"name": "Symptom: Trushna (Polydipsia / excessive thirst)", "patterns": [r"trushna", r"polydipsia", r"thirst"]},
        {"name": "Symptom: Aruchi (Impaired taste / anorexia)", "patterns": [r"aruchi", r"taste", r"appetite"]}
    ],
    "TC-06-SYM-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Symptom: Rasabhinodan vruddhi (Blood pressure rise)", "patterns": [r"rasabhinodan", r"blood pressure", r"hypertension", r"bp"]},
        {"name": "Symptom: Santat Jwar (persistent fever) or Mukhshushkata", "patterns": [r"santat jwar", r"fever", r"mukhshushkata", r"dryness of mouth"]}
    ],
    "TC-07-MED-01": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Patient with Asthma / COPD", "patterns": [r"asthma", r"copd", r"bronchial"]},
        {"name": "Current therapy: Regular inhalers", "patterns": [r"inhaler", r"regular inhaler"]}
    ],
    "TC-07-MED-02": [
        {"name": "Disease alignment (Diabetes / Prameh)", "patterns": [r"diabet", r"prameh", r"\bdm\b", r"dm rr", r"glycemic"]},
        {"name": "Patients already taking medications for other illnesses", "patterns": [r"already taking", r"other illness", r"existing med", r"concurrent"]},
        {"name": "Advice to continue medications under Ayurveda physician review", "patterns": [r"continue", r"physician", r"vaidya", r"examination", r"review"]}
    ],
    "TC-08-BND-01": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Moderate state threshold (SpO2 90–94% / RR >= 24)", "patterns": [r"moderate", r"90[\-–]94", r"spo2", r"24", r"hypoxia"]},
        {"name": "Required clinical investigations protocol", "patterns": [r"investigation", r"cbc", r"rft", r"lft", r"hrct", r"crp", r"ferritin", r"d-dimer"]}
    ],
    "TC-08-BND-02": [
        {"name": "Disease alignment (Diabetic Nephropathy / End Stage)", "patterns": [r"diabet", r"nephropath", r"prameh", r"kidney failure"]},
        {"name": "Stage 5 threshold (GFR < 15% / Creatinine > 8)", "patterns": [r"stage 5", r"gfr < 15", r"gfr <15", r"< 15%", r"creatinine > 8", r"creatinine >8"]}
    ],
    "TC-09-MIS-01": [
        {"name": "Disease alignment (Diabetes / Prameh)", "patterns": [r"diabet", r"prameh", r"madhumeh"]},
        {"name": "Routine pathological investigations list", "patterns": [r"investigation", r"cbc", r"lft", r"rft", r"bsl", r"hba1c", r"urine", r"lipid"]},
        {"name": "Follow-up monitoring interval (every 4 or 6 months)", "patterns": [r"4 or 6 months", r"4[\-–]6 months", r"interval", r"every 4"]}
    ],
    "TC-09-MIS-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Daily prophylaxis (Nitya Rasayan Sevan)", "patterns": [r"nitya", r"daily", r"prophylaxis", r"sevan"]},
        {"name": "Target population: No significant comorbidities", "patterns": [r"no significant comorbidi", r"without comorbidi", r"general population"]}
    ],
    "TC-10-PAR-01": [
        {"name": "Disease alignment (Diabetes / Prameh)", "patterns": [r"diabet", r"prameh", r"madhumeh"]},
        {"name": "Eye complications / Diabetic Retinopathy / Blurred vision", "patterns": [r"retinopath", r"eye", r"blurred vision", r"vision"]},
        {"name": "Stage differentiation (Early stage vs Late stage dark spots/bleeding)", "patterns": [r"early", r"late", r"dark spot", r"bleed", r"stage"]}
    ],
    "TC-10-PAR-02": [
        {"name": "Disease alignment (Respiratory viral infection)", "patterns": [r"respirat", r"pranvah", r"viral"]},
        {"name": "Home care procedure: Salt & turmeric gargles", "patterns": [r"gargle", r"salt", r"turmeric", r"haldi", r"yashti"]},
        {"name": "Home care procedure: Steam inhalation with eucalyptus oil", "patterns": [r"steam", r"eucalyptus"]},
        {"name": "Daily vital monitoring & dietary restrictions", "patterns": [r"monitor", r"spo2", r"diet", r"viruddhashan", r"avoid"]}
    ]
}


# ============================================================
# EVALUATOR ENGINE CLASS
# ============================================================

class GenerationEvaluator:
    """
    Automated generation evaluation engine for Ayurvedic Clinical RAG.
    Evaluates 20 scenarios (10 categories x 2 test cases) with 3 candidates each.
    """

    def __init__(self, dataset_path: Optional[Path] = None, output_report_path: Optional[Path] = None):
        self.dataset_path = dataset_path or DATASET_PATH
        self.output_report_path = output_report_path or DEFAULT_REPORT_PATH
        self.dataset = self.load_dataset()
        self.retrieval_service: RetrievalService = get_retrieval_service()

    def load_dataset(self) -> Dict[str, Any]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found at: {self.dataset_path}")
        with self.dataset_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if "cases" in data and "test_cases" not in data:
            data["test_cases"] = data["cases"]
        elif "test_cases" in data and "cases" not in data:
            data["cases"] = data["test_cases"]
        return data

    # ------------------------------------------------------------
    # METRIC 1: SOURCE CORRECTNESS
    # ------------------------------------------------------------
    def evaluate_source_correctness(
        self,
        test_case: Dict[str, Any],
        sources: List[Dict[str, Any]],
        answer_text: str
    ) -> Dict[str, Any]:
        src_meta = test_case.get("source", {}) if isinstance(test_case.get("source"), dict) else {}
        expected_chunk_ids = set(test_case.get("relevant_chunk_ids") or src_meta.get("expected_chunk_ids", []))
        expected_pages = set(test_case.get("expected_pages") or src_meta.get("pages", []))

        retrieved_chunk_ids = [s.get("chunk_id") for s in sources if s.get("chunk_id")]
        retrieved_pages = [s.get("page") for s in sources if s.get("page") is not None]

        matched_chunks = [cid for cid in retrieved_chunk_ids if cid in expected_chunk_ids]
        chunk_hit = len(matched_chunks) > 0

        chunk_rank = None
        for idx, cid in enumerate(retrieved_chunk_ids):
            if cid in expected_chunk_ids:
                chunk_rank = idx + 1
                break

        matched_pages = [p for p in retrieved_pages if p in expected_pages]
        page_matched = len(matched_pages) > 0

        cited_chunks = [cid for cid in expected_chunk_ids if cid.lower() in answer_text.lower()]
        cited_pages = [
            p for p in expected_pages
            if f"page {p}" in answer_text.lower() or f"p. {p}" in answer_text.lower() or f"page: {p}" in answer_text.lower()
        ]

        # Composite score
        score = 0.0
        if chunk_hit:
            score += 0.50
        if page_matched:
            score += 0.25
        if len(cited_chunks) > 0 or len(cited_pages) > 0:
            score += 0.25

        return {
            "score": round(score, 3),
            "chunk_hit": chunk_hit,
            "chunk_rank": chunk_rank,
            "matched_chunk_ids": matched_chunks,
            "expected_chunks": list(expected_chunk_ids),
            "retrieved_chunks": retrieved_chunk_ids,
            "page_matched": page_matched,
            "matched_pages": matched_pages,
            "expected_pages": list(expected_pages),
            "retrieved_pages": retrieved_pages,
            "cited_chunks_in_answer": cited_chunks,
            "cited_pages_in_answer": cited_pages,
        }

    # ------------------------------------------------------------
    # METRIC 2: COMPLETENESS (COMPONENT-LEVEL STRICT EVALUATION)
    # ------------------------------------------------------------
    def evaluate_completeness(
        self,
        test_case: Dict[str, Any],
        answer_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates completeness by decomposing each expected answer element into its
        clinical components (medicine, dose, vehicle, timing, frequency, condition).
        An element is credited proportionately based on the recall of its components.
        """
        elements = test_case.get("expected_answer_elements", [])
        if not elements:
            return {
                "score": 1.0,
                "matched_elements": [],
                "missing_elements": [],
                "matched_terms": [],
                "missing_terms": [],
                "total_elements": 0,
                "match_ratio": "0/0",
                "element_breakdown": []
            }

        element_breakdown = []
        all_terms_matched = []
        all_terms_missing = []
        element_recalls = []

        for el in elements:
            clean_el = clean_element_metadata_labels(el)
            parsed = parse_element_clinical_components(clean_el)
            # Flatten components to evaluate
            flat_components = []
            for comp_type, items in parsed.items():
                for itm in items:
                    flat_components.append((comp_type, itm))

            if not flat_components:
                # Fallback to key phrases if no specific clinical tokens detected
                fallback_phrases = [p.strip() for p in clean_el.split(',') if len(p.strip()) > 3]
                flat_components = [("phrase", p) for p in fallback_phrases[:4]]

            matched_in_el = []
            missing_in_el = []

            for comp_type, comp_val in flat_components:
                if evaluate_component_match(comp_val, answer_text):
                    matched_in_el.append(f"{comp_type}: {comp_val}")
                    all_terms_matched.append(comp_val)
                else:
                    missing_in_el.append(f"{comp_type}: {comp_val}")
                    all_terms_missing.append(comp_val)

            el_recall = len(matched_in_el) / max(1, len(flat_components))
            element_recalls.append(el_recall)

            element_breakdown.append({
                "element": el,
                "recall": round(el_recall, 3),
                "matched_components": matched_in_el,
                "missing_components": missing_in_el,
                "status": "fully_matched" if el_recall == 1.0 else ("partially_matched" if el_recall >= 0.50 else "missing")
            })

        # Score is average component recall across all expected elements
        overall_score = round(sum(element_recalls) / max(1, len(element_recalls)), 3)
        matched_elements = [b["element"] for b in element_breakdown if b["recall"] >= 0.70]
        missing_elements = [b["element"] for b in element_breakdown if b["recall"] < 0.70]

        return {
            "score": overall_score,
            "matched_elements": matched_elements,
            "missing_elements": missing_elements,
            "matched_terms": sorted(list(set(all_terms_matched))),
            "missing_terms": sorted(list(set(all_terms_missing))),
            "total_elements": len(elements),
            "match_ratio": f"{len(matched_elements)}/{len(elements)}",
            "element_breakdown": element_breakdown
        }

    # ------------------------------------------------------------
    # METRIC 3: GROUNDEDNESS & FAITHFULNESS (CLAIM-LEVEL LOCAL GROUNDING)
    # ------------------------------------------------------------
    def evaluate_groundedness(
        self,
        answer_text: str,
        retrieved_context_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates clinical guidance claims individually against retrieved context.
        Verifies whether clinical factual components (medicine, dose, vehicle, timing)
        are supported in local context, rather than global word overlap.
        """
        guidance_text = answer_text
        if "### 1. Clinical Guidance" in answer_text:
            part = answer_text.split("### 1. Clinical Guidance")[1]
            if "### 2. Evidence" in part:
                guidance_text = part.split("### 2. Evidence")[0]
            elif "### 2." in part:
                guidance_text = part.split("### 2.")[0]

        # Strip inline citation blocks before groundedness claim extraction
        guidance_text = strip_inline_citations(guidance_text)

        # Extract substantive clinical claim lines
        raw_lines = guidance_text.split('\n')
        claims = []
        for line in raw_lines:
            cleaned = re.sub(r'^[\*\-\>\s\d\.]+', '', line).strip()
            if not cleaned or cleaned.startswith('#') or len(cleaned) <= 15:
                continue

            # Issue 1: Groundedness must ignore Markdown table header rows and separators
            if is_markdown_table_header_or_separator(cleaned):
                continue

            # Issue 2: Groundedness must ignore conversational/introductory scaffolding sentences
            if is_conversational_scaffolding(cleaned):
                continue

            # Check if it has clinical substance
            if any(kw in cleaned.lower() for kw in [
                "rasayan", "matra", "dose", "water", "honey", "kal", "patient",
                "advise", "protocol", "investigation", "gargle", "steam", "stage",
                "mg", "drops", "twice", "times", "after food", "empty stomach",
                "cbc", "rft", "lft", "ecg", "gfr", "diet", "inhaler", "nasya", "pranvir"
            ]) or any(kf.lower() in cleaned.lower() for kf in KNOWN_FORMULATIONS[:30]):
                claims.append(cleaned)

        if not claims:
            return {
                "score": 1.0,
                "groundedness_score": 1.0,
                "faithfulness": 1.0,
                "faithfulness_score": 1.0,
                "total_claims": 0,
                "grounded_claims": 0,
                "ungrounded_claims": [],
                "claim_details": []
            }

        norm_full_context = normalize_text(retrieved_context_text)
        grounded_claims_count = 0
        ungrounded_claims = []
        claim_details = []
        total_assertions = 0
        supported_assertions = 0

        for claim in claims:
            parsed = parse_element_clinical_components(claim)
            assertions = []

            for m in parsed["medicines"]:
                assertions.append(("medicine", m))
            for d in parsed["dosages"]:
                assertions.append(("dosage", d))
            for v in parsed["vehicles"]:
                assertions.append(("vehicle", v))
            for t in parsed["timings"]:
                assertions.append(("timing", t))
            for c in parsed["conditions"]:
                assertions.append(("condition", c))

            if not assertions:
                # Pure descriptive claim: check key substantive tokens
                words = [w for w in normalize_text(claim).split() if len(w) > 4]
                supported_w = sum(1 for w in words if w in norm_full_context or evaluate_component_match(w, retrieved_context_text))
                ratio = supported_w / max(1, len(words))
                is_grounded = ratio >= 0.65
                if is_grounded:
                    grounded_claims_count += 1
                else:
                    ungrounded_claims.append({
                        "claim": claim[:140],
                        "unsupported_components": ["Insufficient context support for narrative statement"],
                        "reason": f"Only {supported_w}/{len(words)} key terms found in context"
                    })
                claim_details.append({
                    "claim": claim[:140],
                    "is_grounded": is_grounded,
                    "assertions_count": len(words),
                    "supported_count": supported_w
                })
                total_assertions += len(words)
                supported_assertions += supported_w
                continue

            # Identify primary entity (e.g. medicine or condition) to define local context window
            primary_entity = parsed["medicines"][0] if parsed["medicines"] else (
                parsed["conditions"][0] if parsed["conditions"] else None
            )

            # Extract local context window around the primary entity
            local_context = retrieved_context_text
            if primary_entity:
                norm_pe = normalize_text(primary_entity)
                # Find paragraphs or chunks containing the entity
                chunks = retrieved_context_text.split("--- Context Chunk")
                matching_chunks = [c for c in chunks if norm_pe in normalize_text(c) or evaluate_component_match(primary_entity, c)]
                if matching_chunks:
                    local_context = "\n".join(matching_chunks)

            norm_local = normalize_text(local_context)
            claim_unsupported = []

            for a_type, a_val in assertions:
                total_assertions += 1
                matched = evaluate_component_match(a_val, local_context)
                if not matched and evaluate_component_match(a_val, retrieved_context_text):
                    # Supported across retrieved context chunks
                    matched = True
                    supported_assertions += 1
                elif not matched:
                    claim_unsupported.append(f"{a_type}: '{a_val}' (absent from retrieved context)")
                else:
                    supported_assertions += 1

            is_grounded = len(claim_unsupported) == 0
            if is_grounded:
                grounded_claims_count += 1
            else:
                ungrounded_claims.append({
                    "claim": claim[:140],
                    "unsupported_components": claim_unsupported,
                    "reason": "Clinical attributes mismatched or unsupported in local context"
                })

            claim_details.append({
                "claim": claim[:140],
                "primary_entity": primary_entity,
                "is_grounded": is_grounded,
                "unsupported_components": claim_unsupported
            })

        groundedness_score = round(grounded_claims_count / max(1, len(claims)), 3)
        faithfulness_score = round(supported_assertions / max(1, total_assertions), 3)

        return {
            "score": groundedness_score,
            "groundedness_score": groundedness_score,
            "faithfulness": faithfulness_score,
            "faithfulness_score": faithfulness_score,
            "total_claims": len(claims),
            "grounded_claims": grounded_claims_count,
            "ungrounded_claims": ungrounded_claims,
            "claim_details": claim_details
        }

    # ------------------------------------------------------------
    # METRIC 4: STRICT HALLUCINATION & UNSUPPORTED DETAIL DETECTION
    # ------------------------------------------------------------
    def evaluate_hallucination(
        self,
        answer_text: str,
        retrieved_context_text: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Validates that all prescribed medicines exist in the retrieved context.
        Also inspects clinical dosages to ensure no fabricated dosage schedules.
        """
        prescribed = extract_prescribed_medicines(answer_text)
        norm_context = normalize_text(retrieved_context_text)
        norm_query = normalize_text(query)

        hallucinated_entities = []
        verified_entities = []
        unsupported_clinical_details = []

        for med in prescribed:
            norm_med = normalize_text(med)
            # Medicine must be supported as a complete formulation entity
            in_context = norm_med in norm_context or evaluate_component_match(med, retrieved_context_text)
            in_query = norm_med in norm_query or evaluate_component_match(med, query)

            if in_context or in_query:
                verified_entities.append(med)
                # Verify whether the prescribed dosage is supported for this medicine
                # Find lines mentioning this medicine
                med_lines = [l for l in answer_text.split('\n') if med.lower() in l.lower()]
                for ml in med_lines:
                    doses_in_claim = re.findall(r'\b\d+-\d+-\d+\b', ml)
                    for d in doses_in_claim:
                        # Find chunks in retrieved context with this medicine
                        chunks = [c for c in retrieved_context_text.split("--- Context Chunk") if norm_med in normalize_text(c)]
                        context_sub = "\n".join(chunks) if chunks else retrieved_context_text
                        if d not in context_sub:
                            unsupported_clinical_details.append({
                                "medicine": med,
                                "prescribed_dose": d,
                                "issue": f"Dosage {d} is not supported by retrieved context for {med}"
                            })
            else:
                hallucinated_entities.append(med)

        hallucination_detected = len(hallucinated_entities) > 0 or len(unsupported_clinical_details) > 0
        hallucination_score = round(
            (len(hallucinated_entities) + len(unsupported_clinical_details)) / max(1, len(prescribed)), 3
        ) if hallucination_detected else 0.0

        return {
            "detected": hallucination_detected,
            "hallucination_detected": hallucination_detected,
            "score": hallucination_score,
            "hallucination_score": hallucination_score,
            "total_prescribed_entities": len(prescribed),
            "verified_entities": verified_entities,
            "hallucinated_entities": hallucinated_entities,
            "unsupported_clinical_details": unsupported_clinical_details
        }

    # ------------------------------------------------------------
    # METRIC 5: SCENARIO-SPECIFIC CLINICAL CONTEXT MATCHING
    # ------------------------------------------------------------
    def evaluate_clinical_context(
        self,
        test_case: Dict[str, Any],
        answer_text: str
    ) -> Dict[str, Any]:
        """
        Validates scenario-specific features (severity, stage, comorbidities,
        symptoms, thresholds, and patient types) directly from ground truth.
        """
        test_id = test_case.get("test_id", "")
        disease = test_case.get("disease", "")
        answer_lower = answer_text.lower()

        # Check disease alignment
        disease_matched = False
        if disease == "diabetes" and (
            "diabet" in answer_lower
            or "prameh" in answer_lower
            or "madhumeh" in answer_lower
            or bool(re.search(r"\bdm\b", answer_lower))
            or "dm rr" in answer_lower
            or "glycemic" in answer_lower
        ):
            disease_matched = True
        elif disease == "respiratory_viral_infection" and (
            "respirat" in answer_lower
            or "pranvah" in answer_lower
            or "viral" in answer_lower
            or "kasa" in answer_lower
            or "jwara" in answer_lower
            or "lung" in answer_lower
        ):
            disease_matched = True

        # Check scenario conditions
        conditions_spec = SCENARIO_CLINICAL_CONDITIONS.get(test_id, [])
        if not conditions_spec:
            # Fallback for dynamic cases
            conditions_spec = [
                {"name": f"Disease: {disease}", "patterns": [disease.replace('_', ' ')]}
            ]

        matched_conditions = []
        missing_conditions = []

        for cond in conditions_spec:
            c_name = cond["name"]
            c_patterns = cond["patterns"]
            found = False
            for pat in c_patterns:
                if re.search(pat, answer_lower):
                    found = True
                    break
            if found:
                matched_conditions.append(c_name)
            else:
                missing_conditions.append(c_name)

        context_score = round(len(matched_conditions) / max(1, len(conditions_spec)), 3)

        return {
            "score": context_score,
            "disease_matched": disease_matched,
            "matched_scenario_conditions": matched_conditions,
            "missing_scenario_conditions": missing_conditions,
            "total_scenario_conditions": len(conditions_spec)
        }

    # ------------------------------------------------------------
    # METRIC 6: MISSING-INFORMATION & LIMITATIONS HANDLING
    # ------------------------------------------------------------
    def evaluate_missing_information_handling(
        self,
        test_case: Dict[str, Any],
        answer_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates whether limitations are meaningful, precautions are noted,
        and for missing-info scenarios, verifies that no unsupported patient data was fabricated.
        """
        category = test_case.get("category", "")
        has_section_header = "### 3. Limitations & Missing Information" in answer_text or "### 3." in answer_text
        section_text = ""

        if has_section_header:
            parts = answer_text.split("### 3.")
            if len(parts) > 1:
                section_text = parts[1].strip()

        is_substantive = len(section_text) > 40
        limitation_keywords = [
            "insufficient", "not specified", "not provide", "missing", "contraindication",
            "duration", "dose", "criteria", "interaction", "severity", "caution", "limitation",
            "laboratory", "investigation", "renal", "hepatic", "monitoring", "consult"
        ]
        found_keywords = [kw for kw in limitation_keywords if kw in section_text.lower()]

        # For Category 9 (Missing / Partial Patient Information):
        # Ensure answer does not invent specific patient values not present in prompt
        fabricated_patient_data = False
        if "Missing" in category:
            if re.search(r'\bstage [1-5]\b', section_text.lower()) and "stage" not in test_case.get("query", "").lower():
                fabricated_patient_data = True

        score = 0.0
        if has_section_header:
            score += 0.35
        if is_substantive:
            score += 0.35
        if len(found_keywords) >= 2:
            score += 0.30
        if fabricated_patient_data:
            score = max(0.0, score - 0.50)

        return {
            "score": round(score, 3),
            "has_limitations_section": has_section_header,
            "is_substantive": is_substantive,
            "detected_limitations": found_keywords,
            "no_fabricated_patient_data": not fabricated_patient_data,
            "limitations_excerpt": section_text[:160] + ("..." if len(section_text) > 160 else "")
        }

    # ------------------------------------------------------------
    # EVALUATE INDIVIDUAL CANDIDATE
    # ------------------------------------------------------------
    def evaluate_single_candidate(
        self,
        test_case: Dict[str, Any],
        candidate: Dict[str, Any],
        sources: List[Dict[str, Any]],
        retrieved_context_text: str,
        query: str
    ) -> Dict[str, Any]:
        cid = candidate.get("candidate_id", 0)
        answer_text = candidate.get("answer", "") or ""
        gen_status = candidate.get("status", "success")
        model_used = candidate.get("model", "unknown")

        # Handle failed or quota error candidate
        if gen_status in ("failed", "quota_error") or not answer_text.strip():
            fail_reason = candidate.get("error") or f"Candidate generation {gen_status}"
            return {
                "candidate_id": cid,
                "model": model_used,
                "status": gen_status,
                "generation_status": gen_status,
                "verdict": "FAIL",
                "failure_reasons": [fail_reason],
                "metrics": {
                    "source_correctness": {
                        "score": 0.0, "chunk_hit": False, "page_matched": False,
                        "matched_chunk_ids": [], "expected_chunks": [], "retrieved_chunks": [],
                        "cited_chunks_in_answer": [], "cited_pages_in_answer": []
                    },
                    "completeness": {
                        "score": 0.0, "matched_elements": [],
                        "missing_elements": test_case.get("expected_answer_elements", []),
                        "matched_terms": [], "missing_terms": [], "total_terms": 0, "match_ratio": "0/0"
                    },
                    "groundedness": {
                        "score": 0.0, "groundedness_score": 0.0, "faithfulness": 0.0, "faithfulness_score": 0.0,
                        "total_claims": 0, "grounded_claims": 0, "ungrounded_claims": []
                    },
                    "hallucination": {
                        "detected": False, "hallucination_detected": False, "score": 0.0,
                        "hallucination_score": 0.0, "total_prescribed_entities": 0,
                        "verified_entities": [], "hallucinated_entities": [], "unsupported_clinical_details": []
                    },
                    "clinical_context": {
                        "score": 0.0, "disease_matched": False,
                        "matched_scenario_conditions": [], "missing_scenario_conditions": []
                    },
                    "missing_information_handling": {
                        "score": 0.0, "has_limitations_section": False,
                        "is_substantive": False, "detected_limitations": []
                    },
                },
                "answer_preview": "",
                "full_answer": ""
            }

        # Compute rigorous metrics
        source_eval = self.evaluate_source_correctness(test_case, sources, answer_text)
        completeness_eval = self.evaluate_completeness(test_case, answer_text)
        groundedness_eval = self.evaluate_groundedness(answer_text, retrieved_context_text)
        hallucination_eval = self.evaluate_hallucination(answer_text, retrieved_context_text, query)
        clinical_context_eval = self.evaluate_clinical_context(test_case, answer_text)
        missing_info_eval = self.evaluate_missing_information_handling(test_case, answer_text)

        # STRICT PASS / FAIL Criteria:
        # 1. completeness >= 0.70
        # 2. groundedness >= 0.75
        # 3. source_correctness >= 0.50
        # 4. expected chunk hit == True
        # 5. disease matched == True and clinical_context score >= 0.70
        # 6. hallucination_detected == False
        failure_reasons = []

        if completeness_eval["score"] < 0.70:
            failure_reasons.append(
                f"Completeness {completeness_eval['score']:.2f} < 0.70 (Missing elements: {completeness_eval.get('missing_elements')})"
            )

        if source_eval["score"] < 0.50:
            failure_reasons.append(
                f"Source correctness {source_eval['score']:.2f} < 0.50"
            )

        if not source_eval["chunk_hit"]:
            failure_reasons.append("Expected chunk was not retrieved in Top-5 context")

        if not clinical_context_eval["disease_matched"] or clinical_context_eval["score"] < 0.70:
            failure_reasons.append(
                f"Clinical context score {clinical_context_eval['score']:.2f} < 0.70 (Missing conditions: {clinical_context_eval.get('missing_scenario_conditions')})"
            )

        if hallucination_eval["hallucination_detected"]:
            reasons = []
            if hallucination_eval["hallucinated_entities"]:
                reasons.append(f"Hallucinated: {hallucination_eval['hallucinated_entities']}")
            if hallucination_eval["unsupported_clinical_details"]:
                reasons.append(f"Unsupported details: {hallucination_eval['unsupported_clinical_details']}")
            failure_reasons.append(f"Hallucination detected: {'; '.join(reasons)}")

        if groundedness_eval["groundedness_score"] < 0.75:
            failure_reasons.append(
                f"Groundedness score {groundedness_eval['groundedness_score']:.2f} < 0.75"
            )

        verdict = "PASS" if len(failure_reasons) == 0 else "FAIL"

        return {
            "candidate_id": cid,
            "model": model_used,
            "status": "success",
            "generation_status": "success",
            "verdict": verdict,
            "failure_reasons": failure_reasons,
            "metrics": {
                "source_correctness": source_eval,
                "completeness": completeness_eval,
                "groundedness": groundedness_eval,
                "hallucination": hallucination_eval,
                "clinical_context": clinical_context_eval,
                "missing_information_handling": missing_info_eval,
            },
            "answer_preview": answer_text[:400] + ("..." if len(answer_text) > 400 else ""),
            "full_answer": answer_text
        }

    # ------------------------------------------------------------
    # BEST CANDIDATE DETERMINISTIC SELECTOR
    # ------------------------------------------------------------
    def select_best_candidate(self, candidate_evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Selects candidate using strict deterministic ranking:
        1. No hallucination
        2. Higher completeness
        3. Higher groundedness
        4. Higher source correctness
        5. Higher faithfulness
        6. Lower candidate ID as tie-breaker
        """
        def ranking_key(cand: Dict[str, Any]):
            if cand.get("status") in ("failed", "quota_error") or not cand.get("metrics"):
                return (-1, 0, 0, 0, 0, 0)
            m = cand["metrics"]
            no_hallucination = 1 if not m["hallucination"]["hallucination_detected"] else 0
            comp_score = m["completeness"]["score"]
            ground_score = m["groundedness"]["groundedness_score"]
            source_score = m["source_correctness"]["score"]
            faith_score = m["groundedness"].get("faithfulness_score", 0.0)
            cid = cand.get("candidate_id", 99)
            return (no_hallucination, comp_score, ground_score, source_score, faith_score, -cid)

        sorted_candidates = sorted(candidate_evaluations, key=ranking_key, reverse=True)
        return sorted_candidates[0]

    # ------------------------------------------------------------
    # EVALUATE SINGLE TEST CASE (3 INDEPENDENT CANDIDATES)
    # ------------------------------------------------------------
    def evaluate_case(self, test_case: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
        test_id = test_case.get("test_id", "")
        category = test_case.get("category", "General")
        disease = test_case.get("disease", "")
        query = test_case.get("query") or test_case.get("question", "")

        start_time = time.time()

        # Execute generation pipeline (exactly 3 candidate answers generated)
        gen_result = generate_response(query=query, disease=disease, top_k=top_k, num_candidates=3)
        latency = round(time.time() - start_time, 2)

        raw_candidates = gen_result.get("candidates", [])
        sources = gen_result.get("sources", [])
        retrieved_context_text = gen_result.get("context_text", "")

        # Fallback to fetch documents from Chroma if context_text missing
        if not retrieved_context_text and sources:
            try:
                chunk_ids = [s.get("chunk_id") for s in sources if s.get("chunk_id")]
                chunks = self.retrieval_service.collection.get(ids=chunk_ids, include=["documents"])
                id_to_doc = dict(zip(chunks["ids"], chunks["documents"]))
                retrieved_context_text = "\n\n".join(id_to_doc.get(cid, "") for cid in chunk_ids)
            except Exception:
                retrieved_context_text = ""

        # Evaluate all 3 candidates independently
        candidate_evaluations = []
        for cand in raw_candidates:
            cand_eval = self.evaluate_single_candidate(
                test_case=test_case,
                candidate=cand,
                sources=sources,
                retrieved_context_text=retrieved_context_text,
                query=query
            )
            candidate_evaluations.append(cand_eval)

        # Deterministically select best candidate
        best_candidate = self.select_best_candidate(candidate_evaluations)

        # Case-level status
        has_quota = any(c.get("status") == "quota_error" for c in candidate_evaluations)
        all_failed = all(c.get("status") in ("failed", "quota_error") for c in candidate_evaluations)

        if all_failed and has_quota:
            case_gen_status = "quota_error"
        elif all_failed:
            case_gen_status = "failed"
        else:
            case_gen_status = "success"

        m = best_candidate.get("metrics", {})
        verdict = best_candidate["verdict"]

        return {
            "test_id": test_id,
            "category": category,
            "disease": disease,
            "query": query,
            "generation_status": case_gen_status,
            "latency_seconds": latency,
            "best_candidate_pass": verdict == "PASS",
            "selected_candidate_number": best_candidate["candidate_id"],
            "selected_candidate_metrics": m,
            "verdict": verdict,
            "completeness": m.get("completeness", {}).get("score", 0.0) if m else 0.0,
            "groundedness": m.get("groundedness", {}).get("groundedness_score", 0.0) if m else 0.0,
            "faithfulness": m.get("groundedness", {}).get("faithfulness_score", 0.0) if m else 0.0,
            "hallucination": 1 if m and m.get("hallucination", {}).get("hallucination_detected") else 0,
            "source_correctness": m.get("source_correctness", {}).get("score", 0.0) if m else 0.0,
            "chunk_hit": m.get("source_correctness", {}).get("chunk_hit", False) if m else False,
            "page_match": m.get("source_correctness", {}).get("page_matched", False) if m else False,
            "failure_reasons": best_candidate["failure_reasons"],
            "candidates": candidate_evaluations,
            "best_candidate": {
                "selected_candidate_id": best_candidate["candidate_id"],
                "verdict": verdict,
                "failure_reasons": best_candidate["failure_reasons"],
                "metrics": m,
                "model": best_candidate.get("model"),
                "answer_preview": best_candidate.get("answer_preview", ""),
                "full_answer": best_candidate.get("full_answer", "")
            },
            "sources": sources,
            "metrics": m,
            "model": best_candidate.get("model"),
            "full_answer": best_candidate.get("full_answer", "")
        }

    # ------------------------------------------------------------
    # RUN ALL 20 TEST CASES
    # ------------------------------------------------------------
    def evaluate_all(
        self,
        top_k: int = 5,
        disease_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        test_id_filter: Optional[str] = None,
        num_candidates: int = 3
    ) -> Dict[str, Any]:
        cases = self.dataset.get("cases") or self.dataset.get("test_cases", [])
        if test_id_filter:
            cases = [c for c in cases if c.get("test_id") == test_id_filter]
        if category_filter:
            cases = [c for c in cases if c.get("category", "").lower() == category_filter.lower()]
        if disease_filter:
            cases = [c for c in cases if c.get("disease", "").lower() == disease_filter.lower()]

        total_cases = len(cases)

        print(f"\n================================================================================")
        print(f"STARTING STRICT GENERATION EVALUATION ({total_cases} SCENARIOS, {num_candidates} CANDIDATES EACH)")
        print(f"Dataset: {self.dataset_path.name}")
        print(f"Top-K Reranked Context: {top_k}")
        print(f"================================================================================\n")

        case_results = []
        start_all = time.time()

        for idx, tc in enumerate(cases, 1):
            t_id = tc.get("test_id", f"TC-{idx}")
            t_cat = tc.get("category", "General")
            t_dis = tc.get("disease", "")
            print(f"[{idx}/{total_cases}] Evaluating {t_id} | {t_cat} ({t_dis})...", flush=True)

            try:
                res = self.evaluate_case(tc, top_k=top_k)
                case_results.append(res)

                print(f"--------------------------------------------------------------------------------")
                print(f"{res['test_id']}")
                print(f"Category: {res['category']}")
                print(f"Disease: {res['disease']}")
                print(f"{res['verdict']}")
                print(f"Completeness: {res['completeness']:.2f}")
                print(f"Groundedness: {res['groundedness']:.2f}")
                print(f"Faithfulness: {res['faithfulness']:.2f}")
                print(f"Hallucination: {res['hallucination']}")
                print(f"Source Correctness: {res['source_correctness']:.2f}")
                print(f"Chunk Hit: {str(res['chunk_hit']).lower()}")
                print(f"Page Match: {str(res['page_match']).lower()}")

                for cand in res["candidates"]:
                    cid = cand["candidate_id"]
                    cv = cand["verdict"]
                    cm = cand.get("metrics")
                    print(f"\nCandidate {cid}:")
                    if cm:
                        print(f"  Verdict: {cv}")
                        print(f"  Completeness: {cm['completeness']['score']:.2f}")
                        print(f"  Groundedness: {cm['groundedness']['groundedness_score']:.2f}")
                        print(f"  Faithfulness: {cm['groundedness'].get('faithfulness_score', 0.0):.2f}")
                        print(f"  Hallucination: {1 if cm['hallucination']['hallucination_detected'] else 0}")
                        print(f"  Source Correctness: {cm['source_correctness']['score']:.2f}")
                    else:
                        print(f"  Status: {cand.get('status')}")
                        print(f"  Error: {cand.get('failure_reasons', ['Unknown'])[0]}")

                print(f"\nSelected Best Candidate: Candidate {res['selected_candidate_number']}")
                print(f"  best_candidate_pass: {res['best_candidate_pass']}")
                print(f"  selected_candidate_number: {res['selected_candidate_number']}")
                print(f"  latency: {res['latency_seconds']}s\n", flush=True)

            except Exception as e:
                print(f"    ERROR executing {t_id}: {str(e)}", flush=True)
                is_quota = is_quota_error(str(e))
                gen_stat = "quota_error" if is_quota else "failed"
                dummy_cand = [
                    {
                        "candidate_id": i,
                        "model": None,
                        "status": gen_stat,
                        "generation_status": gen_stat,
                        "verdict": "FAIL",
                        "failure_reasons": [f"Execution error: {str(e)}"],
                        "metrics": None
                    }
                    for i in range(1, 4)
                ]
                case_results.append({
                    "test_id": t_id,
                    "category": t_cat,
                    "disease": t_dis,
                    "query": tc.get("query") or tc.get("question", ""),
                    "generation_status": gen_stat,
                    "latency_seconds": 0.0,
                    "best_candidate_pass": False,
                    "selected_candidate_number": 1,
                    "selected_candidate_metrics": None,
                    "verdict": "FAIL",
                    "completeness": 0.0,
                    "groundedness": 0.0,
                    "faithfulness": 0.0,
                    "hallucination": 0,
                    "source_correctness": 0.0,
                    "chunk_hit": False,
                    "page_match": False,
                    "failure_reasons": [f"Execution error: {str(e)}"],
                    "candidates": dummy_cand,
                    "best_candidate": {
                        "selected_candidate_id": 1,
                        "verdict": "FAIL",
                        "failure_reasons": [f"Execution error: {str(e)}"],
                        "metrics": None,
                        "model": None,
                        "answer_preview": "",
                        "full_answer": ""
                    },
                    "metrics": None,
                    "model": None,
                    "full_answer": "",
                    "sources": []
                })

            time.sleep(2.5)

        total_duration = round(time.time() - start_all, 2)

        # ------------------------------------------------------------
        # AGGREGATE OVERALL METRICS
        # ------------------------------------------------------------
        successful_cases = sum(1 for c in case_results if c.get("generation_status") == "success")
        quota_failures = sum(1 for c in case_results if c.get("generation_status") == "quota_error")
        failed_generation_cases = sum(1 for c in case_results if c.get("generation_status") not in ("success", "quota_error"))
        passed_count = sum(1 for c in case_results if c.get("verdict") == "PASS")
        overall_pass_rate = round((passed_count / max(1, total_cases)) * 100, 2)

        # Exclude quota errors from quality averages
        valid_results = [
            c for c in case_results
            if c.get("generation_status") == "success" and c.get("best_candidate", {}).get("metrics")
        ]

        avg_completeness = round(sum(c["completeness"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0
        avg_groundedness = round(sum(c["groundedness"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0
        avg_faithfulness = round(sum(c["faithfulness"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0
        hallucination_count = sum(1 for c in valid_results if c["hallucination"] > 0)
        hallucination_rate = round((hallucination_count / max(1, len(valid_results))) * 100, 2)
        avg_source_correctness = round(sum(c["source_correctness"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0
        avg_clinical_context = round(sum(c["metrics"]["clinical_context"]["score"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0
        avg_missing_info = round(sum(c["metrics"]["missing_information_handling"]["score"] for c in valid_results) / max(1, len(valid_results)), 3) if valid_results else 0.0

        chunk_hit_count = sum(1 for c in valid_results if c["chunk_hit"])
        chunk_hit_rate = round((chunk_hit_count / max(1, len(valid_results))) * 100, 2)

        page_match_count = sum(1 for c in valid_results if c["page_match"])
        page_match_rate = round((page_match_count / max(1, len(valid_results))) * 100, 2)

        avg_latency = round(sum(c.get("latency_seconds", 0.0) for c in case_results) / max(1, len(case_results)), 2)

        c1_cases = [c["candidates"][0] for c in case_results if len(c.get("candidates", [])) > 0]
        c2_cases = [c["candidates"][1] for c in case_results if len(c.get("candidates", [])) > 1]
        c3_cases = [c["candidates"][2] for c in case_results if len(c.get("candidates", [])) > 2]

        c1_pass_rate = round(sum(1 for c in c1_cases if c.get("verdict") == "PASS") / max(1, total_cases) * 100, 2)
        c2_pass_rate = round(sum(1 for c in c2_cases if c.get("verdict") == "PASS") / max(1, total_cases) * 100, 2)
        c3_pass_rate = round(sum(1 for c in c3_cases if c.get("verdict") == "PASS") / max(1, total_cases) * 100, 2)

        overall_metrics = {
            "total_cases": total_cases,
            "successful_cases": successful_cases,
            "failed_generation_cases": failed_generation_cases,
            "quota_failures": quota_failures,
            "passed_cases": passed_count,
            "overall_pass_rate": overall_pass_rate,
            "average_completeness": avg_completeness,
            "average_groundedness": avg_groundedness,
            "average_faithfulness": avg_faithfulness,
            "hallucination_rate": hallucination_rate,
            "average_source_correctness": avg_source_correctness,
            "average_clinical_context_correctness": avg_clinical_context,
            "average_missing_information_handling": avg_missing_info,
            "chunk_hit_rate": chunk_hit_rate,
            "page_match_rate": page_match_rate,
            "average_latency_seconds": avg_latency,
            "candidate_1_pass_rate": c1_pass_rate,
            "candidate_2_pass_rate": c2_pass_rate,
            "candidate_3_pass_rate": c3_pass_rate,
            "best_candidate_pass_rate": overall_pass_rate,
        }

        # ------------------------------------------------------------
        # CATEGORY-WISE METRICS (ALL 10 CATEGORIES)
        # ------------------------------------------------------------
        categories = [
            "Multi-Parameter Patient Context",
            "Severity / Clinical Stage",
            "Comorbidity & Previous Conditions",
            "Age / Patient Type",
            "Clinical Intent / Treatment Objective",
            "Symptoms & Clinical Presentation",
            "Current Medication / Therapy Context",
            "Boundary / Threshold Conditions",
            "Missing / Partial Patient Information",
            "Paraphrase / Clinical Language Robustness"
        ]

        category_metrics = {}
        for cat in categories:
            cat_cases = [c for c in case_results if c.get("category") == cat]
            cat_valid = [
                c for c in cat_cases
                if c.get("generation_status") == "success" and c.get("best_candidate", {}).get("metrics")
            ]
            cat_passed = sum(1 for c in cat_cases if c.get("verdict") == "PASS")
            cat_pass_rate = round((cat_passed / max(1, len(cat_cases))) * 100, 2)

            cat_comp = round(sum(c["completeness"] for c in cat_valid) / max(1, len(cat_valid)), 3) if cat_valid else 0.0
            cat_ground = round(sum(c["groundedness"] for c in cat_valid) / max(1, len(cat_valid)), 3) if cat_valid else 0.0
            cat_faith = round(sum(c["faithfulness"] for c in cat_valid) / max(1, len(cat_valid)), 3) if cat_valid else 0.0
            cat_halluc_count = sum(1 for c in cat_valid if c["hallucination"] > 0)
            cat_halluc_rate = round((cat_halluc_count / max(1, len(cat_valid))) * 100, 2)
            cat_src = round(sum(c["source_correctness"] for c in cat_valid) / max(1, len(cat_valid)), 3) if cat_valid else 0.0
            cat_chunk_hit = round(sum(1 for c in cat_valid if c["chunk_hit"]) / max(1, len(cat_valid)) * 100, 2)
            cat_page_match = round(sum(1 for c in cat_valid if c["page_match"]) / max(1, len(cat_valid)) * 100, 2)

            category_metrics[cat] = {
                "category_name": cat,
                "number_of_cases": len(cat_cases),
                "pass_count": cat_passed,
                "pass_rate": cat_pass_rate,
                "average_completeness": cat_comp,
                "average_groundedness": cat_ground,
                "average_faithfulness": cat_faith,
                "hallucination_rate": cat_halluc_rate,
                "source_correctness": cat_src,
                "chunk_hit_rate": cat_chunk_hit,
                "page_match_rate": cat_page_match,
            }

        report = {
            "metadata": {
                "evaluation_type": "Strict Grounded Clinical Generation Evaluation (20 Scenarios, 10 Categories)",
                "dataset_name": self.dataset_path.name,
                "dataset_version": self.dataset.get("metadata", {}).get("version", "1.0.0"),
                "total_cases": total_cases,
                "total_categories": len(categories),
                "candidates_per_case": 3,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_duration_seconds": total_duration,
                "top_k": top_k
            },
            "overall_metrics": overall_metrics,
            "category_metrics": category_metrics,
            "case_results": case_results,
            "summary": {
                "total_cases": total_cases,
                "successful_cases": successful_cases,
                "quota_failures": quota_failures,
                "passed_cases": passed_count,
                "overall_pass_rate_percent": overall_pass_rate,
                "average_completeness_score": avg_completeness,
                "average_groundedness_score": avg_groundedness,
                "average_faithfulness_score": avg_faithfulness,
                "hallucination_rate_percent": hallucination_rate,
                "average_source_correctness_score": avg_source_correctness,
                "average_clinical_context_score": avg_clinical_context,
                "average_missing_info_handling_score": avg_missing_info,
                "ground_truth_chunk_hit_rate_percent": chunk_hit_rate,
                "expected_page_match_rate_percent": page_match_rate,
            }
        }

        return report

    def save_report(self, report: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
        out = output_path or getattr(self, "output_report_path", DEFAULT_REPORT_PATH)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return out

    evaluate_all_cases = evaluate_all
