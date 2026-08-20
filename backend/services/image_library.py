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
      ))
  logger.info("image library: %d images loaded from %s", len(images), LIBRARY_DIR)
  return tuple(images)


def reload_index() -> None:
  """Drop the cache. Call after build_image_library.py adds files to a
  process that is already running (tests; a long-lived dev server)."""
  _load_index.cache_clear()


def available_categories() -> Tuple[str, ...]:
  return tuple(sorted({img.category for img in _load_index()}))


def select_image(category: str, seed: str = "") -> Optional[LibraryImage]:
  """The image for `category`, or None if that category has nothing.

  Selection is a stable hash of (category, seed) rather than random, so the
  same scene gets the same image across repeated renders — a demo should not
  visibly reshuffle its own backgrounds between takes. Pass a per-job or
  per-scene seed (e.g. the scene_id) to vary the pick across scenes that
  share a category.
  """
  candidates = [img for img in _load_index() if img.category == category]
  if not candidates:
    return None
  digest = hashlib.sha256(f"{category}|{seed}".encode("utf-8")).digest()
  index = int.from_bytes(digest[:4], "big") % len(candidates)
  return candidates[index]
