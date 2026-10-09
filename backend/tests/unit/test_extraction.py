"""
Unit tests for Docling Extraction and Provenance Utilities.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.extraction import json_safe, get_page_numbers, SUPPORTED_EXTENSIONS


class DummyProv:
    def __init__(self, page_no):
        self.page_no = page_no


class DummyItem:
    def __init__(self, pages):
        self.prov = [DummyProv(p) for p in pages]


class TestExtraction(unittest.TestCase):

    def test_supported_extensions(self):
        self.assertIn(".pdf", SUPPORTED_EXTENSIONS)
        self.assertIn(".docx", SUPPORTED_EXTENSIONS)

    def test_json_safe_primitives(self):
        self.assertEqual(json_safe(42), 42)
        self.assertEqual(json_safe("text"), "text")
        self.assertEqual(json_safe(Path("a/b")), str(Path("a/b")))

    def test_get_page_numbers(self):
        item = DummyItem([5, 3, 5])
        pages = get_page_numbers(item)
        self.assertEqual(pages, [3, 5])


if __name__ == "__main__":
    unittest.main()
