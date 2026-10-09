"""
Integration tests for Document Ingestion Pipeline.
"""

import sys
import unittest
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.rag.ingestion import ingest_file_to_pipeline


class TestIngestionIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        self.temp_file.write(b"Ayurvedic clinical management guideline sample content.")
        self.temp_file.close()
        self.temp_path = Path(self.temp_file.name)

    def tearDown(self):
        if self.temp_path.exists():
            self.temp_path.unlink()
        staged_copy = settings.UPLOADS_PATH / self.temp_path.name
        if staged_copy.exists():
            staged_copy.unlink()

    def test_ingest_file_stages_correctly(self):
        result = ingest_file_to_pipeline(self.temp_path)
        self.assertEqual(result["status"], "staged")
        self.assertEqual(result["file_name"], self.temp_path.name)
        staged_path = settings.UPLOADS_PATH / self.temp_path.name
        self.assertTrue(staged_path.exists())

    def test_ingest_missing_file_raises_error(self):
        non_existent = Path("non_existent_guideline_file.pdf")
        with self.assertRaises(FileNotFoundError):
            ingest_file_to_pipeline(non_existent)


if __name__ == "__main__":
    unittest.main()
