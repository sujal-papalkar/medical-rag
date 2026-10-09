"""
ChromaDB Connection Management.

Provides singleton access to the persistent ChromaDB client, ensuring all
modules access the single verified database in backend/chroma_db and never
spawn empty databases in current working directories.
"""

from typing import Optional
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("chroma-connection")

_chroma_client: Optional[ClientAPI] = None
_collection_cache: Optional[Collection] = None


def get_chroma_client() -> ClientAPI:
    """Returns the persistent ChromaDB client singleton."""
    global _chroma_client
    if _chroma_client is None:
        logger.info(f"Initializing Persistent ChromaDB client at: {settings.CHROMA_PERSIST_DIR}")
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection(name: Optional[str] = None) -> Collection:
    """
    Returns the target ChromaDB collection (default: 'medical_guidelines').
    Verifies that the collection exists without wiping or recreating it.
    """
    global _collection_cache
    target_name = name or settings.CHROMA_COLLECTION_NAME

    if _collection_cache is None or _collection_cache.name != target_name:
        client = get_chroma_client()
        logger.info(f"Retrieving existing Chroma collection: '{target_name}'")
        try:
            _collection_cache = client.get_collection(target_name)
        except Exception as exc:
            logger.error(f"Collection '{target_name}' not found: {exc}")
            raise
    return _collection_cache


def verify_database_health() -> dict:
    """Checks collection existence and vector count."""
    try:
        col = get_collection()
        count = col.count()
        return {
            "status": "healthy",
            "path": settings.CHROMA_PERSIST_DIR,
            "collection": col.name,
            "vector_count": count
        }
    except Exception as exc:
        return {
            "status": "error",
            "path": settings.CHROMA_PERSIST_DIR,
            "error": str(exc)
        }
