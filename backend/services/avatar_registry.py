"""Resolves a pre-baked presenter clip for a job's target language.

Everything is local disk: a JSON manifest plus MP4 loops under
`assets/avatars/`. No network calls, no API keys, no per-render inference.
Adding a presenter means dropping an MP4 in and adding a manifest entry —
no code change.

Disclosure is not optional. Every Avatar carries a `disclosure_label` that
the compositor renders on screen whenever the presenter is shown. A
photorealistic presenter delivering government scheme information is
misleading unless the viewer can tell it is synthetic, and README section 21
already requires computer-narrated output to be labelled. The label is a
required manifest field with no default precisely so it cannot be forgotten.

The registry is also allowed to resolve nothing. With no avatars installed
`resolve()` returns None and the compositor renders its normal full-width
layout, so the pipeline works unchanged before any presenter exists.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

AVATARS_DIR = Path(__file__).resolve().parent.parent / "assets" / "avatars"
MANIFEST_PATH = AVATARS_DIR / "manifest.json"

# A real official's likeness must never be animated — that is a deepfake of a
# named public figure in their official capacity, which no disclosure label
# makes acceptable. Manifest entries must declare one of these origins.
ALLOWED_SOURCES = ("synthetic", "licensed_stock", "consented_performer")


class AvatarManifestError(Exception):
    """The manifest is malformed, or an entry violates a hard requirement."""


@dataclass(frozen=True)
class Avatar:
    avatar_id: str
    file_path: Path
    languages: Tuple[str, ...]
    display_name: str
    source: str
    licence: str
    disclosure_label: str

    @property
    def exists(self) -> bool:
        return self.file_path.is_file()


def _parse_entry(raw: Dict, avatars_dir: Path) -> Avatar:
    missing = [
        k for k in ("avatar_id", "file", "languages", "source", "licence", "disclosure_label")
        if not raw.get(k)
    ]
    if missing:
        raise AvatarManifestError(
            f"avatar entry {raw.get('avatar_id', '<unnamed>')!r} is missing required field(s): {', '.join(missing)}"
        )

    source = raw["source"]
    if source not in ALLOWED_SOURCES:
        raise AvatarManifestError(
            f"avatar {raw['avatar_id']!r} declares source={source!r}; must be one of {ALLOWED_SOURCES}. "
            "Animating a real, identifiable person's likeness is not permitted."
        )

    return Avatar(
        avatar_id=raw["avatar_id"],
        file_path=avatars_dir / raw["file"],
        languages=tuple(raw["languages"]),
        display_name=raw.get("display_name", raw["avatar_id"]),
        source=source,
        licence=raw["licence"],
        disclosure_label=raw["disclosure_label"],
    )


@lru_cache(maxsize=4)
def load_registry(manifest_path: Optional[str] = None) -> Tuple[Avatar, ...]:
    """Read the manifest. Returns an empty tuple when none is installed."""
    path = Path(manifest_path) if manifest_path else MANIFEST_PATH
    if not path.is_file():
        logger.info("No avatar manifest at %s; presenter layout disabled", path)
        return ()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AvatarManifestError(f"{path} is not valid JSON: {exc}") from exc

    entries: List[Avatar] = [_parse_entry(raw, path.parent) for raw in data.get("avatars", [])]

    present = []
    for avatar in entries:
        if avatar.exists:
            present.append(avatar)
        else:
            # A manifest entry whose MP4 is absent is a packaging mistake, not
            # a reason to fail the render — fall back to the normal layout.
            logger.warning(
                "avatar %r listed in manifest but %s is missing; skipping",
                avatar.avatar_id, avatar.file_path,
            )
    return tuple(present)


def resolve(lang: str, manifest_path: Optional[str] = None) -> Optional[Avatar]:
    """Best presenter for `lang`, or None if there isn't one.

    Exact language match wins; otherwise an avatar declaring "*" acts as a
    catch-all. Returning None is a normal outcome, not an error.
    """
    registry = load_registry(manifest_path)
    if not registry:
        return None

    for avatar in registry:
        if lang in avatar.languages:
            return avatar
    for avatar in registry:
        if "*" in avatar.languages:
            logger.info("no avatar for lang=%s; using catch-all %r", lang, avatar.avatar_id)
            return avatar

    logger.info("no avatar matches lang=%s", lang)
    return None


def available_languages(manifest_path: Optional[str] = None) -> Tuple[str, ...]:
    seen = []
    for avatar in load_registry(manifest_path):
        for lang in avatar.languages:
            if lang not in seen:
                seen.append(lang)
    return tuple(seen)
