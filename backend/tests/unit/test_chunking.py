"""
Unit tests for Structure-Aware Document Chunker.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.chunking import (
    clean_heading,
    is_signature,
    is_disclaimer_boilerplate,
    is_ocr_garbage,
    DISEASE_BY_DOCUMENT,
    TARGET_CHARS,
    MIN_CHUNK_CHARS,
)


class TestChunking(unittest.TestCase):

    def test_clean_heading(self):
        self.assertEqual(clean_heading("## Therapeutic Guidelines <!-- page: 5 -->"), "Therapeutic Guidelines")

    def test_signature_detection(self):
        self.assertTrue(is_signature("Thank you, Vd. Yogesh Bendale CMD, Ayurveda Rasayani"))
        self.assertFalse(is_signature("Administer Somtajvir 1 tablet twice daily"))

    def test_disclaimer_boilerplate_detection(self):
        self.assertTrue(is_disclaimer_boilerplate("Only for the guidance of registered ayurvedic medical practitioners"))
        self.assertFalse(is_disclaimer_boilerplate("Treatment of Pratishyaya with warm water"))

    def test_ocr_garbage_detection(self):
        self.assertTrue(is_ocr_garbage("`"))
        self.assertTrue(is_ocr_garbage("\u65e5"))
        self.assertFalse(is_ocr_garbage("Somtajvir"))

    def test_disease_mapping_configured(self):
        self.assertIn("DM RR", DISEASE_BY_DOCUMENT)
        self.assertEqual(DISEASE_BY_DOCUMENT["DM RR"], "diabetes")


if __name__ == "__main__":
    unittest.main()
