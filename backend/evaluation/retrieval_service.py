"""
Retrieval Service for Evaluation.

Retrieval flow:
1. Create Gemini query embedding.
2. Retrieve a larger semantic candidate set from ChromaDB.
3. Rerank candidates using lexical/context relevance.
4. Return the final Top-K results.

The underlying documents, chunks, embeddings, and ChromaDB are unchanged.
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from dotenv import load_dotenv
from google import genai


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent

ENV_PATH = BACKEND_DIR / ".env"
CHROMA_DB_PATH = BACKEND_DIR / "chroma_db"
CHUNKS_FILE_PATH = BACKEND_DIR / "chunked_output" / "chunks.json"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        f"GEMINI_API_KEY not found in {ENV_PATH} or environment"
    )


COLLECTION_NAME = "medical_guidelines"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768

# Final number of results returned to evaluator
DEFAULT_TOP_K = 10

# Retrieve more candidates first, then rerank them.
CANDIDATE_TOP_K = 20


# ============================================================
# RETRIEVAL SERVICE
# ============================================================

class RetrievalService:

    def __init__(self):

        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        self.chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH)
        )

        self.collection = self.chroma_client.get_collection(
            COLLECTION_NAME
        )

        self._chunks_cache = None


    # ========================================================
    # EMBEDDING
    # ========================================================

    def create_embedding(self, text: str) -> List[float]:

        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config={
                "output_dimensionality": EMBEDDING_DIMENSION
            }
        )

        return response.embeddings[0].values


    # ========================================================
    # TEXT NORMALIZATION
    # ========================================================

    @staticmethod
    def normalize_text(text: str) -> str:

        text = text.lower()

        # Keep letters/numbers, convert everything else to spaces
        text = re.sub(r"[^a-z0-9]+", " ", text)

        return re.sub(r"\s+", " ", text).strip()


    # ========================================================
    # LEXICAL / CONTEXT RERANKING
    # ========================================================

    def lexical_score(
        self,
        query: str,
        content: str,
        section: str = ""
    ) -> float:

        query_normalized = self.normalize_text(query)
        content_normalized = self.normalize_text(
            f"{section} {content}"
        )

        query_terms = set(
            query_normalized.split()
        )

        content_terms = set(
            content_normalized.split()
        )

        if not query_terms or not content_terms:
            return 0.0

        # ----------------------------------------------------
        # Basic term overlap
        # ----------------------------------------------------

        overlap = query_terms.intersection(
            content_terms
        )

        overlap_score = (
            len(overlap) / len(query_terms)
        )


        # ----------------------------------------------------
        # Important clinical phrases
        # ----------------------------------------------------

        important_phrases = [
            "asthma",
            "copd",
            "regular inhalers",
            "inhalers",
            "pranvah srotas",
            "rasayana",
            "prophylaxis",
            "prophylactic",
            "medicine",
            "matra",
            "sahpaan",
            "aushadh kal",
            "dose",
            "timing",
        ]

        phrase_score = 0.0

        for phrase in important_phrases:

            phrase_normalized = self.normalize_text(
                phrase
            )

            if phrase_normalized in content_normalized:

                # Only reward the phrase if it is also
                # relevant to the query.
                query_phrase_present = (
                    phrase_normalized in query_normalized
                )

                if query_phrase_present:
                    phrase_score += 0.20


        # ----------------------------------------------------
        # Exact multi-word phrase matching
        # ----------------------------------------------------

        query_words = query_normalized.split()

        bigram_matches = 0
        total_bigrams = max(
            len(query_words) - 1,
            1
        )

        for i in range(len(query_words) - 1):

            bigram = (
                query_words[i]
                + " "
                + query_words[i + 1]
            )

            if bigram in content_normalized:
                bigram_matches += 1

        bigram_score = (
            bigram_matches / total_bigrams
        )


        # ----------------------------------------------------
        # Final lexical score
        # ----------------------------------------------------

        score = (
            0.45 * overlap_score
            + 0.35 * bigram_score
            + 0.20 * min(phrase_score, 1.0)
        )

        return score


    # ========================================================
    # RERANK
    # ========================================================

    def rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        if not results:
            return results


        for result in results:

            semantic_distance = float(
                result.get("distance", 1.0)
            )

            # Chroma distance: lower = better.
            # Convert it into a similarity-like score.
            semantic_score = 1.0 / (
                1.0 + max(semantic_distance, 0.0)
            )

            lexical_score = self.lexical_score(
                query=query,
                content=result.get("content", ""),
                section=result.get("section", "")
            )

            # Semantic retrieval remains dominant,
            # lexical relevance helps resolve close matches.
            final_score = (
                0.70 * semantic_score
                + 0.30 * lexical_score
            )

            result["_semantic_score"] = round(
                semantic_score,
                6
            )

            result["_lexical_score"] = round(
                lexical_score,
                6
            )

            result["_rerank_score"] = round(
                final_score,
                6
            )


        # Highest final score first
        results.sort(
            key=lambda x: x["_rerank_score"],
            reverse=True
        )


        # Reassign ranks after reranking
        for index, result in enumerate(results):

            result["rank"] = index + 1


        return results


    # ========================================================
    # RETRIEVE
    # ========================================================

    def retrieve(
        self,
        query: str,
        disease: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K
    ) -> List[Dict[str, Any]]:

        # ----------------------------------------------------
        # 1. Create query embedding
        # ----------------------------------------------------

        query_embedding = self.create_embedding(
            query
        )


        # ----------------------------------------------------
        # 2. Disease filter
        # ----------------------------------------------------

        where_filter = None

        if disease and disease.strip():

            where_filter = {
                "disease": disease.strip()
            }


        # ----------------------------------------------------
        # 3. Retrieve larger candidate set
        # ----------------------------------------------------

        candidate_k = max(
            CANDIDATE_TOP_K,
            top_k
        )


        if where_filter:

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=candidate_k,
                where=where_filter,
                include=[
                    "documents",
                    "metadatas",
                    "distances"
                ]
            )

        else:

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=candidate_k,
                include=[
                    "documents",
                    "metadatas",
                    "distances"
                ]
            )


        # ----------------------------------------------------
        # 4. Convert Chroma response
        # ----------------------------------------------------

        ids = (
            results["ids"][0]
            if results.get("ids")
            else []
        )

        documents = (
            results["documents"][0]
            if results.get("documents")
            else []
        )

        metadatas = (
            results["metadatas"][0]
            if results.get("metadatas")
            else []
        )

        distances = (
            results["distances"][0]
            if results.get("distances")
            else []
        )


        formatted_results = []


        for i in range(len(ids)):

            meta = (
                metadatas[i]
                if i < len(metadatas)
                else {}
            )

            formatted_results.append({

                "rank": i + 1,

                "chunk_id": ids[i],

                "distance": (
                    round(
                        float(distances[i]),
                        4
                    )
                    if i < len(distances)
                    else None
                ),

                "document_name": meta.get(
                    "document_name",
                    ""
                ),

                "page": meta.get(
                    "page"
                ),

                "disease": meta.get(
                    "disease",
                    ""
                ),

                "content_type": meta.get(
                    "content_type",
                    ""
                ),

                "section": meta.get(
                    "section",
                    ""
                ),

                "content": (
                    documents[i]
                    if i < len(documents)
                    else ""
                )
            })


        # ----------------------------------------------------
        # 5. Rerank candidates
        # ----------------------------------------------------

        reranked_results = self.rerank_results(
            query=query,
            results=formatted_results
        )


        # ----------------------------------------------------
        # 6. Return final Top-K
        # ----------------------------------------------------

        final_results = reranked_results[
            :top_k
        ]


        # Remove internal scoring fields from
        # the final evaluation output.
        for result in final_results:

            result.pop(
                "_semantic_score",
                None
            )

            result.pop(
                "_lexical_score",
                None
            )

            result.pop(
                "_rerank_score",
                None
            )


        # Reassign final ranks
        for index, result in enumerate(
            final_results
        ):

            result["rank"] = index + 1


        return final_results


    # ========================================================
    # GET CHUNK BY ID
    # ========================================================

    def get_chunk_by_id(
        self,
        chunk_id: str
    ) -> Optional[Dict[str, Any]]:

        if self._chunks_cache is None:

            if CHUNKS_FILE_PATH.exists():

                with CHUNKS_FILE_PATH.open(
                    "r",
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)

                chunk_list = (
                    data.get("chunks", data)
                    if isinstance(data, dict)
                    else data
                )

                self._chunks_cache = {
                    c["chunk_id"]: c
                    for c in chunk_list
                    if "chunk_id" in c
                }

            else:

                self._chunks_cache = {}


        return self._chunks_cache.get(
            chunk_id
        )


# ============================================================
# SINGLETON
# ============================================================

_service_instance: Optional[
    RetrievalService
] = None


def get_retrieval_service() -> RetrievalService:

    global _service_instance

    if _service_instance is None:

        _service_instance = RetrievalService()

    return _service_instance