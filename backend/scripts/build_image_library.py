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


def fetch_category_members(category: str, limit: int = 20) -> List[Candidate]:
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
    if Path(title).suffix.lower() in EXCLUDE_EXTENSIONS:
      continue

    infos = page.get("imageinfo") or []
    if not infos:
      continue
    info = infos[0]
    width, height = info.get("width", 0), info.get("height", 0)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
      continue

    meta = info.get("extmetadata", {}) or {}
    licence = (meta.get("LicenseShortName", {}) or {}).get("value", "")
    if not licence.lower().startswith(ACCEPTED_LICENCE_PREFIXES):
      continue

    artist = _strip_html((meta.get("Artist", {}) or {}).get("value", "")) or "Unknown (see source page)"

    out.append(Candidate(
        title=title, url=info["url"], page=info.get("descriptionurl", ""),
        width=width, height=height, mime=info.get("mime", ""),
        licence=licence, artist=artist,
    ))
  return out


def _slug(text: str) -> str:
  return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:56] or "image"


def _download_body(url: str, attempts: int = 4) -> Optional[bytes]:
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
          if len(body) > MAX_BYTES:
            return None
        return body
    except Exception:
      time.sleep(1.5 * (attempt + 1))
  return None


def download_candidate(c: Candidate, category: str, out_dir: Path) -> Optional[Path]:
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

  out_path.with_suffix(".source.json").write_text(
      json.dumps({
          "category": category,
          "commons_title": c.title,
          "image_url": c.url,
          "source_page": c.page,
          "licence": c.licence,
          "artist": c.artist,
          "width": c.width,
          "height": c.height,
      }, indent=2, ensure_ascii=False),
      encoding="utf-8",
  )
  return out_path


def build(per_category: int) -> Dict[str, List[Path]]:
  results: Dict[str, List[Path]] = {}
  for category, commons_cats in SOURCE_CATEGORIES.items():
    out_dir = LIBRARY_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    seen_titles = set()
    pool: List[Candidate] = []
    for cc in commons_cats:
      for c in fetch_category_members(cc, limit=per_category * 3):
        if c.title not in seen_titles:
          seen_titles.add(c.title)
          pool.append(c)
      time.sleep(0.3)  # polite pacing between category lookups

    print(f"{category:<16} pool={len(pool):<3} from {len(commons_cats)} Commons categor{'y' if len(commons_cats)==1 else 'ies'}")

    for c in pool:
      if len(saved) >= per_category:
        break
      existing = out_dir / f"{_slug(Path(c.title).stem)}.jpg"
      existing_png = existing.with_suffix(".png")
      if existing.is_file() or existing_png.is_file():
        saved.append(existing if existing.is_file() else existing_png)
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


def main() -> int:
  p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
  p.add_argument("--contact-sheet-only", action="store_true", help="skip fetching, just re-render the sheet")
  args = p.parse_args()

  if args.contact_sheet_only:
    results = {
        d.name: sorted([f for f in d.glob("*") if f.suffix in (".jpg", ".png")])
        for d in LIBRARY_DIR.iterdir() if d.is_dir()
    } if LIBRARY_DIR.is_dir() else {}
  else:
    results = build(args.per_category)
    total = sum(len(v) for v in results.values())
    print(f"=== {total} images across {len(results)} categories ===")

  contact_sheet(results, BACKEND_ROOT / "out" / "inspect" / "image_library_sheet.png")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
