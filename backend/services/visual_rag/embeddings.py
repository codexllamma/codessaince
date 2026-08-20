"""Sentence embeddings for the vector retrieval layer.

One small model, loaded once, shared by the indexer and by every query the
pipeline makes. `all-MiniLM-L6-v2` is chosen over anything larger because the
whole point of this layer is to run on the same machine that is already holding
a torch render pipeline in VRAM -- 384 dimensions and ~90MB of weights buy most
of the semantic win at a fraction of the cost.

Importing this module is deliberately cheap: nothing touches sentence-
transformers until someone actually asks for a vector, because the pipeline
imports the whole visual_rag package even on machines that will never embed
anything and fall straight through to fuzzy search.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384

# Guarded by _LOCK: two scenes embedding concurrently must not both pay the
# multi-second load, and must not race a half-constructed model into use.
_LOCK = threading.Lock()
_MODEL: Optional[Any] = None
_LOAD_FAILED = False


def _sentence_transformers() -> Any:
  """Indirection point so tests can simulate the dependency being absent."""
  from sentence_transformers import SentenceTransformer

  return SentenceTransformer


def _resolve_device() -> str:
  """CUDA when it is really there. A wrong guess here is not a slow run, it is
  a hard crash inside torch, so this stays a positive check rather than a
  preference."""
  try:
    import torch

    if torch.cuda.is_available():
      return "cuda"
  except Exception:  # torch missing or a broken CUDA install
    logger.debug("torch unavailable or CUDA probe failed; using cpu", exc_info=True)
  return "cpu"


def _get_model() -> Any:
  """The cached model, loading it on first use. Raises if it cannot load."""
  global _MODEL, _LOAD_FAILED

  if _MODEL is not None:
    return _MODEL

  with _LOCK:
    if _MODEL is not None:
      return _MODEL

    device = _resolve_device()
    logger.info("loading embedding model %s on %s", MODEL_NAME, device)
    try:
      model_cls = _sentence_transformers()
      model = model_cls(MODEL_NAME, device=device)
    except Exception:
      # Remembered so a machine with no model cache does not re-attempt a
      # failing download once per scene.
      _LOAD_FAILED = True
      raise

    # Renamed in sentence-transformers 6; the old name still works but warns.
    get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    dim = int(get_dim() or 0)
    if dim and dim != EMBED_DIM:
      logger.warning("model %s reports dim %d, expected %d", MODEL_NAME, dim, EMBED_DIM)

    _MODEL = model
    logger.info("embedding model ready (%s, dim=%d)", device, dim or EMBED_DIM)
    return _MODEL


def embed_texts(texts: Sequence[str]) -> np.ndarray:
  """Embed a batch. Returns shape (len(texts), EMBED_DIM), float32, L2-normalised.

  Normalised because everything downstream -- Chroma's cosine space and any
  hand-rolled reranking -- then treats a dot product as the similarity, and
  scores from different queries stay on one comparable scale.
  """
  items: List[str] = [t if isinstance(t, str) else str(t) for t in texts]
  if not items:
    return np.zeros((0, EMBED_DIM), dtype=np.float32)

  vectors = _get_model().encode(
      items,
      batch_size=32,
      convert_to_numpy=True,
      normalize_embeddings=True,
      show_progress_bar=False,
  )
  return np.asarray(vectors, dtype=np.float32).reshape(len(items), -1)


def embed_query(text: str) -> np.ndarray:
  """Embed one string. Returns shape (EMBED_DIM,), float32, L2-normalised."""
  return embed_texts([text])[0]


def is_available() -> bool:
  """Whether embedding will actually work here -- never raises.

  Callers use this to decide between vector search and the fuzzy fallback, so a
  missing package or an unreachable model download has to read as a plain False
  rather than take the pipeline down with it. The first call pays the model
  load; later ones are free.
  """
  if _MODEL is not None:
    return True
  if _LOAD_FAILED:
    return False
  try:
    _get_model()
    return True
  except Exception as exc:
    logger.warning("embeddings unavailable (%s: %s)", type(exc).__name__, exc)
    return False


def reset_model_cache() -> None:
  """Drop the cached model. For tests and for freeing VRAM after an indexing run."""
  global _MODEL, _LOAD_FAILED
  with _LOCK:
    _MODEL = None
    _LOAD_FAILED = False
