"""The ChromaDB vector index over the asset catalogue.

One persistent collection, `visual_assets`, holding one entry per catalogued
image or clip: the id is the asset id, the document is `AssetRecord.
embedding_text()`, and the metadata is `AssetRecord.as_metadata()` so a hit can
be rehydrated into a real record without going back to disk.

Everything here degrades rather than raises on the read path. A machine with no
index -- or no chromadb at all -- must still render; it just falls through to
fuzzy search instead.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.visual_rag import embeddings
from services.visual_rag.catalog import BACKEND_DIR, AssetRecord

logger = logging.getLogger(__name__)

CHROMA_DIR = BACKEND_DIR / "data" / "chroma"
COLLECTION_NAME = "visual_assets"

# Cosine, not Chroma's default L2. The embeddings are unit-normalised, so cosine
# is the metric they were trained for and distance stops depending on text
# length.
_SPACE = "cosine"

# Chroma's own ceiling on a single add/upsert is generous, but batching keeps
# peak memory flat when the library grows past a few thousand assets.
_BATCH = 256

# Keyed by persist path: tests point CHROMA_DIR at a tmp dir, and each path owns
# its own client. Chroma itself refuses two live clients on one path.
_CLIENTS: Dict[str, Any] = {}
_COLLECTIONS: Dict[str, Any] = {}


def _chromadb() -> Any:
  """Indirection point so tests can simulate the dependency being absent."""
  import chromadb

  return chromadb


def _persist_dir() -> Path:
  # Read through the module constant on every call rather than caching it, so a
  # test (or a caller with its own index) can repoint CHROMA_DIR.
  return Path(CHROMA_DIR)


def _get_client() -> Any:
  path = _persist_dir()
  key = str(path)
  client = _CLIENTS.get(key)
  if client is not None:
    return client

  chromadb = _chromadb()
  path.mkdir(parents=True, exist_ok=True)
  from chromadb.config import Settings

  client = chromadb.PersistentClient(
      path=key,
      settings=Settings(anonymized_telemetry=False, allow_reset=True),
  )
  _CLIENTS[key] = client
  return client


def _get_collection() -> Any:
  key = str(_persist_dir())
  collection = _COLLECTIONS.get(key)
  if collection is not None:
    return collection

  client = _get_client()
  # embedding_function=None because we always hand Chroma vectors we computed
  # ourselves; left unset it would pull in its default ONNX MiniLM and quietly
  # embed with a different model than the index was built with.
  kwargs = {
      "name": COLLECTION_NAME,
      "metadata": {"hnsw:space": _SPACE},
      "embedding_function": None,
  }
  try:
    collection = client.get_or_create_collection(**kwargs)
  except (TypeError, ValueError):
    # Some chromadb releases reject an explicit None embedding_function.
    kwargs.pop("embedding_function")
    collection = client.get_or_create_collection(**kwargs)

  _COLLECTIONS[key] = collection
  return collection


def _forget(key: str) -> None:
  _COLLECTIONS.pop(key, None)


def upsert_assets(records: Sequence[AssetRecord]) -> int:
  """Index (or re-index) these assets. Returns how many were written.

  Upsert rather than add so `scripts/build_visual_index.py` is idempotent: the
  library is re-scanned whenever an asset is added, and re-running must refresh
  existing entries instead of erroring on duplicate ids or growing the index.
  """
  items = list(records)
  if not items:
    return 0

  collection = _get_collection()
  written = 0
  for start in range(0, len(items), _BATCH):
    chunk = items[start:start + _BATCH]
    documents = [r.embedding_text() for r in chunk]
    vectors = embeddings.embed_texts(documents)
    collection.upsert(
        ids=[r.asset_id for r in chunk],
        embeddings=[list(map(float, v)) for v in vectors],
        documents=documents,
        metadatas=[r.as_metadata() for r in chunk],
    )
    written += len(chunk)

  logger.info("indexed %d asset(s) into %s", written, _persist_dir())
  return written


def query(
    text: str,
    n_results: int = 5,
    category: Optional[str] = None,
) -> List[Tuple[AssetRecord, float]]:
  """Nearest assets to `text`, best first, as (record, similarity).

  `score` is a similarity in [0, 1], higher is better. Chroma returns a cosine
  *distance* (1 - cosine similarity, so 0 is identical and 2 is opposite); this
  converts with `score = 1 - distance` and clamps at 0. Clamping rather than
  rescaling by /2 keeps the number readable as "how alike are these": unrelated
  text lands near 0 instead of near 0.5, which is what a caller comparing this
  against a fuzzy-match ratio expects. Anti-correlated embeddings, which MiniLM
  effectively never produces for prose, all flatten to 0.

  `category` applies a Chroma metadata filter, for callers that already know the
  fact category a scene belongs to.
  """
  if not text or not text.strip() or n_results <= 0:
    return []

  try:
    collection = _get_collection()
    vector = embeddings.embed_query(text)
    result = collection.query(
        query_embeddings=[list(map(float, vector))],
        n_results=n_results,
        where={"category": category} if category else None,
        include=["metadatas", "distances"],
    )
  except Exception as exc:
    # A read failure means "no vector hits", not "stop the render".
    logger.warning("vector query failed (%s: %s)", type(exc).__name__, exc)
    return []

  metadatas = (result.get("metadatas") or [[]])[0] or []
  distances = (result.get("distances") or [[]])[0] or []

  hits: List[Tuple[AssetRecord, float]] = []
  for meta, distance in zip(metadatas, distances):
    if not meta:
      continue
    score = 1.0 - float(distance)
    hits.append((AssetRecord.from_metadata(dict(meta)), min(1.0, max(0.0, score))))

  # Chroma already returns nearest-first, but the clamp above can only preserve
  # that ordering, never create it -- sorting makes the contract explicit.
  hits.sort(key=lambda pair: pair[1], reverse=True)
  return hits


def count() -> int:
  """How many assets are indexed. 0 when the store cannot be opened."""
  try:
    return int(_get_collection().count())
  except Exception as exc:
    logger.warning("could not count the index (%s: %s)", type(exc).__name__, exc)
    return 0


def reset() -> None:
  """Drop the collection and recreate it empty.

  Used by `--reset` when the catalogue shrank: an upsert can refresh and add,
  but it can never remove an asset that was deleted from the library.
  """
  key = str(_persist_dir())
  client = _get_client()
  _forget(key)
  try:
    client.delete_collection(COLLECTION_NAME)
  except Exception:
    logger.debug("no existing collection to delete", exc_info=True)
  _get_collection()
  logger.info("collection %s reset at %s", COLLECTION_NAME, key)


def is_available() -> bool:
  """Whether the vector store can be used here -- never raises.

  False covers both "chromadb is not installed" and "the persist directory is
  there but unopenable", because the caller's response to either is the same:
  use fuzzy search instead.
  """
  try:
    _get_collection()
    return True
  except Exception as exc:
    logger.warning("vector store unavailable (%s: %s)", type(exc).__name__, exc)
    return False


def persist_dir() -> Path:
  """Where this process would read and write the index."""
  return _persist_dir()
