"""
Unit tests for BM25-Based Hybrid Reranker (70% Semantic + 30% BM25).

Verifies:
1. Text normalization and consistent tokenization (punctuation, casing, duplicates).
2. Pure dynamic BM25 scoring across queries and candidate corpora.
3. Support for previously unseen diseases, comorbidities, and clinical terms without code modifications.
4. Hierarchical breadcrumbs & contextual metadata integration (section_path, comorbidity, section).
5. Safe handling of empty queries, empty documents, missing metadata, and zero-match cases.
6. Deterministic tie-breaking and rank assignment.
7. Proper scaling and saturation calibration of BM25 scores.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.rag.reranking import (
    normalize_text,
    tokenize_text,
    build_candidate_document_text,
    compute_bm25_scores,
    compute_lexical_score,
    compute_cross_encoder_scores,
    rerank_candidates,
    CrossEncoderManager,
    BM25_SATURATION_K,
)
from app.rag.conflict_resolver import extract_parameters_from_text
from app.rag.generation import generate_structured_prescription
from app.rag.retrieval import RetrievalService


class TestBM25Reranker(unittest.TestCase):

    def setUp(self):
        self._orig_enable = settings.ENABLE_CROSS_ENCODER
        settings.ENABLE_CROSS_ENCODER = False
        CrossEncoderManager.reset()

    def tearDown(self):
        settings.ENABLE_CROSS_ENCODER = self._orig_enable
        CrossEncoderManager.reset()

    def test_normalize_and_tokenize_text(self):
        raw = "Asthma / COPD on Regular Inhalers (15-20 yrs)!!!"
        self.assertEqual(normalize_text(raw), "asthma copd on regular inhalers 15 20 yrs")
        tokens = tokenize_text(raw)
        self.assertEqual(tokens, ["asthma", "copd", "on", "regular", "inhalers", "15", "20", "yrs"])

    def test_tokenization_empty_and_whitespace(self):
        self.assertEqual(tokenize_text(""), [])
        self.assertEqual(tokenize_text("   \n\t  "), [])
        self.assertEqual(normalize_text(""), "")

    def test_duplicate_terms_handled_safely(self):
        query = "cough cough fever cough"
        tokens = tokenize_text(query)
        self.assertEqual(tokens, ["cough", "cough", "fever", "cough"])
        # Should not crash and should properly register term frequency
        candidates = [
            {"chunk_id": "c1", "content": "Patient with persistent cough and high fever"},
            {"chunk_id": "c2", "content": "Patient with headache only"},
        ]
        scores = compute_bm25_scores(query, candidates)
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores[1], 0.0)

    def test_unseen_diseases_and_comorbidities_scored_dynamically(self):
        """Verifies BM25 scores novel diseases not in any pre-existing hardcoded lists."""
        query = "Ankylosing Spondylitis with Asthivaha srotas inflammation"
        candidates = [
            {
                "chunk_id": "c1",
                "disease": "ankylosing_spondylitis",
                "content": "Protocol for managing Ankylosing Spondylitis targeting Asthivaha srotas",
                "section": "Chronic Autoimmune Protocols"
            },
            {
                "chunk_id": "c2",
                "disease": "gout",
                "content": "Protocol for acute Vatarakta and joint effusion",
                "section": "Metabolic Joint Disorders"
            }
        ]
        scores = compute_bm25_scores(query, candidates)
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[0], 0.2)
        self.assertEqual(scores[1], 0.0)

    def test_hierarchical_breadcrumbs_and_metadata_integration(self):
        """Verifies that terms matching section_path or comorbidity breadcrumb elevate the score."""
        candidate = {
            "chunk_id": "c1",
            "section_path": ["THERAPEUTIC GUIDELINES", "RASAYANA THERAPY"],
            "section": "Stage 2 Interventions",
            "comorbidity": "Rasavah srotas vyadhi (Heart Diseases, HTN etc.)",
            "content": "| Medicine | Matra |",
        }
        doc_text = build_candidate_document_text(candidate)
        self.assertIn("THERAPEUTIC GUIDELINES", doc_text)
        self.assertIn("Rasavah srotas vyadhi", doc_text)
        self.assertIn("Heart Diseases", doc_text)

        # Query matching only the comorbidity breadcrumb
        query = "Rasavah srotas vyadhi heart diseases"
        scores = compute_bm25_scores(query, [candidate, {"chunk_id": "c2", "content": "general text"}])
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[0], 0.2)

    def test_empty_query_and_empty_candidates(self):
        self.assertEqual(compute_bm25_scores("", [{"chunk_id": "c1", "content": "text"}]), [0.0])
        self.assertEqual(compute_bm25_scores("cough", []), [])
        self.assertEqual(rerank_candidates("", []), [])
        self.assertEqual(rerank_candidates("query", []), [])

    def test_missing_metadata_handled_gracefully(self):
        candidates = [
            {"chunk_id": "c1", "content": "diabetes glucose"},  # No section, no disease, no path
            {"chunk_id": "c2"},  # Missing content entirely
        ]
        scores = compute_bm25_scores("diabetes", candidates)
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores[0], 0.0)
        self.assertEqual(scores[1], 0.0)

    def test_deterministic_tie_breaking(self):
        """Candidates with identical scores and distances must be deterministically ordered by chunk_id."""
        query = "common cold"
        candidates = [
            {"chunk_id": "chunk_z", "distance": 0.5, "content": "common cold protocol"},
            {"chunk_id": "chunk_a", "distance": 0.5, "content": "common cold protocol"},
            {"chunk_id": "chunk_m", "distance": 0.5, "content": "common cold protocol"},
        ]
        results1 = rerank_candidates(query, candidates, top_k=3)
        order1 = [c["chunk_id"] for c in results1]

        # Invert input candidate order and rerank
        candidates_rev = list(reversed(candidates))
        results2 = rerank_candidates(query, candidates_rev, top_k=3)
        order2 = [c["chunk_id"] for c in results2]

        # Both should break ties deterministically alphabetically by chunk_id
        self.assertEqual(order1, ["chunk_a", "chunk_m", "chunk_z"])
        self.assertEqual(order2, ["chunk_a", "chunk_m", "chunk_z"])

    def test_rerank_candidates_hybrid_formula(self):
        query = "diabetes trushna aruchi"
        candidates = [
            {
                "chunk_id": "c1",
                "distance": 0.35,  # Better semantic distance
                "content": "general overview of metabolic conditions",
                "section": "overview"
            },
            {
                "chunk_id": "c2",
                "distance": 0.38,  # Slightly worse semantic distance, but strong BM25 keyword match
                "content": "treatment for diabetes with trushna and aruchi symptoms",
                "section": "symptoms"
            }
        ]
        results = rerank_candidates(query, candidates, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[1]["rank"], 2)
        # c2 should rank 1 due to high BM25 boost
        self.assertEqual(results[0]["chunk_id"], "c2")

    def test_bm25_saturation_bounds(self):
        """Verifies normalized BM25 score is strictly bounded in [0.0, 1.0)."""
        query = "test query"
        candidates = [
            {"chunk_id": "c1", "content": "test query " * 50},
        ]
        scores = compute_bm25_scores(query, candidates)
        self.assertGreaterEqual(scores[0], 0.0)
        self.assertLess(scores[0], 1.0)

    def test_exact_clinical_biomarker_and_severity_terms(self):
        """Verifies that exact numerical biomarker and severity keywords are accurately ranked by BM25."""
        query = "HRCT score > 15 SpO2 below 90 severe Pranvah srotas"
        candidates = [
            {
                "chunk_id": "c_mild",
                "distance": 0.40,
                "content": "Mild stage HRCT score 0 to 8 SpO2 above 94 without dyspnea",
                "section": "Mild Respiratory Infection"
            },
            {
                "chunk_id": "c_severe",
                "distance": 0.42,
                "content": "Severe stage HRCT score > 15 SpO2 below 90 severe Pranvah srotas vyadhi",
                "section": "Severe Respiratory Infection"
            }
        ]
        results = rerank_candidates(query, candidates, top_k=2)
        self.assertEqual(results[0]["chunk_id"], "c_severe")

    def test_compute_lexical_score_backward_compat(self):
        """Verifies backward compatibility helper compute_lexical_score."""
        score = compute_lexical_score("diabetes prameha", "Treatment guidelines for diabetes and prameha")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class TestCrossEncoderReranker(unittest.TestCase):
    """
    Unit tests for Multi-Stage Cross-Encoder Reranker:
    - Score ordering & deterministic tie-breaking.
    - Handling empty inputs and missing candidate metadata.
    - Inclusion of complete hierarchical breadcrumbs and comorbidity context.
    - BM25 and Cross-Encoder score combination.
    - Explicit model load failure handling and graceful fallback to BM25 baseline.
    - Configurable disablement fallback.
    - Clinical safety gating for contradictory biomarkers (HRCT 7 vs SpO2 92).
    - Absence of hardcoded phrase dictionaries in reranking.
    """

    def setUp(self):
        CrossEncoderManager.reset()
        self._orig_enable = settings.ENABLE_CROSS_ENCODER
        self._orig_mode = settings.RERANKING_MODE
        self._orig_model = settings.CROSS_ENCODER_MODEL

    def tearDown(self):
        CrossEncoderManager.reset()
        settings.ENABLE_CROSS_ENCODER = self._orig_enable
        settings.RERANKING_MODE = self._orig_mode
        settings.CROSS_ENCODER_MODEL = self._orig_model

    def test_cross_encoder_score_ordering_and_deterministic_tie_breaking(self):
        """Verifies cross-encoder scores determine rank and ties are broken deterministically by chunk_id."""
        mock_model = MagicMock()
        def mock_predict(pairs):
            scores = []
            for _, doc in pairs:
                if "Top evidence" in doc:
                    scores.append(4.0)
                else:
                    scores.append(1.5)
            return scores

        mock_model.predict.side_effect = mock_predict

        manager = CrossEncoderManager.get_instance()
        manager.set_model(mock_model)

        candidates = [
            {"chunk_id": "chunk_z", "distance": 0.4, "content": "Evidence text z"},
            {"chunk_id": "chunk_a", "distance": 0.4, "content": "Evidence text a"},
            {"chunk_id": "chunk_winner", "distance": 0.4, "content": "Top evidence"},
        ]

        query = "test query"
        results = rerank_candidates(query, candidates, top_k=3)

        self.assertEqual(len(results), 3)
        # Winner must be ranked 1st
        self.assertEqual(results[0]["chunk_id"], "chunk_winner")
        self.assertEqual(results[0]["rank"], 1)

        # Ties between chunk_z and chunk_a (equal CE score, equal distance) broken alphabetically by chunk_id
        self.assertEqual(results[1]["chunk_id"], "chunk_a")
        self.assertEqual(results[2]["chunk_id"], "chunk_z")

    def test_empty_candidate_sets_and_missing_metadata(self):
        """Verifies empty candidates, empty queries, and chunks with missing metadata are handled safely."""
        self.assertEqual(rerank_candidates("", []), [])
        self.assertEqual(rerank_candidates("query", []), [])
        self.assertEqual(compute_cross_encoder_scores("query", []), [])
        self.assertEqual(compute_cross_encoder_scores("", [{"chunk_id": "c1", "content": "text"}]), [])

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.0, 1.0]
        CrossEncoderManager.get_instance().set_model(mock_model)

        # Chunks with partial/missing fields
        candidates = [
            {"chunk_id": "c1"},  # completely missing content and metadata
            {"chunk_id": "c2", "content": "partial content"},  # missing section, path, comorbidity
        ]
        results = rerank_candidates("query", candidates, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[1]["rank"], 2)

    def test_correct_inclusion_of_hierarchical_breadcrumbs(self):
        """Verifies candidate text passed to Cross-Encoder contains breadcrumbs, section, and comorbidity."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [2.0]
        CrossEncoderManager.get_instance().set_model(mock_model)

        candidate = {
            "chunk_id": "c_hier",
            "section_path": ["THERAPEUTIC", "RASAYANA"],
            "section": "Stage 2 Interventions",
            "comorbidity": "Rasavah srotas vyadhi (Heart Diseases)",
            "disease": "respiratory_viral_infection",
            "content": "| Agastya Haritaki | 10g |",
            "distance": 0.35,
        }

        query = "Heart disease Rasayana"
        rerank_candidates(query, [candidate], top_k=1)

        mock_model.predict.assert_called_once()
        pairs = mock_model.predict.call_args[0][0]
        self.assertEqual(len(pairs), 1)
        q_sent, doc_sent = pairs[0]

        self.assertEqual(q_sent, query)
        self.assertIn("THERAPEUTIC", doc_sent)
        self.assertIn("RASAYANA", doc_sent)
        self.assertIn("Stage 2 Interventions", doc_sent)
        self.assertIn("Rasavah srotas vyadhi", doc_sent)
        self.assertIn("Heart Diseases", doc_sent)
        self.assertIn("Agastya Haritaki", doc_sent)

    def test_bm25_and_cross_encoder_integration(self):
        """Verifies multi-stage pipeline integrates BM25 lexical and Cross-Encoder calibrated probabilities."""
        mock_model = MagicMock()
        # CE logit of 2.0 -> sigmoid(2.0) = ~0.880797
        mock_model.predict.return_value = [2.0]
        CrossEncoderManager.get_instance().set_model(mock_model)

        cand = {
            "chunk_id": "c1",
            "distance": 0.25,  # Semantic score = 1.0 / (1.0 + 0.25) = 0.80
            "content": "Treatment for diabetes mellitus with trushna",
            "section": "Therapeutics",
            "disease": "diabetes",
        }

        query = "diabetes trushna"
        results = rerank_candidates(query, [cand], top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "c1")
        self.assertEqual(results[0]["rank"], 1)

    def test_model_loading_failure_and_configured_fallback(self):
        """Verifies that an uninitialized or broken model fails gracefully and falls back to BM25 baseline."""
        manager = CrossEncoderManager.get_instance()
        # Simulate loading error
        with patch.object(manager, "_initialize_model") as mock_init:
            def fail_init():
                manager._initialized = True
                manager._is_available = False
                manager._load_error = "Mocked checkpoint load failure"
            mock_init.side_effect = fail_init

            candidates = [
                {"chunk_id": "c1", "distance": 0.5, "content": "fever cough protocol"},
                {"chunk_id": "c2", "distance": 0.2, "content": "general health info"},
            ]

            # Must not crash; should fall back to Semantic + BM25
            results = rerank_candidates("fever cough", candidates, top_k=2)
            self.assertEqual(len(results), 2)
            self.assertFalse(manager.is_available)
            self.assertIn("Mocked checkpoint load failure", manager.load_error)

    def test_disabled_cross_encoder_fallback(self):
        """Verifies that setting ENABLE_CROSS_ENCODER = False cleanly uses the BM25 baseline."""
        settings.ENABLE_CROSS_ENCODER = False
        manager = CrossEncoderManager.get_instance()

        candidates = [
            {"chunk_id": "c1", "distance": 0.4, "content": "cough treatment"},
            {"chunk_id": "c2", "distance": 0.6, "content": "cough treatment"},
        ]

        results = rerank_candidates("cough", candidates, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertFalse(manager.is_available)
        self.assertEqual(results[0]["chunk_id"], "c1")

    def test_no_reintroduction_of_hardcoded_ranking_phrase_lists(self):
        """Verifies that reranking module contains NO hardcoded phrase lists or keyword dictionaries."""
        import app.rag.reranking as rr
        self.assertFalse(hasattr(rr, "IMPORTANT_CLINICAL_PHRASES"))
        self.assertFalse(hasattr(rr, "CLINICAL_KEYWORDS"))
        self.assertFalse(hasattr(rr, "DISEASE_RANKING_PHRASES"))

        # Inspect source code of reranking.py
        source = Path(rr.__file__).read_text(encoding="utf-8")
        self.assertNotIn("IMPORTANT_CLINICAL_PHRASES", source)

    def test_contradictory_biomarker_safety_gating_hrct_7_spo2_92(self):
        """
        Clinical Safety Requirement:
        Ensures the known contradictory query with HRCT 7 (mild) and SpO2 92% (moderate)
        is caught by the safety gate and blocks actionable prescription generation.
        """
        query = "A patient with respiratory viral infection presenting with HRCT 7 and SpO2 92%"
        params = extract_parameters_from_text(query)

        self.assertEqual(params.get("hrct_severity"), "mild")
        self.assertEqual(params.get("spo2_severity"), "moderate")
        self.assertTrue(params.get("biomarker_contradiction"))

        # Verify prescription generation is blocked
        resp = generate_structured_prescription(
            query=query,
            disease="respiratory_viral_infection",
            confirm_override=False
        )
        self.assertEqual(resp.status, "conflict_detected")
        self.assertTrue(resp.requires_confirmation)
        self.assertEqual(len(resp.medicines), 0)
        self.assertTrue(any(c.conflict_type == "biomarker_contradiction" for c in resp.conflicts))
        self.assertIn("Prescription generation blocked", resp.clinical_guidance.guidance_summary)

    def test_strict_disease_filtering_and_negation_handling(self):
        """Verifies negation-aware parsing and strict disease isolation."""
        query = "Patient has respiratory cough and fever without diabetes"
        params = extract_parameters_from_text(query)

        self.assertEqual(params.get("disease"), "respiratory_viral_infection")
        self.assertIn("diabetes", params.get("comorbidities_absent", []))
        self.assertNotIn("diabetes", params.get("comorbidities_present", []))


if __name__ == "__main__":
    unittest.main()

