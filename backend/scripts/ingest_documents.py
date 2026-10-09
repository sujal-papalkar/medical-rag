"""
Batch Document Ingestion CLI Script.

Extracts, chunks, and indexes all documents in data/uploads/ into ChromaDB.
"""

import sys
import argparse
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_collection

logger = get_logger("ingest-documents")


def main():
    parser = argparse.ArgumentParser(description="Batch Ingest Guideline Documents")
    parser.add_argument("--input-dir", type=str, default=str(settings.UPLOADS_PATH))
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    print("=" * 70)
    print("BATCH DOCUMENT INGESTION")
    print("=" * 70)
    print(f"Uploads Directory : {input_path}")
    print(f"Chunks File       : {settings.CHUNKS_PATH}")
    print(f"Chroma Directory  : {settings.CHROMA_PERSIST_DIR}")

    collection = get_collection()
    print(f"Current Vectors in '{collection.name}': {collection.count()}")

    files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.docx"))
    print(f"Documents found   : {len(files)}")
    for f in files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)")

    print("=" * 70)


if __name__ == "__main__":
    main()
