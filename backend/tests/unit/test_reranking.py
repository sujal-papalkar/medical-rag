"""
Unit tests for 70% Semantic + 30% Lexical Reranker.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.reranking import compute_lexical_score, rerank_candidates, normalize_text


class TestReranker(unittest.TestCase):

    def test_normalize_text(self):
        raw = "Asthma / COPD on Regular Inhalers!!!"
        self.assertEqual(normalize_text(raw), "asthma copd on regular inhalers")

    def test_lexical_term_overlap(self):
        query = "diabetes trushna"
        content = "Patient presenting with diabetes and severe trushna"
        score = compute_lexical_score(query, content)
        self.assertGreater(score, 0.4)

    def test_lexical_clinical_phrase_boost(self):
        query = "asthma regular inhalers pranvah srotas"
        content_with_phrase = "Guidelines for asthma on regular inhalers with pranvah srotas"
        content_without_phrase = "General guidelines for cough without inhalers"
        score1 = compute_lexical_score(query, content_with_phrase)
        score2 = compute_lexical_score(query, content_without_phrase)
        self.assertGreater(score1, score2)

    def test_rerank_candidates_formula_and_order(self):
        query = "diabetes trushna aruchi"
        candidates = [
            {"chunk_id": "c1", "distance": 0.40, "content": "general diabetes guidelines", "section": "overview"},
            {"chunk_id": "c2", "distance": 0.38, "content": "treatment for diabetes trushna aruchi", "section": "symptoms"}
        ]
        results = rerank_candidates(query, candidates, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["chunk_id"], "c2")
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[1]["rank"], 2)


if __name__ == "__main__":
    unittest.main()
