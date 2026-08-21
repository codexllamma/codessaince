"""One-time seed of a local, offline background-image library from Wikimedia
Commons — no API key, no quota, no per-render network call.

    python scripts/build_image_library.py
    python scripts/build_image_library.py --per-category 10
    python scripts/build_image_library.py --contact-sheet-only

This replaces the Google Programmable Search path for the demo: that needs a
Cloud Console project with Custom Search JSON API enabled, which turned out
to be a per-session setup fight not worth having during a sprint. Commons
needs no key at all and every file already carries a machine-readable licence,
which the pipeline's provenance story (an officer approval gate) actually
wants more than a search API's loose "rights" filter did.

Downloads go to assets/broll/library/<FACT_CATEGORY>/, each image beside a
`.source.json` sidecar recording the query, the Commons page, the licence and
the declared author — the same provenance pattern image_fetcher.py used, kept
here because an officer can only vet a picture if they can see where it came
from. services/image_library.py reads this tree at render time and never
touches the network.

What this script cannot check: whether a photo shows an identifiable face or
a branded logo, which README §10.3 rules out. Curated Commons categories are
far cleaner than free-text search, but they are not guaranteed clean — this
writes a contact sheet at the end specifically so a person looks before any
of this reaches a render anyone sees.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
  sys.path.insert(0, str(BACKEND_ROOT))

LIBRARY_DIR = BACKEND_ROOT / "assets" / "broll" / "library"
API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia asks every API client to identify itself; unlike the Google key
# flow this needs no registration, just an honest string.
USER_AGENT = "IndicGov-Sentinel-Hackathon/1.0 (local demo asset library, non-commercial student project)"

# The compositor upscales a too-small still rather than failing the scene
# (compositor/layers.py: "upscaling past native resolution is exactly what
# §8.6 forbids, but a slightly soft background beats failing the scene"), so
# this only needs to keep out the genuinely tiny — thumbnails, icons wrongly
# categorised as photos — not enforce the full 2150x1210 Ken Burns headroom.
MIN_WIDTH = 1200
MIN_HEIGHT = 800
DEFAULT_PER_CATEGORY = 7
MAX_BYTES = 15 * 1024 * 1024

# Curated Commons categories per fact category, picked by hand after checking
# each returns real photographs rather than diagrams or archival scans (see
# the category-namespace search used to find these). Several categories per
# fact category so a bad/empty one does not starve the pool.
SOURCE_CATEGORIES: Dict[str, List[str]] = {
    "SCHEME_NAME": [
        "Category:Agriculture in India",
        "Category:Male farmers in India",
        "Category:Female farmers in India",
    ],
    "AMOUNT": [
        "Category:Banknotes of India",
        "Category:Coins of India",
        "Category:Indian rupee banknotes",
    ],
    "DEADLINE": [
        "Category:Clocks",
        "Category:Wall clocks",
        "Category:Hourglasses",
    ],
    "ELIGIBILITY": [
        "Category:Villages in India",
        "Category:Agriculture in India",
    ],
    "BENEFICIARY": [
        "Category:Male farmers in India",
        "Category:Female farmers in India",
    ],
    "AUTHORITY": [
        "Category:Secretariat Building, New Delhi",
        "Category:Kerala Government Secretariat",
        "Category:Secretariat Building (Chandigarh)",
        "Category:New Secretariat Building, Kolkata",
        "Category:Reserve Bank of India, Mumbai",
    ],
    "ACTION_REQUIRED": [
        "Category:National Payments Corporation of India",
        "Category:Digital Rupee",
        "Category:People with smartphones in India",
    ],
}

# Baseline keyword tags per fact category, used to seed each sidecar's "tags"
# list so a downstream selector can score images by keyword relevance against
# scene text rather than only bucketing by category folder.
CATEGORY_BASE_TAGS: Dict[str, List[str]] = {
    "SCHEME_NAME": ["scheme", "yojana", "agriculture", "farmer", "farmers", "crop", "wheat", "rural", "kisan"],
    "AMOUNT": ["amount", "rupee", "rupees", "money", "payment", "currency", "bank", "cash", "rs", "inr"],
    "DEADLINE": ["deadline", "date", "clock", "calendar", "cutoff", "last", "before", "time"],
    "ELIGIBILITY": ["eligibility", "village", "rural", "household", "family", "villages"],
    "BENEFICIARY": ["beneficiary", "beneficiaries", "farmer", "farmers", "people", "worker", "workers"],
    "AUTHORITY": ["ministry", "government", "authority", "official", "secretariat", "building", "govt"],
    "ACTION_REQUIRED": ["verification", "kyc", "update", "action", "portal", "digital", "payment", "app", "helpdesk"],
}

# Titles containing these are almost never the photograph the category name
# suggests — logos, flags, diagrams, coats of arms, scanned documents.
TITLE_EXCLUDE = re.compile(
    r"\b(logo|flag|map|icon|diagram|screenshot|poster|stamp|seal|emblem|"
    r"coat of arms|chart|graph|banner|watermark|specimen|proof)\b",
    re.IGNORECASE,
)
EXCLUDE_EXTENSIONS = {".svg", ".pdf", ".gif", ".tif", ".tiff", ".webp"}

# LicenseShortName strings accepted as permissive enough to use. CC BY and
# CC BY-SA need attribution, which is why the sidecar always records the
# artist string rather than only the ones that legally require it.
# GODL-India (Government Open Data License – India) covers a lot of RBI and
# other Government-of-India-published photography on Commons and is at least
# as permissive as CC BY for this use — dropping it just meant losing exactly
# the currency and government-building photos this project wants most.
ACCEPTED_LICENCE_PREFIXES = ("public domain", "cc0", "cc-by", "cc by", "pdm", "godl")


# Commons file extensions that are video rather than stills. Commons hosts
# almost no MP4 (it is patent-encumbered); WebM and Ogg Theora are what is
# actually there, and the compositor reads both through MoviePy/ffmpeg.
VIDEO_EXTENSIONS = {".webm", ".ogv", ".ogg", ".mp4", ".mov"}

# A background clip has to outlast a scene without an obvious loop, and a
# scene runs roughly 6-12s. Anything shorter loops visibly; anything longer is
# a documentary whose download cost buys a few usable seconds.
MIN_VIDEO_SEC = 4.0
MAX_VIDEO_SEC = 180.0
MAX_VIDEO_BYTES = 40 * 1024 * 1024

# Which of the twelve domains in assets/broll/ASSET_PLAN.md each fact category
# belongs to. Domains are a coarser grouping than the fact category and are
# what a scene's narration actually sounds like -- a line about "eligible
# farmer families" is agriculture vocabulary regardless of whether the asset
# was filed under ELIGIBILITY or BENEFICIARY -- so they widen retrieval
# without loosening the category filter.
# Commons video categories per fact category. Kept separate from
# SOURCE_CATEGORIES because Commons files video under its own tree -- the
# image categories contain essentially no clips, so pointing --media video at
# them returns nothing.
#
# Each entry below was probed and returned candidates that pass the filters;
# categories that came back empty ("Videos of farming", "Videos of money",
# "Videos of schools") are deliberately not listed rather than left in as
# hopeful guesses.
#
# WARNING, from an actual run: what these return is categorically right and
# contextually useless -- US bank-lobby CCTV for AMOUNT, an ornate Viennese
# museum clock for DEADLINE, aerial flood-disaster footage for SCHEME_NAME.
# All were pruned; the flood clip is worse than nothing behind a scheme
# announcement. Commons has very little video and almost none of it in an
# Indian government context, so source motion backgrounds from licensed stock
# instead and hand-write the sidecar. This map is kept because the code path
# is correct and works the moment it is pointed somewhere better.
# See assets/broll/README.md.
VIDEO_SOURCE_CATEGORIES: Dict[str, List[str]] = {
    "AUTHORITY": ["Category:Videos from India"],
    "SCHEME_NAME": ["Category:Videos of roads", "Category:Videos from India"],
    "AMOUNT": ["Category:Videos of banks"],
    "DEADLINE": ["Category:Videos of clocks"],
    "ACTION_REQUIRED": ["Category:Videos of banks", "Category:Videos of hospitals"],
    "ELIGIBILITY": ["Category:Videos of agriculture", "Category:Videos of villages"],
    "BENEFICIARY": ["Category:Videos of villages", "Category:Videos of agriculture"],
}

CATEGORY_DOMAINS: Dict[str, List[str]] = {
    "AUTHORITY": ["governance"],
    "SCHEME_NAME": ["governance", "rural_development"],
    "AMOUNT": ["banking_dbt"],
    "DEADLINE": ["compliance_deadline", "identity_kyc"],
    "ACTION_REQUIRED": ["identity_kyc", "compliance_deadline"],
    "ELIGIBILITY": ["agriculture", "rural_development"],
    "BENEFICIARY": ["rural_development", "women_child"],
}


@dataclass
class Candidate:
  title: str
  url: str
  page: str
  width: int
  height: int
  mime: str
  licence: str
  artist: str
  description: str = ""
  duration: float = 0.0

  @property
  def is_video(self) -> bool:
    return Path(self.title).suffix.lower() in VIDEO_EXTENSIONS


def _get_json(params: dict, attempts: int = 3, backoff: float = 1.5) -> Optional[dict]:
  """GET with retry. Commons occasionally returns an empty body under load;
  this is far more often transient than a real failure, so it is retried
  before being treated as one."""
  import requests

  for attempt in range(attempts):
    try:
      r = requests.get(API, headers={"User-Agent": USER_AGENT}, params=params, timeout=20)
      if r.ok and r.text.strip():
        return r.json()
    except Exception:
      pass
    if attempt < attempts - 1:
      time.sleep(backoff * (attempt + 1))
  return None


def _strip_html(text: str) -> str:
  return re.sub(r"<[^>]+>", "", text or "").strip()


def _clean_description(raw: str, title: str) -> str:
  """Commons ImageDescription, reduced to one usable sentence.

  This is the field retrieval cares about most: it is the only metadata
  written in prose rather than keywords, so it is the only part phrased the
  way a narration line is phrased. Uploader descriptions are wildly
  inconsistent though -- HTML, multilingual blocks, camera settings, whole
  paragraphs of provenance -- so take the first sentence or two and drop the
  rest rather than embedding boilerplate that dilutes the vector.
  """
  text = _strip_html(raw or "").strip()
  if not text:
    return ""
  # Multilingual descriptions arrive as concatenated language blocks; the
  # English one is first often enough that truncating beats parsing them.
  text = re.sub(r"\s+", " ", text)
  sentences = re.split(r"(?<=[.!?])\s+", text)
  out = " ".join(sentences[:2]).strip()
  if len(out) > 300:
    out = out[:297].rsplit(" ", 1)[0] + "..."
  # A description that only restates the filename teaches retrieval nothing.
  if _slug(out) == _slug(Path(title).stem):
    return ""
  return out


def fetch_category_members(category: str, limit: int = 20, media: str = "image") -> List[Candidate]:
  """Photographs in a Commons category, with size and licence already resolved.

  One call gets both membership and imageinfo via a generator, which is why
  this is cheaper than the search-then-lookup pattern image_fetcher.py used
  for the (abandoned) Google path.
  """
  data = _get_json({
      "action": "query",
      "generator": "categorymembers",
      "gcmtitle": category,
      "gcmtype": "file",
      "gcmlimit": limit,
      "prop": "imageinfo",
      "iiprop": "url|size|mime|extmetadata",
      "format": "json",
  })
  if not data:
    print(f"    (no response for {category}; skipping)")
    return []

  out: List[Candidate] = []
  for page in (data.get("query", {}).get("pages", {}) or {}).values():
    title = page.get("title", "")
    if TITLE_EXCLUDE.search(title):
      continue
    suffix = Path(title).suffix.lower()
    if suffix in EXCLUDE_EXTENSIONS:
      continue

    is_video = suffix in VIDEO_EXTENSIONS
    if media == "image" and is_video:
      continue
    if media == "video" and not is_video:
      continue

    infos = page.get("imageinfo") or []
    if not infos:
      continue
    info = infos[0]
    width, height = info.get("width", 0), info.get("height", 0)
    # A clip is judged on whether it fills the panel, not on stills-grade
    # sharpness: 720p footage upscales acceptably where a 720p photo would
    # not, because motion hides softness.
    min_w, min_h = (960, 540) if is_video else (MIN_WIDTH, MIN_HEIGHT)
    if width < min_w or height < min_h:
      continue

    duration = float(info.get("duration") or 0.0)
    if is_video and not (MIN_VIDEO_SEC <= duration <= MAX_VIDEO_SEC):
      # Too short to survive a scene, or a full documentary that would cost
      # a long download for a few usable seconds.
      continue

    meta = info.get("extmetadata", {}) or {}
    licence = (meta.get("LicenseShortName", {}) or {}).get("value", "")
    if not licence.lower().startswith(ACCEPTED_LICENCE_PREFIXES):
      continue

    artist = _strip_html((meta.get("Artist", {}) or {}).get("value", "")) or "Unknown (see source page)"
    description = _clean_description(
        (meta.get("ImageDescription", {}) or {}).get("value", ""), title
    )

    out.append(Candidate(
        title=title, url=info["url"], page=info.get("descriptionurl", ""),
        width=width, height=height, mime=info.get("mime", ""),
        licence=licence, artist=artist,
        description=description, duration=duration,
    ))
  return out


def _slug(text: str) -> str:
  return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:56] or "image"


_TITLE_TAG_STOPWORDS = {
    "the", "and", "of", "in", "for", "with", "from", "file", "jpg", "jpeg",
    "png", "photo", "image", "picture",
}


def extract_title_tags(title: str) -> list[str]:
  """Keyword tags derived from a Commons file title, e.g.
  "File:Farmer_in_wheat_field.jpg" -> ["farmer", "wheat", "field"].
  """
  stem = title
  if stem.lower().startswith("file:"):
    stem = stem[len("file:"):]
  stem = Path(stem).stem
  tokens = re.split(r"[^a-z0-9]+", stem.lower())

  tags: list[str] = []
  seen = set()
  for tok in tokens:
    if len(tok) <= 2 or tok in _TITLE_TAG_STOPWORDS or tok in seen:
      continue
    seen.add(tok)
    tags.append(tok)
  return tags


def _download_body(url: str, attempts: int = 4, max_bytes: int = MAX_BYTES) -> Optional[bytes]:
  """GET the raw bytes with retry/backoff. upload.wikimedia.org is a
  separate endpoint from the API and rate-limits independently — a burst of
  downloads (this script, or a prior debugging session against the same IP)
  trips 429 here even when the API queries above are all fine."""
  import requests

  for attempt in range(attempts):
    try:
      with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, stream=True) as r:
        if r.status_code == 429:
          wait = float(r.headers.get("Retry-After", 2 * (attempt + 1)))
          time.sleep(min(wait, 20))
          continue
        if not r.ok:
          return None
        body = b""
        for chunk in r.iter_content(64 * 1024):
          body += chunk
          if len(body) > max_bytes:
            return None
        return body
    except Exception:
      time.sleep(1.5 * (attempt + 1))
  return None


def _write_sidecar(out_path: Path, c: Candidate, category: str) -> None:
  tags = list(dict.fromkeys(CATEGORY_BASE_TAGS.get(category, []) + extract_title_tags(c.title)))
  out_path.with_suffix(".source.json").write_text(
      json.dumps({
          "category": category,
          "commons_title": c.title,
          "description": c.description,
          "domains": CATEGORY_DOMAINS.get(category, []),
          "media_type": "video" if c.is_video else "image",
          "image_url": c.url,
          "source_page": c.page,
          "licence": c.licence,
          "artist": c.artist,
          "width": c.width,
          "height": c.height,
          "duration_sec": round(c.duration, 3),
          "tags": tags,
      }, indent=2, ensure_ascii=False),
      encoding="utf-8",
  )


def download_video_candidate(c: Candidate, category: str, out_dir: Path) -> Optional[Path]:
  """Save a Commons clip as-is, without transcoding.

  The compositor already decodes whatever ffmpeg can read, so re-encoding
  here would cost a generation of quality to solve a problem nothing has.
  """
  body = _download_body(c.url, max_bytes=MAX_VIDEO_BYTES)
  if body is None:
    return None

  ext = Path(c.title).suffix.lower() or ".webm"
  out_path = out_dir / f"{_slug(Path(c.title).stem)}{ext}"
  try:
    out_path.write_bytes(body)
  except OSError as exc:
    safe_title = c.title[:60].encode("ascii", "replace").decode("ascii")
    print(f"    ! {safe_title}: {exc}")
    return None

  _write_sidecar(out_path, c, category)
  return out_path


def download_candidate(c: Candidate, category: str, out_dir: Path) -> Optional[Path]:
  if c.is_video:
    return download_video_candidate(c, category, out_dir)

  from PIL import Image

  body = _download_body(c.url)
  if body is None:
    return None

  try:
    from io import BytesIO
    with Image.open(BytesIO(body)) as img:
      img.load()
      ext = ".jpg" if img.mode != "RGBA" else ".png"
      out_path = out_dir / f"{_slug(Path(c.title).stem)}{ext}"
      if ext == ".jpg":
        img.convert("RGB").save(out_path, quality=88)
      else:
        img.save(out_path)
  except Exception as exc:
    # Some Commons titles carry characters the Windows console can't encode
    # (cp1252); printing them raw would raise a second exception inside this
    # handler and abort the whole run silently. ASCII-safe for display only.
    safe_title = c.title[:60].encode("ascii", "replace").decode("ascii")
    print(f"    ! {safe_title}: {exc}")
    return None

  _write_sidecar(out_path, c, category)
  return out_path


def build(per_category: int, media: str = "image") -> Dict[str, List[Path]]:
  results: Dict[str, List[Path]] = {}
  source_map = VIDEO_SOURCE_CATEGORIES if media == "video" else SOURCE_CATEGORIES
  for category, commons_cats in source_map.items():
    out_dir = LIBRARY_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    seen_titles = set()
    pool: List[Candidate] = []
    for cc in commons_cats:
      for c in fetch_category_members(cc, limit=per_category * 3, media=media):
        if c.title not in seen_titles:
          seen_titles.add(c.title)
          pool.append(c)
      time.sleep(0.3)  # polite pacing between category lookups

    print(f"{category:<16} pool={len(pool):<3} from {len(commons_cats)} Commons categor{'y' if len(commons_cats)==1 else 'ies'}")

    for c in pool:
      if len(saved) >= per_category:
        break
      stem = _slug(Path(c.title).stem)
      already = next(
          (out_dir / f"{stem}{ext}" for ext in (".jpg", ".png", *VIDEO_EXTENSIONS)
           if (out_dir / f"{stem}{ext}").is_file()),
          None,
      )
      if already is not None:
        saved.append(already)
        continue
      path = download_candidate(c, category, out_dir)
      if path is not None:
        saved.append(path)
        print(f"    + {path.name}")
      time.sleep(0.6)  # upload.wikimedia.org rate-limits a fast burst

    results[category] = saved
    print(f"    -> {len(saved)}/{per_category} saved\n")

  return results


def contact_sheet(results: Dict[str, List[Path]], out_path: Path) -> None:
  from PIL import Image, ImageDraw

  all_paths = [(cat, p) for cat, paths in results.items() for p in paths]
  if not all_paths:
    print("nothing to show")
    return

  cols = 6
  cell_w, cell_h = 260, 175
  rows = (len(all_paths) + cols - 1) // cols
  sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), (16, 16, 16))
  draw = ImageDraw.Draw(sheet)
  for i, (cat, p) in enumerate(all_paths):
    x, y = (i % cols) * cell_w, (i // cols) * cell_h
    try:
      with Image.open(p) as im:
        sheet.paste(im.convert("RGB").resize((cell_w - 4, cell_h - 24), Image.BILINEAR), (x + 2, y + 2))
    except Exception:
      pass
    draw.text((x + 4, y + cell_h - 20), f"{cat[:14]}", fill=(250, 204, 21))
  out_path.parent.mkdir(parents=True, exist_ok=True)
  sheet.save(out_path)
  print(f"contact sheet -> {out_path}")
  print("Check by eye before this reaches a render anyone sees: no identifiable")
  print("faces, no branded logos, no on-screen text (README §10.3). Delete the")
  print("image + its .source.json sidecar for anything that fails that check.")


def retag_library() -> int:
  """Recompute the derived fields of every existing .source.json sidecar from
  its own recorded category/commons_title, without touching the network.

  Backfills sidecars written before `domains` and `media_type` existed, so
  assets already on disk gain them without being re-downloaded. `description`
  is deliberately left alone: it can only come from Commons or from a human,
  so an empty one stays empty rather than being filled with a guess.
  """
  count = 0
  for sidecar in sorted(LIBRARY_DIR.rglob("*.source.json")):
    try:
      data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception as exc:
      print(f"    ! {sidecar}: {exc}")
      continue

    category = data.get("category", "")
    title = data.get("commons_title", "")
    tags = list(dict.fromkeys(CATEGORY_BASE_TAGS.get(category, []) + extract_title_tags(title)))
    data["tags"] = tags
    data.setdefault("description", "")
    data["domains"] = CATEGORY_DOMAINS.get(category, [])

    if "media_type" not in data:
      media_path = next(
          (p for p in sidecar.parent.iterdir()
           if p.stem == sidecar.name.removesuffix(".source.json") and not p.name.endswith(".json")),
          None,
      )
      suffix = media_path.suffix.lower() if media_path else ""
      data["media_type"] = "video" if suffix in VIDEO_EXTENSIONS else "image"

    sidecar.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    count += 1
    rel = sidecar.relative_to(LIBRARY_DIR)
    missing = "" if data.get("description") else "   (no description - add one by hand)"
    print(f"retagged: {rel.as_posix()} -> domains={data['domains']} tags={len(tags)}{missing}")

  print(f"=== retagged {count} sidecar(s) under {LIBRARY_DIR} ===")
  return 0


def main() -> int:
  p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
  p.add_argument("--contact-sheet-only", action="store_true", help="skip fetching, just re-render the sheet")
  p.add_argument("--retag", action="store_true", help="recompute tags/domains in existing .source.json sidecars, offline, no fetching")
  p.add_argument("--media", choices=["image", "video", "both"], default="image",
                 help="what to fetch. 'video' pulls Commons b-roll (WebM/Ogg); "
                      "Commons has far fewer clips than stills, so expect thin results")
  args = p.parse_args()

  if args.retag:
    return retag_library()

  if args.contact_sheet_only:
    results = {
        d.name: sorted([f for f in d.glob("*") if f.suffix in (".jpg", ".png")])
        for d in LIBRARY_DIR.iterdir() if d.is_dir()
    } if LIBRARY_DIR.is_dir() else {}
  else:
    if args.media == "both":
      results = build(args.per_category, media="image")
      for category, paths in build(args.per_category, media="video").items():
        results.setdefault(category, []).extend(paths)
    else:
      results = build(args.per_category, media=args.media)
    total = sum(len(v) for v in results.values())
    print(f"=== {total} assets across {len(results)} categories ===")

  contact_sheet(results, BACKEND_ROOT / "out" / "inspect" / "image_library_sheet.png")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
