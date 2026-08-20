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


ENABLE_URL = "https://console.cloud.google.com/apis/library/customsearch.googleapis.com"
CX_URL = "https://programmablesearchengine.google.com/controlpanel/all"


def check() -> int:
  """Diagnose the setup. Costs one query only if both values are present."""
  key, cx = image_fetcher._credentials()
  print(f"GOOGLE_API_KEY    : {'set (' + key[:10] + '…, ' + str(len(key)) + ' chars)' if key else 'NOT SET'}")
  print(f"SEARCH_ENGINE_ID  : {'set (' + cx[:10] + '…)' if cx else 'NOT SET'}")

  cached = list(image_fetcher.CACHE_DIR.glob("*.json")) if image_fetcher.CACHE_DIR.is_dir() else []
  fetched = list(image_fetcher.FETCHED_DIR.glob("*.png")) if image_fetcher.FETCHED_DIR.is_dir() else []
  print(f"cached searches   : {len(cached)}")
  print(f"images on disk    : {len(fetched)}")

  if not key:
    print(f"\nSet GOOGLE_API_KEY in {BACKEND_ROOT / '.env'} (see .env.example).")
    return 1

  import requests

  # A deliberately invalid cx still tells us whether the key works and the API
  # is switched on, so this is worth running before the cx exists.
  probe_cx = cx or "000000000000000000000:aaaaaaaaaaa"
  try:
    response = requests.get(
        image_fetcher.ENDPOINT,
        params={"key": key, "cx": probe_cx, "q": "test", "searchType": "image", "num": 1},
        timeout=15,
    )
  except Exception as exc:
    print(f"\nCould not reach the API: {exc}")
    return 1

  message = ""
  try:
    message = response.json().get("error", {}).get("message", "")
  except ValueError:
    pass

  if response.status_code == 403 and "does not have the access" in message:
    print("\n[FAIL] The Custom Search JSON API is not enabled on this key's project.")
    print(f"       Enable it here, on the SAME project the key belongs to:\n       {ENABLE_URL}")
    print("       It can take a minute or two to take effect after enabling.")
    return 1

  if response.status_code == 400 and "API key not valid" in message:
    print("\n[FAIL] The API key itself was rejected. Re-copy it from the Credentials page.")
    return 1

  if not cx:
    print("\n[OK]   Key accepted and the API is enabled.")
    print(f"[NEXT] Set SEARCH_ENGINE_ID in .env. Get it from:\n       {CX_URL}")
    print("       Create one with 'Search the entire web', then turn Image search ON.")
    return 1

  if response.status_code == 400:
    print(f"\n[FAIL] The search engine ID was rejected: {message[:120]}")
    print(f"       Check it against {CX_URL}")
    return 1

  if not response.ok:
    print(f"\n[FAIL] HTTP {response.status_code}: {message[:160]}")
    return 1

  print("\n[OK]   Key and search engine ID both work. Run without --check to fetch.")
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
