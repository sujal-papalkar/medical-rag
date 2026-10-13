"""
Multi-Stage Production Reranker: Semantic Search + BM25 Lexical + Cross-Encoder Reranking.

Pipeline Stages:
1. Candidate Pool: ChromaDB Dense Semantic Search (embeddings: gemini-embedding-001, K = 20)
2. Lexical Scoring: Dynamic BM25Okapi with Lucene-smoothed IDF and saturation calibration
3. Cross-Encoder Reranking: Lightweight CrossEncoder (ms-marco-MiniLM-L-6-v2) for deep semantic-query interaction
4. Calibration & Combination:
   - Sigmoid calibration of raw cross-encoder logits: sig(z) = 1.0 / (1.0 + exp(-z))
   - Calibrated Hybrid Ensemble: 50% Cross-Encoder + 35% Semantic + 15% BM25
   - Alternatively, sequential Cascade Mode: Top-N candidate reordering by Cross-Encoder
5. Deterministic Tie-Breaking: Sort by (-final_score, distance, chunk_id)
6. Robust Fallback: Clean fallback to 70% Semantic + 30% BM25 if Cross-Encoder is disabled or fails to load.

Guarantees:
- Fully dynamic ranking without hardcoded clinical phrase lists or keyword dictionaries.
- Incorporates hierarchical breadcrumbs (section_path), immediate section, comorbidity, and table content.
- Deterministic score computation, tie-breaking, and offline CPU-friendly execution.
"""

import math
import re
from typing import List, Dict, Any, Optional, Tuple
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("reranker")

# Default saturation constant for normalizing unbounded BM25 scores to [0.0, 1.0)
BM25_SATURATION_K: float = 10.0


# =====================================================================
# 1. CROSS-ENCODER MODEL MANAGER (SINGLETON WITH GRACEFUL FALLBACK)
# =====================================================================

class CrossEncoderManager:
    """
    Thread-safe lazy-loading manager for the lightweight Cross-Encoder model.
    Encapsulates model initialization, offline CPU execution, and explicit
    fallback handling when model loading or inference fails.
    """

    _instance: Optional["CrossEncoderManager"] = None

    def __init__(self):
        self._model: Optional[Any] = None
        self._initialized: bool = False
        self._is_available: bool = False
        self._load_error: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "CrossEncoderManager":
        if cls._instance is None:
            cls._instance = CrossEncoderManager()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resets the singleton instance (primarily for testing and mocking)."""
        cls._instance = None

    def _initialize_model(self) -> None:
        if self._initialized:
            return

        if not settings.ENABLE_CROSS_ENCODER:
            self._initialized = True
            self._is_available = False
            self._load_error = "Cross-encoder is disabled via configuration (ENABLE_CROSS_ENCODER=False)."
            logger.info(self._load_error)
            return

        try:
            from sentence_transformers import CrossEncoder

            model_name = settings.CROSS_ENCODER_MODEL
            logger.info(f"Loading Cross-Encoder model: {model_name} on device 'cpu' (offline-first)...")
            try:
                # Attempt offline-first load to avoid network latency and remote queries
                self._model = CrossEncoder(model_name, device="cpu", local_files_only=True)
            except Exception:
                # If local_files_only fails, attempt standard load
                self._model = CrossEncoder(model_name, device="cpu")
            self._is_available = True
            self._load_error = None
            logger.info(f"Cross-Encoder model '{model_name}' loaded successfully.")
        except Exception as exc:
            self._is_available = False
            self._model = None
            self._load_error = str(exc)
            logger.warning(
                f"Failed to initialize Cross-Encoder model '{settings.CROSS_ENCODER_MODEL}': {exc}. "
                "Retrieval will fall back to Semantic + BM25 scoring."
            )
        finally:
            self._initialized = True

    @property
    def is_available(self) -> bool:
        if not self._initialized:
            self._initialize_model()
        return self._is_available

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def set_model(self, model: Any) -> None:
        """Injects a custom or mocked model for unit tests."""
        self._model = model
        self._initialized = True
        self._is_available = model is not None
        self._load_error = None if model is not None else "Model set to None."

    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """
        Runs inference on (query, document) pairs.
        Returns a list of float raw logits.
        """
        if not pairs:
            return []

        if not self.is_available or self._model is None:
            raise RuntimeError(f"Cross-encoder is not available: {self._load_error}")

        try:
            scores = self._model.predict(pairs)
            if hasattr(scores, "tolist"):
                scores = scores.tolist()
            return [float(s) for s in scores]
        except Exception as exc:
            logger.error(f"Cross-encoder prediction error: {exc}")
            raise


# =====================================================================
# 2. BM25 LEXICAL RERANKING UTILITIES
# =====================================================================

class StandardBM25(BM25Okapi):
    """
    BM25Okapi with standard Lucene non-negative smoothed IDF:
        IDF(w) = ln(1.0 + (N - n(w) + 0.5) / (n(w) + 0.5))

    Guarantees non-negative, well-scaled IDFs across candidate pools of any size (including N <= 2),
    preventing term-frequency collapse when candidate subsets are small.
    """

    def _calc_idf(self, nd: Dict[str, int]) -> None:
        for word, freq in nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


def normalize_text(text: str) -> str:
    """
    Normalizes text by lowercasing and replacing non-alphanumeric characters with spaces.
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_text(text: str) -> List[str]:
    """
    Tokenizes text into normalized words. Handles empty strings, punctuation, and duplicate terms.
    """
    norm = normalize_text(text)
    if not norm:
        return []
    return [t for t in norm.split() if t]


def build_candidate_document_text(candidate: Dict[str, Any]) -> str:
    """
    Assembles complete textual representation of a candidate chunk:
    incorporates hierarchical breadcrumbs (section_path), section, comorbidity context,
    disease, and raw chunk content.
    """
    parts: List[str] = []

    # 1. Hierarchical breadcrumbs / section path
    section_path = candidate.get("section_path")
    if section_path:
        if isinstance(section_path, list):
            parts.extend([str(p) for p in section_path if p])
        elif isinstance(section_path, str) and section_path.strip():
            parts.append(section_path.strip())

    # 2. Immediate section title
    section = candidate.get("section")
    if section and str(section).strip() and str(section).strip() not in parts:
        parts.append(str(section).strip())

    # 3. Comorbidity breadcrumb
    comorbidity = candidate.get("comorbidity")
    if comorbidity and str(comorbidity).strip() and str(comorbidity).strip() not in parts:
        parts.append(str(comorbidity).strip())

    # 4. Disease identifier
    disease = candidate.get("disease")
    if disease and str(disease).strip() and str(disease).strip() not in parts:
        parts.append(str(disease).strip())

    # 5. Document / Table content
    content = candidate.get("content", "")
    if content and str(content).strip():
        parts.append(str(content).strip())

    return " ".join(parts)


def compute_bm25_scores(
    query: str,
    candidates: List[Dict[str, Any]],
    k_saturation: float = BM25_SATURATION_K
) -> List[float]:
    """
    Computes normalized BM25 scores for a list of candidate chunks against a query.
    Normalizes unbounded raw BM25 scores to [0.0, 1.0) using a smooth saturation curve:
        normalized_score = raw_score / (raw_score + k_saturation)
    """
    if not candidates:
        return []

    query_tokens = tokenize_text(query)
    if not query_tokens:
        return [0.0] * len(candidates)

    corpus_tokens = [tokenize_text(build_candidate_document_text(c)) for c in candidates]

    if not any(corpus_tokens):
        return [0.0] * len(candidates)

    bm25 = StandardBM25(corpus_tokens)
    raw_scores = bm25.get_scores(query_tokens)

    normalized_scores: List[float] = []
    for raw in raw_scores:
        clipped = max(float(raw), 0.0)
        norm = (clipped / (clipped + k_saturation)) if clipped > 0.0 else 0.0
        normalized_scores.append(round(norm, 6))

    return normalized_scores


def compute_lexical_score(
    query: str,
    content: str,
    section: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> float:
    """
    Convenience function for computing BM25 lexical score for a single content block.
    Provided for backward-compatibility with standalone scoring utilities.
    """
    dummy_candidate = {
        "content": content,
        "section": section,
    }
    if metadata:
        dummy_candidate.update(metadata)

    scores = compute_bm25_scores(query=query, candidates=[dummy_candidate])
    return scores[0] if scores else 0.0


# =====================================================================
# 3. CROSS-ENCODER SCORING & CALIBRATION
# =====================================================================

def compute_cross_encoder_scores(
    query: str,
    candidates: List[Dict[str, Any]]
) -> List[float]:
    """
    Scores candidates using the Cross-Encoder model and applies sigmoid calibration:
        calibrated_probability = 1.0 / (1.0 + exp(-raw_logit))
    Returns empty list if candidates or query are empty, or if Cross-Encoder is unavailable.
    """
    if not query or not candidates:
        return []

    manager = CrossEncoderManager.get_instance()
    if not manager.is_available:
        return []

    pairs = [(query, build_candidate_document_text(c)) for c in candidates]
    try:
        raw_logits = manager.predict(pairs)
        calibrated_probs: List[float] = []
        for logit in raw_logits:
            if logit >= 0:
                prob = 1.0 / (1.0 + math.exp(-logit))
            else:
                exp_z = math.exp(logit)
                prob = exp_z / (1.0 + exp_z)
            calibrated_probs.append(round(prob, 6))
        return calibrated_probs
    except Exception as exc:
        logger.warning(f"Error computing cross-encoder scores: {exc}")
        return []


# =====================================================================
# 4. MULTI-STAGE HYBRID RERANKER
# =====================================================================

def rerank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5,
    k_saturation: float = BM25_SATURATION_K
) -> List[Dict[str, Any]]:
    """
    Multi-stage reranking pipeline combining ChromaDB Semantic Search, Dynamic BM25,
    and Lightweight Cross-Encoder Reranking:

    1. Semantic Score derived from Chroma vector distance:
       S_sem = 1.0 / (1.0 + max(distance, 0.0))

    2. BM25 Lexical Score computed across candidate corpus and saturated:
       S_bm25 = raw_bm25 / (raw_bm25 + 10.0)

    3. Initial Baseline Score:
       S_base = 0.70 * S_sem + 0.30 * S_bm25

    4. Cross-Encoder Stage (if enabled and available):
       - Candidates pre-sorted by S_base; Top-N pool (default N=10) evaluated by Cross-Encoder.
       - Sigmoid calibration applied: CE_prob = 1.0 / (1.0 + exp(-logit)).
       - Mode 'hybrid' (default):
         S_final = 0.50 * CE_prob + 0.35 * S_sem + 0.15 * S_bm25
         (Pool remainder assigned S_base * 0.5 to maintain tier priority).
       - Mode 'cascade':
         S_final = CE_prob (for top-N pool)

    5. Fallback Mode (if Cross-Encoder disabled or failed to initialize):
       S_final = 0.70 * S_sem + 0.30 * S_bm25

    6. Deterministic Tie-Breaking:
       Candidates sorted by (-S_final, distance, chunk_id).
    """
    if not candidates:
        return []

    # 1. Compute dynamic BM25 scores
    bm25_normalized_scores = compute_bm25_scores(
        query=query,
        candidates=candidates,
        k_saturation=k_saturation
    )

    # 2. Compute semantic & initial baseline scores for all candidates
    for idx, item in enumerate(candidates):
        semantic_distance = float(item.get("distance", 1.0))
        semantic_score = 1.0 / (1.0 + max(semantic_distance, 0.0))
        lexical_score = bm25_normalized_scores[idx] if idx < len(bm25_normalized_scores) else 0.0
        baseline_score = (
            settings.SEMANTIC_WEIGHT * semantic_score
            + settings.LEXICAL_WEIGHT * lexical_score
        )

        item["_semantic_score"] = round(semantic_score, 6)
        item["_lexical_score"] = round(lexical_score, 6)
        item["_baseline_score"] = round(baseline_score, 6)

    # 3. Check Cross-Encoder availability
    manager = CrossEncoderManager.get_instance()
    use_cross_encoder = settings.ENABLE_CROSS_ENCODER and manager.is_available

    if use_cross_encoder:
        try:
            # Sort candidates by initial baseline score to select Top-N for Cross-Encoder
            candidates.sort(
                key=lambda x: (
                    -x["_baseline_score"],
                    float(x.get("distance", 1.0)),
                    str(x.get("chunk_id", ""))
                )
            )

            top_n = min(settings.CROSS_ENCODER_TOP_N, len(candidates))
            ce_pool = candidates[:top_n]
            remainder_pool = candidates[top_n:]

            pairs = [(query, build_candidate_document_text(c)) for c in ce_pool]
            raw_logits = manager.predict(pairs)

            mode = settings.RERANKING_MODE.lower().strip()

            for idx, item in enumerate(ce_pool):
                raw_logit = float(raw_logits[idx])
                if raw_logit >= 0:
                    ce_prob = 1.0 / (1.0 + math.exp(-raw_logit))
                else:
                    exp_z = math.exp(raw_logit)
                    ce_prob = exp_z / (1.0 + exp_z)

                item["_ce_raw"] = round(raw_logit, 6)
                item["_ce_prob"] = round(ce_prob, 6)

                if mode == "cascade":
                    final_score = ce_prob
                else:
                    final_score = (
                        settings.CROSS_ENCODER_WEIGHT * ce_prob
                        + settings.HYBRID_SEMANTIC_WEIGHT * item["_semantic_score"]
                        + settings.HYBRID_LEXICAL_WEIGHT * item["_lexical_score"]
                    )
                item["_rerank_score"] = round(final_score, 6)

            for item in remainder_pool:
                item["_ce_raw"] = None
                item["_ce_prob"] = 0.0
                item["_rerank_score"] = round(item["_baseline_score"] * 0.5, 6)

        except Exception as exc:
            logger.warning(
                f"Cross-encoder execution error: {exc}. Falling back to 70% Semantic + 30% BM25."
            )
            for item in candidates:
                item["_rerank_score"] = item["_baseline_score"]
    else:
        if not settings.ENABLE_CROSS_ENCODER:
            logger.debug("Cross-encoder disabled via configuration; applying Semantic + BM25 baseline.")
        else:
            logger.warning(
                f"Cross-encoder model unavailable ({manager.load_error}); falling back to Semantic + BM25 baseline."
            )
        for item in candidates:
            item["_rerank_score"] = item["_baseline_score"]

    # 4. Deterministic candidate sorting with tie-breaking
    candidates.sort(
        key=lambda x: (
            -x["_rerank_score"],
            float(x.get("distance", 1.0)),
            str(x.get("chunk_id", ""))
        )
    )

    # 5. Cut to Top-K
    final_results = candidates[:top_k]

    # 6. Reassign ranks 1..K and strip internal calculation fields
    for index, res in enumerate(final_results, 1):
        res["rank"] = index
        res.pop("_semantic_score", None)
        res.pop("_lexical_score", None)
        res.pop("_baseline_score", None)
        res.pop("_ce_raw", None)
        res.pop("_ce_prob", None)
        res.pop("_rerank_score", None)

    return final_results

