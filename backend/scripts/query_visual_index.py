"""Ask the visual retriever what it would pick for a line of narration.

    cd backend
    ../.venv/Scripts/python.exe scripts/query_visual_index.py "eligible farmer families"
    ../.venv/Scripts/python.exe scripts/query_visual_index.py --compare "deadline for e-KYC"

The point of --compare is that the two retrieval layers disagree, and the
finished video gives you no way to tell which one answered. Running both side
by side shows whether the vector index is actually earning its place over
plain fuzzy matching on your data -- if they agree on everything, the index is
not buying you much yet.

    --category   restrict to one FactCategory bucket
    --media      image | video
    -n           how many results
    --compare    run vector and fuzzy separately and show both rankings
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))


def _configure(verbose: bool) -> None:
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      try:
        stream.reconfigure(encoding="utf-8")
      except Exception:
        pass
  logging.basicConfig(
      level=logging.DEBUG if verbose else logging.WARNING,
      format="%(levelname)-7s %(name)-28s %(message)s",
      stream=sys.stderr,
  )


def _print_hits(title: str, hits) -> None:
  print(f"\n{title}")
  print("-" * len(title))
  if not hits:
    print("  (nothing above the confidence floor)")
    return
  for i, hit in enumerate(hits, 1):
    record = hit.record if hasattr(hit, "record") else hit[0]
    score = hit.score if hasattr(hit, "score") else hit[1]
    print(f"  {i}. {score:6.3f}  [{record.media_type:5}] {record.asset_id}")
    print(f"              category={record.category}  tags={', '.join(record.tags[:8]) or '-'}")


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("query", nargs="*", help="narration text to match against")
  parser.add_argument("--category", default=None)
  parser.add_argument("--media", default=None, choices=["image", "video"])
  parser.add_argument("-n", type=int, default=5)
  parser.add_argument("--compare", action="store_true", help="show vector and fuzzy rankings separately")
  parser.add_argument("-v", "--verbose", action="store_true")
  args = parser.parse_args()

  _configure(args.verbose)

  query = " ".join(args.query).strip()
  if not query:
    parser.error("give me some narration text to match")

  from services.visual_rag import retriever

  print(f"query    : {query!r}")
  print(f"backends : {retriever.describe_backends()}")

  if not args.compare:
    hits = retriever.retrieve(query, category=args.category, n_results=args.n, media_type=args.media)
    strategy = hits[0].strategy if hits else "none"
    _print_hits(f"result (strategy={strategy})", hits)
    return 0

  # Force each layer in turn so their rankings can be compared directly.
  from services.visual_rag import fuzzy

  saved = os.environ.get("VISUAL_RAG_DISABLE")
  try:
    os.environ.pop("VISUAL_RAG_DISABLE", None)
    vector_hits = retriever._try_vector(query, args.n, args.category)
  finally:
    if saved is not None:
      os.environ["VISUAL_RAG_DISABLE"] = saved

  _print_hits("vector (MiniLM + Chroma)", vector_hits)
  _print_hits("fuzzy (rapidfuzz over sidecar JSON)", fuzzy.search(
      query, n_results=args.n, category=args.category, min_score=0.0))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
