"""Fetch a still image for a fact via Google Programmable Search.

Turns an ExtractedFact into a background still, so a scene about wheat shows
wheat instead of the procedural gradient. The compositor already handles
`static_graphic` assets, so a fetched image needs no rendering changes — it
drops into VisualAssetSelection.file_path and Ken Burns pans across it.

Three constraints shape everything here.

*The free tier is 100 queries a day.* Search results are cached on disk by
query, so a repeated query costs nothing. During a sprint you will run the
same four scenes dozens of times; without the cache that alone exhausts the
quota before lunch. Cache hits are logged so you can see what you are
actually spending.

*The images belong to other people.* Web image search returns whatever is on
the web, and a government notice illustrated with someone's copyrighted
photograph is a real problem rather than a theoretical one. Results are
filtered to Creative Commons licences by default, and every download writes a
provenance sidecar recording the query, the page it came from, and the
declared rights. That is also what makes the officer approval gate meaningful
— an officer can only vet an image if they can see where it came from.

*A scene must never fail for want of an asset* (README §10.2). Every failure
path here returns None, and the caller keeps whatever asset it already had.
No missing key, quota error, timeout, or malformed image can break a render.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

ENDPOINT = "https://www.googleapis.com/customsearch/v1"

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FETCHED_DIR = BACKEND_ROOT / "assets" / "broll" / "fetched"
CACHE_DIR = BACKEND_ROOT / "assets" / "broll" / ".search_cache"

# Ken Burns pans across a source larger than the output, so an image that only
# just reaches 1920x1080 would have to be upscaled to move at all. Rejecting
# below this is cheaper than shipping a soft background.
MIN_WIDTH = 2100
MIN_HEIGHT = 1200

# Creative Commons only by default. Passing rights=None searches everything,
# which is fine for a private test and not fine for anything anyone will see.
DEFAULT_RIGHTS = "cc_publicdomain|cc_attribute|cc_sharealike"

REQUEST_TIMEOUT_SEC = 10
DOWNLOAD_TIMEOUT_SEC = 20
MAX_BYTES = 12 * 1024 * 1024


class ImageFetchError(Exception):
  """Raised only by the strict CLI path; the pipeline path returns None."""


@dataclass(frozen=True)
class ImageCandidate:
  url: str
  context_link: str
  mime: str
  width: int
  height: int

  @property
  def is_large_enough(self) -> bool:
    return self.width >= MIN_WIDTH and self.height >= MIN_HEIGHT


def _credentials() -> tuple[Optional[str], Optional[str]]:
  """(api_key, cx) from the environment, loading a .env if one is present."""
  try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_ROOT / ".env")
  except ImportError:  # python-dotenv is pinned, but do not hard-fail on it
    pass
  return os.getenv("GOOGLE_API_KEY"), os.getenv("SEARCH_ENGINE_ID")


def is_configured() -> bool:
  key, cx = _credentials()
  return bool(key and cx)


def _cache_path(query: str, rights: Optional[str], num: int) -> Path:
  # Rights and count are part of the identity: the same words under a
  # different licence filter are a different search and a different answer.
  digest = hashlib.sha256(f"{query}|{rights}|{num}".encode("utf-8")).hexdigest()[:16]
  return CACHE_DIR / f"{digest}.json"


def search_images(
    query: str,
    num: int = 5,
    rights: Optional[str] = DEFAULT_RIGHTS,
    use_cache: bool = True,
) -> List[ImageCandidate]:
  """Image results for `query`. Returns [] rather than raising.

  A cached result costs no quota, so repeated renders of the same scene are
  free. Delete assets/broll/.search_cache to force fresh results.
  """
  if not query.strip():
    return []

  cache_file = _cache_path(query, rights, num)
  if use_cache and cache_file.is_file():
    try:
      raw = json.loads(cache_file.read_text(encoding="utf-8"))
      logger.info("image search cache hit for %r (no quota spent)", query)
      return [ImageCandidate(**c) for c in raw["candidates"]]
    except (json.JSONDecodeError, KeyError, TypeError):
      logger.warning("discarding malformed search cache %s", cache_file.name)

  api_key, cx = _credentials()
  if not api_key or not cx:
    logger.info(
        "GOOGLE_API_KEY/SEARCH_ENGINE_ID not set; skipping image search for %r. "
        "See .env.example",
        query,
    )
    return []

  try:
    import requests

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": max(1, min(num, 10)),  # the API caps at 10
        "safe": "active",
        "imgSize": "xlarge",
    }
    if rights:
      params["rights"] = rights

    response = requests.get(ENDPOINT, params=params, timeout=REQUEST_TIMEOUT_SEC)
  except Exception:
    logger.warning("image search for %r failed to reach the API", query, exc_info=True)
    return []

  if response.status_code == 429:
    logger.warning("image search quota exhausted (100/day on the free tier); using fallbacks")
    return []
  if response.status_code == 403:
    logger.warning(
        "image search refused (403). Usually the Custom Search API is not enabled "
        "on the project, or the key is restricted to other APIs."
    )
    return []
  if not response.ok:
    logger.warning("image search returned HTTP %s for %r", response.status_code, query)
    return []

  try:
    payload = response.json()
  except ValueError:
    logger.warning("image search returned a non-JSON body for %r", query)
    return []

  candidates: List[ImageCandidate] = []
  for item in payload.get("items", []):
    image = item.get("image") or {}
    try:
      candidates.append(
          ImageCandidate(
              url=item["link"],
              context_link=image.get("contextLink", ""),
              mime=item.get("mime", ""),
              width=int(image.get("width", 0)),
              height=int(image.get("height", 0)),
          )
      )
    except (KeyError, TypeError, ValueError):
      continue

  CACHE_DIR.mkdir(parents=True, exist_ok=True)
  cache_file.write_text(
      json.dumps(
          {
              "query": query,
              "rights": rights,
              "fetched_at": datetime.now(timezone.utc).isoformat(),
              "candidates": [asdict(c) for c in candidates],
          },
          indent=2,
      ),
      encoding="utf-8",
  )
  logger.info("image search for %r returned %d candidate(s)", query, len(candidates))
  return candidates


def _slug(text: str) -> str:
  return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48] or "image"


# Searching the literal fact value is the obvious approach and the wrong one.
# "PM-KISAN" returns logos and portal screenshots; "₹2,000" returns charts and
# stock-photo banknote montages with figures printed on them; "31-10-2026"
# returns calendar graphics covered in numbers. README §10.3 rules all of that
# out — no branded logos, no text. So a category maps to the *subject* the
# fact is about, and only free-text categories contribute their own words.
CATEGORY_QUERIES = {
    "SCHEME_NAME": "indian farmer wheat field harvest",
    "AMOUNT": "indian rupee banknotes closeup",
    "DEADLINE": "wall clock calendar minimal desk",
    "ELIGIBILITY": "rural indian village household",
    "BENEFICIARY": "indian farmers working field",
    "AUTHORITY": "indian government building architecture",
    "ACTION_REQUIRED": "smartphone digital payment rural india",
}

DEFAULT_QUERY = "rural india landscape agriculture"

# Words that pull results towards documents, logos and screenshots.
_NOISE = re.compile(
    r"\b(scheme|yojana|installment|instalment|rs|inr|rupees?|ministry|govt|government|"
    r"portal|website|www|gov|in|before|after|last|date|complete|verification)\b",
    re.IGNORECASE,
)


def build_query(category: str, value: str = "", extra: str = "") -> str:
  """An image query for a fact of `category`.

  Free-text categories (who is eligible, what to do) genuinely describe a
  scene, so their own words help. Numeric and named categories do not, and
  contribute nothing but noise, so their subject mapping is used alone.
  """
  base = CATEGORY_QUERIES.get(category.upper(), DEFAULT_QUERY)

  if category.upper() in ("ELIGIBILITY", "BENEFICIARY"):
    cleaned = _NOISE.sub(" ", value)
    cleaned = re.sub(r"[^A-Za-z\s]", " ", cleaned)
    words = [w for w in cleaned.split() if len(w) > 3][:3]
    if words:
      return f"{' '.join(words).lower()} india photograph"

  return f"{base} {extra}".strip()


def download_image(
    candidate: ImageCandidate, query: str, rights: Optional[str] = DEFAULT_RIGHTS
) -> Optional[Path]:
  """Download and verify one candidate. Returns the saved path, or None.

  Verification is not optional: the URL is arbitrary web content, so it is
  decoded with Pillow before being accepted. A file that decodes is an image;
  a file that merely has a .jpg URL is not.
  """
  try:
    import requests
    from PIL import Image

    with requests.get(candidate.url, timeout=DOWNLOAD_TIMEOUT_SEC, stream=True) as response:
      if not response.ok:
        logger.info("candidate %s returned HTTP %s", candidate.url[:80], response.status_code)
        return None

      body = b""
      for chunk in response.iter_content(64 * 1024):
        body += chunk
        if len(body) > MAX_BYTES:
          logger.info("candidate %s exceeds %d MB; skipping", candidate.url[:80], MAX_BYTES // 1048576)
          return None

    FETCHED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FETCHED_DIR / f"{_slug(query)}_{hashlib.sha256(candidate.url.encode()).hexdigest()[:8]}.png"

    from io import BytesIO

    with Image.open(BytesIO(body)) as img:
      img.load()
      if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
        logger.info(
            "candidate %s is %dx%d, below the %dx%d Ken Burns minimum",
            candidate.url[:60], img.width, img.height, MIN_WIDTH, MIN_HEIGHT,
        )
        return None
      img.convert("RGB").save(out_path)
  except Exception:
    logger.info("candidate %s could not be downloaded or decoded", candidate.url[:80], exc_info=True)
    return None

  # Provenance sits beside the image, not in a database, so it survives being
  # copied around and is readable by whoever has to vet the picture.
  out_path.with_suffix(".source.json").write_text(
      json.dumps(
          {
              "query": query,
              "image_url": candidate.url,
              "source_page": candidate.context_link,
              "declared_rights_filter": rights,
              "fetched_at": datetime.now(timezone.utc).isoformat(),
              "note": (
                  "Rights come from the search filter, which reflects what the "
                  "publisher declared. Verify before any public use."
              ),
          },
          indent=2,
      ),
      encoding="utf-8",
  )
  logger.info("fetched %s for %r", out_path.name, query)
  return out_path


def fetch_image_for_query(
    query: str, rights: Optional[str] = DEFAULT_RIGHTS, max_attempts: int = 4
) -> Optional[Path]:
  """Best usable image for `query`, or None.

  Tries candidates in rank order until one downloads and decodes, because the
  top hit is regularly a dead link or a thumbnail dressed up as full size.
  """
  # An already-fetched image for this query is reused rather than re-downloaded.
  existing = sorted(FETCHED_DIR.glob(f"{_slug(query)}_*.png")) if FETCHED_DIR.is_dir() else []
  if existing:
    logger.info("reusing already-fetched %s for %r", existing[0].name, query)
    return existing[0]

  candidates = [c for c in search_images(query, rights=rights) if c.is_large_enough]
  if not candidates:
    return None

  for candidate in candidates[:max_attempts]:
    path = download_image(candidate, query, rights)
    if path is not None:
      return path

  logger.info("no candidate for %r survived download and decoding", query)
  return None
