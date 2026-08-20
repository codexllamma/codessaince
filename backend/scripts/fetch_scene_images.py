"""Prefetch and inspect background stills for the standard scene categories.

    python scripts/fetch_scene_images.py --check      # credentials only, 0 quota
    python scripts/fetch_scene_images.py              # fetch all four categories
    python scripts/fetch_scene_images.py --query "flood relief india"
    python scripts/fetch_scene_images.py --contact-sheet

Run this before a demo rather than letting renders hit the API. Search results
are cached, so a render afterwards spends no quota, and you get to look at what
turned up before it appears behind a government notice.

Every image is somebody's photograph. README §10.3 asks for no identifiable
faces, no branded logos and no text, and no API filter enforces that — the
contact sheet exists so a person can check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
  sys.path.insert(0, str(BACKEND_ROOT))

import logging

from services import image_fetcher

CATEGORIES = ["SCHEME_NAME", "AMOUNT", "DEADLINE", "ACTION_REQUIRED"]


def check() -> int:
  key, cx = image_fetcher._credentials()
  print(f"GOOGLE_API_KEY    : {'set (' + key[:6] + '…)' if key else 'NOT SET'}")
  print(f"SEARCH_ENGINE_ID  : {'set (' + cx[:6] + '…)' if cx else 'NOT SET'}")
  if not (key and cx):
    print(f"\nCopy {BACKEND_ROOT / '.env.example'} to .env and fill both in.")
    return 1

  cached = list(image_fetcher.CACHE_DIR.glob("*.json")) if image_fetcher.CACHE_DIR.is_dir() else []
  fetched = list(image_fetcher.FETCHED_DIR.glob("*.png")) if image_fetcher.FETCHED_DIR.is_dir() else []
  print(f"\ncached searches   : {len(cached)} (each one is a query you do not pay for again)")
  print(f"images on disk    : {len(fetched)}")
  print("\nCredentials look present. This check spent no quota; run without --check to fetch.")
  return 0


def contact_sheet(paths, out_path: Path) -> None:
  from PIL import Image, ImageDraw

  if not paths:
    print("nothing to show")
    return
  W, H = 420, 236
  sheet = Image.new("RGB", (W * min(len(paths), 4), H * ((len(paths) + 3) // 4)), (18, 18, 18))
  for i, p in enumerate(paths):
    with Image.open(p) as im:
      sheet.paste(im.convert("RGB").resize((W, H), Image.BILINEAR), (W * (i % 4), H * (i // 4)))
    ImageDraw.Draw(sheet).text((W * (i % 4) + 6, H * (i // 4) + 6), p.stem[:44], fill=(255, 255, 0))
  out_path.parent.mkdir(parents=True, exist_ok=True)
  sheet.save(out_path)
  print(f"\ncontact sheet -> {out_path}")
  print("Check each one by eye: no identifiable faces, no logos, no text (README §10.3).")


def main() -> int:
  p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument("--check", action="store_true", help="verify credentials, spend no quota")
  p.add_argument("--query", help="fetch one specific query instead of the category set")
  p.add_argument("--any-rights", action="store_true",
                 help="drop the Creative Commons filter (private testing only)")
  p.add_argument("--contact-sheet", action="store_true", help="write a sheet of what is on disk")
  p.add_argument("--verbose", action="store_true")
  args = p.parse_args()

  logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")

  if args.check:
    return check()

  if not image_fetcher.is_configured():
    print("No credentials configured. Run with --check for setup instructions.", file=sys.stderr)
    return 1

  rights = None if args.any_rights else image_fetcher.DEFAULT_RIGHTS
  if args.any_rights:
    print("WARNING: licence filter off. Results may be fully copyrighted.\n")

  queries = [(args.query, args.query)] if args.query else [
      (c, image_fetcher.build_query(c)) for c in CATEGORIES
  ]

  saved = []
  for label, query in queries:
    print(f"{label:<18} {query!r}")
    path = image_fetcher.fetch_image_for_query(query, rights=rights)
    if path is None:
      print("   -> nothing usable; this scene keeps the gradient fallback")
      continue
    saved.append(path)
    meta_file = path.with_suffix(".source.json")
    source = json.loads(meta_file.read_text(encoding="utf-8")).get("source_page", "") if meta_file.is_file() else ""
    print(f"   -> {path.name}")
    if source:
      print(f"      from {source[:88]}")

  if args.contact_sheet or saved:
    on_disk = sorted(image_fetcher.FETCHED_DIR.glob("*.png")) if image_fetcher.FETCHED_DIR.is_dir() else []
    contact_sheet(on_disk, BACKEND_ROOT / "out" / "inspect" / "fetched_images.png")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
