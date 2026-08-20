"""Scan the asset library and (re)build the vector index.

    cd backend
    ../.venv/Scripts/python.exe scripts/build_visual_index.py

Run this after adding anything to assets/broll/library/. It is safe to re-run:
entries are upserted by asset id, so an existing asset is refreshed rather than
duplicated. Use --reset when assets have been *deleted*, which an upsert cannot
express.

    --library    library root to scan (default: the catalogue's LIBRARY_DIR)
    --reset      drop the collection first
    --dry-run    scan and print what would be indexed; embed nothing
    -v           per-asset detail
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

TEXT_PREVIEW = 96


def _configure_logging(verbose: bool) -> None:
  # Asset titles come from Commons and carry accents and Devanagari; a cp1252
  # console -- the Windows default -- raises UnicodeEncodeError on the first one
  # and kills the whole indexing run.
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      try:
        stream.reconfigure(encoding="utf-8")
      except Exception:
        pass

  logging.basicConfig(
      level=logging.DEBUG if verbose else logging.INFO,
      format="%(asctime)s  %(levelname)-7s %(name)-28s %(message)s",
      datefmt="%H:%M:%S",
      stream=sys.stdout,
  )
  for noisy in ("urllib3", "httpx", "chromadb", "sentence_transformers", "filelock", "PIL"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _truncate(text: str, limit: int = TEXT_PREVIEW) -> str:
  flat = " ".join(text.split())
  return flat if len(flat) <= limit else flat[:limit - 1] + "…"


def main() -> int:
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
  )
  parser.add_argument("--library", default=None, help="library root to scan")
  parser.add_argument("--reset", action="store_true", help="drop the collection before indexing")
  parser.add_argument("--dry-run", action="store_true", help="scan and print only; embed nothing")
  parser.add_argument("-v", "--verbose", action="store_true")
  args = parser.parse_args()

  _configure_logging(args.verbose)
  log = logging.getLogger("visual_rag.build")

  from services.visual_rag import embeddings, store
  from services.visual_rag.catalog import LIBRARY_DIR, scan_library

  library = Path(args.library) if args.library else LIBRARY_DIR
  if not library.is_dir():
    log.error("library not found: %s", library)
    return 2

  started = time.perf_counter()
  records = scan_library(library)
  scanned = len(records)
  log.info("scanned %d asset(s) under %s", scanned, library)

  for record in records:
    log.info(
        "  %-52s %-5s %-16s %s",
        record.asset_id,
        record.media_type,
        record.category,
        _truncate(record.embedding_text()),
    )

  if args.dry_run:
    elapsed = time.perf_counter() - started
    log.info("")
    log.info("=" * 72)
    log.info("[DRY RUN] nothing was embedded or written")
    log.info("  scanned      : %d", scanned)
    log.info("  would index  : %d", scanned)
    log.info("  elapsed      : %.2fs", elapsed)
    log.info("  persist dir  : %s", store.persist_dir())
    return 0

  # Checked before any work: an unavailable model or store is a setup problem
  # the operator has to fix, not something to half-succeed through.
  if not embeddings.is_available():
    log.error(
        "embedding model unavailable -- cannot build the index. Install "
        "sentence-transformers and make sure '%s' can be downloaded or is "
        "already cached.",
        embeddings.MODEL_NAME,
    )
    return 1

  if not store.is_available():
    log.error(
        "vector store unavailable -- cannot build the index. Install chromadb "
        "and make sure %s is writable.",
        store.persist_dir(),
    )
    return 1

  if args.reset:
    store.reset()
    log.info("collection dropped and recreated")

  if not records:
    log.warning("no assets found; the index was left with %d entr(ies)", store.count())
    return 0

  try:
    indexed = store.upsert_assets(records)
  except Exception:
    log.exception("indexing failed")
    return 1

  elapsed = time.perf_counter() - started
  skipped = scanned - indexed

  log.info("")
  log.info("=" * 72)
  log.info("[DONE] visual index built")
  log.info("  scanned      : %d", scanned)
  log.info("  indexed      : %d", indexed)
  log.info("  skipped      : %d", skipped)
  log.info("  in collection: %d", store.count())
  log.info("  elapsed      : %.2fs", elapsed)
  log.info("  persist dir  : %s", store.persist_dir())
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
