"""Pick the visual for a scene, degrading through three strategies.

    vector -> fuzzy -> None

Each layer is tried only if the one above is unavailable or returns nothing
above its confidence floor. The caller (services/asset_matcher.py) treats a
None as "keep what you had", so the existing tag scoring and finally the
procedural gradient remain underneath this whole module. Nothing here can
make a scene fail to render.

Why the order is this way round: the vector layer understands meaning, so a
scene saying "eligible farmer families" can retrieve an asset described as
"smallholder agriculture" with no shared words at all -- but it needs a
downloaded model and a built index. The fuzzy layer needs neither and is
always available, so it is the floor rather than the ceiling. A demo on a
fresh machine still selects sensible visuals; a demo on a prepared one
selects better ones.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from services.visual_rag.catalog import AssetRecord, load_catalog

logger = logging.getLogger(__name__)

# A vector hit below this is worse than what fuzzy matching would find, so it
# is not worth preferring purely because the model is available. Cosine
# similarity on MiniLM puts genuinely unrelated short texts around 0.0-0.15
# and loosely related ones around 0.25-0.4; 0.30 keeps the loose matches while
# rejecting noise.
VECTOR_MIN_SCORE = 0.30

# Fuzzy scores are not comparable to cosine similarity -- they come from a
# different scale entirely -- so this layer carries its own floor.
FUZZY_MIN_SCORE = 0.22

# Set VISUAL_RAG_DISABLE=1 to force the fuzzy path, which is how the fallback
# gets exercised on a machine that does have the model installed.
_DISABLE_ENV = "VISUAL_RAG_DISABLE"


@dataclass(frozen=True)
class Retrieval:
  record: AssetRecord
  score: float
  strategy: str  # "vector" | "fuzzy"


def _vector_disabled() -> bool:
  return os.environ.get(_DISABLE_ENV, "").strip().lower() in {"1", "true", "yes"}


def _try_vector(query: str, n_results: int, category: Optional[str]) -> List[Tuple[AssetRecord, float]]:
  if _vector_disabled():
    return []
  try:
    from services.visual_rag import embeddings, store

    if not embeddings.is_available() or not store.is_available():
      return []
    if store.count() == 0:
      logger.debug("visual vector index is empty; run scripts/build_visual_index.py")
      return []
    return store.query(query, n_results=n_results, category=category)
  except Exception:
    # An unavailable or half-built index must not break a render, and the
    # layer below will answer the same question adequately.
    logger.debug("vector retrieval unavailable; falling through to fuzzy", exc_info=True)
    return []


def _try_fuzzy(
    query: str,
    n_results: int,
    category: Optional[str],
    records: Optional[Sequence[AssetRecord]],
) -> List[Tuple[AssetRecord, float]]:
  try:
    from services.visual_rag import fuzzy

    return fuzzy.search(
        query,
        records=records,
        n_results=n_results,
        category=category,
        min_score=FUZZY_MIN_SCORE,
    )
  except Exception:
    logger.debug("fuzzy retrieval failed", exc_info=True)
    return []


def retrieve(
    query: str,
    category: Optional[str] = None,
    n_results: int = 5,
    records: Optional[Sequence[AssetRecord]] = None,
    media_type: Optional[str] = None,
) -> List[Retrieval]:
  """Ranked assets for `query`, best first, from whichever layer answered.

  `category` narrows to one FactCategory bucket; pass None to search the whole
  library, which is what a scene with no strong category preference wants.
  `media_type` filters to "image" or "video" after retrieval -- the ranking
  itself is media-agnostic because relevance does not depend on whether the
  match happens to be a still or a clip.
  """
  if not query or not query.strip():
    return []

  hits = _try_vector(query, n_results, category)
  strategy = "vector"
  hits = [(r, s) for r, s in hits if s >= VECTOR_MIN_SCORE]

  if not hits:
    hits = _try_fuzzy(query, n_results, category, records)
    strategy = "fuzzy"

  results = [Retrieval(record=r, score=s, strategy=strategy) for r, s in hits]

  if media_type:
    results = [r for r in results if r.record.media_type == media_type]

  if results:
    logger.info(
        "visual retrieval [%s] %r -> %s (%.3f)",
        strategy, query[:60], results[0].record.asset_id, results[0].score,
    )
  else:
    logger.info("visual retrieval found nothing for %r", query[:60])
  return results


def retrieve_best(
    query: str,
    category: Optional[str] = None,
    records: Optional[Sequence[AssetRecord]] = None,
    media_type: Optional[str] = None,
) -> Optional[Retrieval]:
  """Single best asset, or None to tell the caller to keep what it had."""
  results = retrieve(query, category=category, n_results=5, records=records, media_type=media_type)
  return results[0] if results else None


def describe_backends() -> str:
  """One-line summary of which layers are live, for the pipeline's step log.

  Worth printing on every run: the difference between a semantic match and a
  fuzzy one is invisible in the finished video, so without this there is no
  way to tell whether the index was actually used.
  """
  parts = []
  if _vector_disabled():
    parts.append(f"vector=disabled({_DISABLE_ENV})")
  else:
    try:
      from services.visual_rag import embeddings, store

      if embeddings.is_available() and store.is_available():
        parts.append(f"vector=ready({store.count()} indexed)")
      else:
        parts.append("vector=unavailable")
    except Exception:
      parts.append("vector=unavailable")

  try:
    from services.visual_rag import fuzzy  # noqa: F401

    parts.append(f"fuzzy=ready({len(load_catalog())} assets)")
  except Exception:
    parts.append("fuzzy=unavailable")

  return ", ".join(parts)
