"""
Unit tests for Candidate Retrieval & Vector Search Service (RetrievalService).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.rag.retrieval import RetrievalService, get_retrieval_service
from app.database.connection import get_collection


class TestRetrievalUnit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = get_retrieval_service()
        cls.collection = get_collection()

    def test_chroma_collection_exists_and_has_121_vectors(self):
        self.assertEqual(self.collection.name, "medical_guidelines")
        self.assertEqual(self.collection.count(), 121)

    def test_empty_query_returns_empty_list(self):
        results = self.service.retrieve("")
        self.assertEqual(results, [])
        results_ws = self.service.retrieve("   ")
        self.assertEqual(results_ws, [])

    def test_embedding_dimension(self):
        emb = self.service.create_embedding("Ayurvedic management of Prameha")
        self.assertEqual(len(emb), settings.EMBEDDING_DIMENSION)
        self.assertEqual(len(emb), 768)

    def test_retrieval_returns_ranked_results_with_metadata(self):
        results = self.service.retrieve("diabetes mellitus blood sugar control", top_k=5)
        base_results = [r for r in results if not r.get("is_continuation_bundled")]
        self.assertLessEqual(len(base_results), 5)

        for rank, r in enumerate(results, start=1):
            self.assertEqual(r["rank"], rank)
            self.assertIn("chunk_id", r)
            self.assertIn("document_name", r)
            self.assertIn("content", r)
            self.assertIn("distance", r)
            self.assertGreaterEqual(r["distance"], 0.0)

    def test_disease_filter(self):
        results = self.service.retrieve("fever and cough", disease="respiratory_viral_infection", top_k=3)
        self.assertGreater(len(results), 0)
        for r in results:
            if r.get("disease"):
                self.assertEqual(r["disease"], "respiratory_viral_infection")


if __name__ == "__main__":
    unittest.main()
