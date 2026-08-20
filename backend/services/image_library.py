"""Select a background still from the local Commons image library.

Pure local disk lookup — no network call, no API key, no quota. Replaces the
Google Programmable Search path (image_fetcher.py) for the demo: that needed
a Cloud Console project with an API properly enabled, which turned into a
setup fight not worth having mid-sprint. This has no such dependency: the
library is seeded once by scripts/build_image_library.py from Wikimedia
Commons, and selection at render time is just picking a file.

Per §10.2, a scene must never fail for want of an asset. A category with zero
images is the normal state for whichever categories weren't seeded (or fully
reviewed and pruned) — select_image returns None and the caller keeps
whatever asset it already had, exactly like the image_fetcher.py path did.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = BACKEND_ROOT / "assets" / "broll" / "library"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


@dataclass(frozen=True)
class LibraryImage:
  path: Path
  category: str
  commons_title: str
  licence: str
  artist: str
  source_page: str
  tags: Tuple[str, ...] = ()


@lru_cache(maxsize=1)
def _load_index() -> Tuple[LibraryImage, ...]:
  """Every image with a readable sidecar, across all categories.

  Cached for the process lifetime: the library is seeded once, offline,
  before a server starts, not written to during a render.
  """
  if not LIBRARY_DIR.is_dir():
    return ()

  images: List[LibraryImage] = []
  for category_dir in sorted(LIBRARY_DIR.iterdir()):
    if not category_dir.is_dir():
      continue
    for img_path in sorted(category_dir.iterdir()):
      if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
        continue
      sidecar = img_path.with_suffix(".source.json")
      if not sidecar.is_file():
        logger.warning("library image %s has no .source.json sidecar; skipping", img_path.name)
        continue
      try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
      except json.JSONDecodeError:
        logger.warning("malformed sidecar %s; skipping", sidecar.name)
        continue
      images.append(LibraryImage(
          path=img_path,
          category=meta.get("category", category_dir.name),
          commons_title=meta.get("commons_title", ""),
          licence=meta.get("licence", ""),
          artist=meta.get("artist", ""),
          source_page=meta.get("source_page", ""),
          tags=tuple(str(t) for t in meta.get("tags", []) if isinstance(t, str)),
      ))
  logger.info("image library: %d images loaded from %s", len(images), LIBRARY_DIR)
  return tuple(images)


def reload_index() -> None:
  """Drop the cache. Call after build_image_library.py adds files to a
  process that is already running (tests; a long-lived dev server)."""
  _load_index.cache_clear()


def available_categories() -> Tuple[str, ...]:
  return tuple(sorted({img.category for img in _load_index()}))


def _best_scoring(candidates: Tuple[LibraryImage, ...], scene_text: str) -> List[LibraryImage]:
  """Candidates scoring highest against `scene_text`, or all of them if
  nothing scored above zero (empty text, or no tag matched anything)."""
  if not scene_text:
    return list(candidates)
  search_corpus = scene_text.lower()
  scores = [sum(2 for tag in img.tags if tag in search_corpus) for img in candidates]
  best_score = max(scores)
  if best_score == 0:
    return list(candidates)
  return [img for img, score in zip(candidates, scores) if score == best_score]


def _pick_deterministic(pool: List[LibraryImage], salt: str, seed: str) -> LibraryImage:
  """Stable hash pick, never random — so a demo does not visibly reshuffle
  its own backgrounds between identical re-renders."""
  digest = hashlib.sha256(f"{salt}|{seed}".encode("utf-8")).digest()
  return pool[int.from_bytes(digest[:4], "big") % len(pool)]


def select_image(category: str, scene_text: str = "", seed: str = "") -> Optional[LibraryImage]:
  """The image for `category`, or None if that category has nothing.

  `scene_text` is the scene's actual fact text (or however much of it the
  caller has), used to steer which of several images in a category gets
  used: a scene mentioning "verification" should prefer an image tagged
  "verification" over a generically-tagged one in the same category, rather
  than an arbitrary pick that ignores what the scene is actually about.
  Scoring mirrors match_visual_asset in asset_matcher.py — +2 per tag that
  appears as a substring of the lowercased scene text — so the two stay
  consistent if either is tuned later.

  Ties (including the "no scene_text" and "nothing matched" cases, which are
  a tie across the full candidate pool at score 0) are broken by a stable
  hash of (category, seed) rather than randomly. Pass a per-job or per-scene
  seed (e.g. the scene_id) to vary the pick across scenes that share a
  category.
  """
  candidates = tuple(img for img in _load_index() if img.category == category)
  if not candidates:
    return None
  pool = _best_scoring(candidates, scene_text)
  return _pick_deterministic(pool, category, seed)


def select_generic_image(scene_text: str = "", seed: str = "") -> Optional[LibraryImage]:
  """Any image in the library, regardless of category — the floor beneath
  the procedural gradient.

  A government-notice video that always shows a real photograph reads as a
  finished broadcast; one that drops to a flat gradient whenever a scene's
  specific category (AMOUNT, DEADLINE, ...) has not been seeded yet reads as
  an unfinished one, even though the gradient exists for exactly that
  situation and is a deliberate, tested fallback (README §10.2). So this
  sits between select_image and the gradient in the fallback order: try the
  fact-relevant category first, then any image at all, then the gradient
  only if the library is completely empty.

  Still scored against `scene_text` where it can be, so "any image" does not
  mean "an obviously wrong one" if something in the library happens to match
  regardless of which category it was filed under.
  """
  candidates = _load_index()
  if not candidates:
    return None
  pool = _best_scoring(candidates, scene_text)
  return _pick_deterministic(pool, "__generic__", seed)
