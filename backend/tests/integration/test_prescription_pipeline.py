"""
Integration test for End-to-End Structured Prescription Pipeline.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.prescriptions import PatientInfo
from app.rag.generation import generate_structured_prescription


class TestPrescriptionPipeline(unittest.TestCase):

    def test_structured_prescription_empty_query(self):
        resp = generate_structured_prescription(query="", disease="diabetes")
        self.assertEqual(resp.status, "invalid_query")
        self.assertEqual(len(resp.medicines), 0)

    def test_structured_prescription_insufficient_context(self):
        resp = generate_structured_prescription(
            query="unsupported non-guideline Martian disease x999",
            disease="diabetes",
            top_k=2
        )
        # Should complete gracefully with valid or controlled fallback
        self.assertIn(resp.status, ["success", "insufficient_context", "partial_success"])
        self.assertIsNotNone(resp.clinical_guidance)


if __name__ == "__main__":
    unittest.main()
