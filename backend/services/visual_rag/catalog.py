"""The asset catalogue every visual-selection strategy reads.

One record type shared by all three retrieval strategies -- vector search,
fuzzy metadata search, and the original tag scoring -- so they rank the same
things and a result from one is interchangeable with a result from another.

Assets live under assets/broll/library/<CATEGORY>/ as a media file beside a
.source.json sidecar carrying its provenance. Both stills and b-roll clips are
catalogued here: a scene needs the most relevant *visual*, and whether that
turns out to be a photograph or a few seconds of footage is a property of the
asset, not a different kind of search.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LIBRARY_DIR = BACKEND_DIR / "assets" / "broll" / "library"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv")


@dataclass(frozen=True)
class AssetRecord:
  """One catalogued visual, with everything any strategy needs to rank it."""

  asset_id: str
  path: Path
  media_type: str  # "image" | "video"
  category: str
  title: str
  tags: Tuple[str, ...] = ()
  domains: Tuple[str, ...] = ()
  description: str = ""
  licence: str = ""
  artist: str = ""
  source_page: str = ""
  width: int = 0
  height: int = 0
  duration_sec: float = 0.0

  def embedding_text(self) -> str:
    """The single string that represents this asset to a text matcher.

    Everything a scene might plausibly say lives here -- the human title, the
    curated tags, the domain, the category, and any description -- because a
    scene line like "eligible farmer families in rural districts" has to be
    matchable against an asset whose title only says "Agriculture land near
    Palayam". Category is included in words rather than as a filter so that a
    semantically close asset in a neighbouring category can still surface.
    """
    parts = [
        self.title,
        self.description,
        " ".join(self.tags),
        " ".join(self.domains),
        self.category.replace("_", " ").lower(),
    ]
    return " . ".join(p.strip() for p in parts if p and p.strip())

  def as_metadata(self) -> Dict[str, str]:
    """Flat, JSON-scalar metadata. Chroma rejects lists and nested objects,
    so sequences are joined rather than stored as-is."""
    return {
        "asset_id": self.asset_id,
        "path": str(self.path),
        "media_type": self.media_type,
        "category": self.category,
        "title": self.title,
        "tags": ",".join(self.tags),
        "domains": ",".join(self.domains),
        "licence": self.licence,
        "artist": self.artist,
        "source_page": self.source_page,
        "width": str(self.width),
        "height": str(self.height),
        "duration_sec": f"{self.duration_sec:.3f}",
    }

  @classmethod
  def from_metadata(cls, meta: Dict[str, str]) -> "AssetRecord":
    def _split(key: str) -> Tuple[str, ...]:
      raw = meta.get(key) or ""
      return tuple(p for p in (s.strip() for s in raw.split(",")) if p)

    return cls(
        asset_id=meta.get("asset_id", ""),
        path=Path(meta.get("path", "")),
        media_type=meta.get("media_type", "image"),
        category=meta.get("category", ""),
        title=meta.get("title", ""),
        tags=_split("tags"),
        domains=_split("domains"),
        licence=meta.get("licence", ""),
        artist=meta.get("artist", ""),
        source_page=meta.get("source_page", ""),
        width=int(meta.get("width") or 0),
        height=int(meta.get("height") or 0),
        duration_sec=float(meta.get("duration_sec") or 0.0),
    )


def _media_type(path: Path) -> Optional[str]:
  suffix = path.suffix.lower()
  if suffix in IMAGE_EXTENSIONS:
    return "image"
  if suffix in VIDEO_EXTENSIONS:
    return "video"
  return None


def _record_from_sidecar(media_path: Path, sidecar: Path, category: str) -> Optional[AssetRecord]:
  try:
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    logger.warning("unreadable sidecar %s; skipping", sidecar.name)
    return None

  media_type = _media_type(media_path)
  if media_type is None:
    return None

  # commons_title is the historical field name; title is what newer sidecars
  # (and hand-written ones) use. Accept either rather than forcing a migration
  # of files already on disk.
  title = meta.get("title") or meta.get("commons_title") or media_path.stem
  title = str(title).removeprefix("File:").replace("_", " ")

  return AssetRecord(
      asset_id=f"{category}/{media_path.stem}",
      path=media_path,
      media_type=media_type,
      category=meta.get("category", category),
      title=title,
      tags=tuple(str(t).lower() for t in meta.get("tags", []) if isinstance(t, str)),
      domains=tuple(str(d).lower() for d in meta.get("domains", []) if isinstance(d, str)),
      description=str(meta.get("description", "")),
      licence=str(meta.get("licence", "")),
      artist=str(meta.get("artist", "")),
      source_page=str(meta.get("source_page", "")),
      width=int(meta.get("width") or 0),
      height=int(meta.get("height") or 0),
      duration_sec=float(meta.get("duration_sec") or 0.0),
  )


def scan_library(library_dir: Optional[Path] = None) -> List[AssetRecord]:
  """Every catalogued asset on disk. Uncached; callers that read repeatedly
  should use `load_catalog`."""
  root = Path(library_dir) if library_dir else LIBRARY_DIR
  if not root.is_dir():
    logger.warning("asset library not found at %s", root)
    return []

  records: List[AssetRecord] = []
  for category_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    for media_path in sorted(category_dir.iterdir()):
      if media_path.name.endswith(".source.json"):
        continue
      if _media_type(media_path) is None:
        continue
      sidecar = media_path.with_suffix(".source.json")
      if not sidecar.is_file():
        logger.warning("%s has no .source.json sidecar; skipping", media_path.name)
        continue
      record = _record_from_sidecar(media_path, sidecar, category_dir.name)
      if record is not None:
        records.append(record)

  logger.info("asset catalogue: %d records under %s", len(records), root)
  return records


@lru_cache(maxsize=4)
def _load_cached(root: str) -> Tuple[AssetRecord, ...]:
  return tuple(scan_library(Path(root)))


def load_catalog(library_dir: Optional[Path] = None) -> Tuple[AssetRecord, ...]:
  """Cached catalogue. The library is seeded offline and not written to during
  a render, so re-scanning per scene would be wasted work."""
  root = str(Path(library_dir) if library_dir else LIBRARY_DIR)
  return _load_cached(root)


def reload_catalog() -> None:
  """Drop the cache after the build script adds assets to a running process."""
  _load_cached.cache_clear()
