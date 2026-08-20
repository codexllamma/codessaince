"""Fuzzy metadata search -- the layer that works when nothing else is installed.

This is the graceful-degradation floor beneath the vector strategy. It reads
the catalogue built from the .source.json sidecars and scores each asset
against a scene's text with string similarity alone: no MiniLM download, no
ChromaDB index, no network, and deliberately no import of either. A machine
that has never run the indexer must still pick sensible visuals, so this
module is always available (`is_available()` is unconditionally True).

rapidfuzz is used when present because its token_set_ratio is both faster and
better behaved than the stdlib equivalent, but it is an optimisation, not a
requirement -- a difflib implementation of the same measure takes over when
the import fails, and the weighted blend below is what actually decides
rankings either way.
"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from services.visual_rag.catalog import AssetRecord, load_catalog

try:  # rapidfuzz is optional; see module docstring.
  from rapidfuzz import fuzz as _rapidfuzz_fuzz
except ImportError:  # pragma: no cover - exercised by forcing the flag in tests
  _rapidfuzz_fuzz = None


# --- signal weights -------------------------------------------------------
#
# The ordering is the point, not the exact numbers. Tags and domains are
# hand-curated per asset by whoever seeded the library, so a query word landing
# on one is the single most trustworthy piece of evidence we have and carries
# the most weight. The token-set ratio comes next: it reads the whole
# embedding_text (title + description + tags + domains + category), which is
# broad enough to catch a real match the tags happened to miss, but also broad
# enough to score incidental words, so it must not be able to outvote a curated
# tag on its own. Partial/substring credit is third -- it rescues morphology
# and compounds ("landholding" vs "land") but fires on coincidental prefixes
# too. The category bonus is deliberately smallest: category is a filing
# decision, not a description, and a scene that says "eligibility" should be
# nudged towards ELIGIBILITY assets, not handed them outright.
#
# They sum to 1.0, which is what keeps the blended score inside [0, 1].
WEIGHT_TAG_OVERLAP: float = 0.45
WEIGHT_TOKEN_SET: float = 0.25
WEIGHT_PARTIAL: float = 0.20
WEIGHT_CATEGORY: float = 0.10

# Character similarity below this is noise -- two unrelated English words
# routinely share half their letters -- so partial credit is withheld entirely
# rather than dribbling small amounts into every score.
PARTIAL_SIM_FLOOR: float = 0.72

# A query sharing nothing but stray letters with an asset lands around 0.03-0.10
# (token-set ratio alone, at a quarter weight). One real tag hit on a
# multi-word query clears 0.30. The threshold sits between those two bands,
# nearer the noise floor, because the cost of the two errors is asymmetric:
# returning a weak-but-plausible visual is recoverable (the caller can still
# fall back), while returning an actively wrong one is what a viewer notices.
DEFAULT_MIN_SCORE: float = 0.18

# Function words carry no visual meaning, and leaving them in would let a scene
# match an asset purely on "the" and "of".
STOPWORDS: FrozenSet[str] = frozenset("""
a an the and or but if then than so because as at by for from in into of on
onto to with without within under over about across after before between
during near per via out up down off again further once here there when where
why how all any both each few more most other some such no nor not only own
same too very can will just should now shall may might must would could
is are was were be been being am do does did doing done have has had having
it its it's this that these those they them their theirs he him his she her
hers we us our ours you your yours i me my mine who whom whose which what
""".split())

_WORD_RE = re.compile(r"[a-z0-9]+")


# --- tokenisation ---------------------------------------------------------


def tokenize(text: str) -> List[str]:
  """Lowercased content words: punctuation stripped, stopwords and single
  characters dropped.

  Single characters go because "P.N.Palayam" in a Commons title explodes into
  ["p", "n", "palayam"] and the initials would otherwise match any query
  containing the letter p.
  """
  if not text:
    return []
  return [t for t in _WORD_RE.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


def _stem(token: str) -> str:
  """Crude suffix stripping, only enough to make morphological variants of the
  same word collide.

  Scene text and curated tags are written by different people at different
  times: a scene says "eligible farmer families", the tag says "farming",
  "family". A real stemmer is overkill for a vocabulary this small, and an
  aggressive one starts merging words that are genuinely different, so this
  handles the plural/gerund/agent endings that actually show up and stops.
  """
  t = token
  if len(t) > 4 and t.endswith("ies"):
    t = t[:-3] + "i"
  elif len(t) > 4 and t.endswith("ing"):
    t = t[:-3]
  elif len(t) > 4 and t.endswith("ers"):
    t = t[:-3]
  elif len(t) > 4 and t.endswith("ed"):
    t = t[:-2]
  elif len(t) > 3 and t.endswith("er"):
    t = t[:-2]
  elif len(t) > 3 and t.endswith("es"):
    t = t[:-2]
  elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
    t = t[:-1]
  if len(t) > 3 and t.endswith("y"):
    t = t[:-1] + "i"
  if len(t) > 3 and t.endswith("e"):
    t = t[:-1]
  return t


def _stems(tokens: Iterable[str]) -> Set[str]:
  return {_stem(t) for t in tokens}


# --- similarity primitives ------------------------------------------------


def _char_ratio(a: str, b: str) -> float:
  """Character-level similarity in [0, 1]."""
  if not a or not b:
    return 1.0 if a == b else 0.0
  if _rapidfuzz_fuzz is not None:
    return float(_rapidfuzz_fuzz.ratio(a, b)) / 100.0
  return SequenceMatcher(None, a, b).ratio()


def _stdlib_token_set_ratio(a: str, b: str) -> float:
  """difflib reimplementation of rapidfuzz's token_set_ratio.

  Compare the shared tokens against each side's shared-plus-leftover string;
  a query whose every token appears in the document scores 1.0 regardless of
  how much extra text the document carries. That "extra text is free"
  behaviour is the whole reason this measure is used here: an asset's
  embedding_text is always far longer than a scene fragment.
  """
  ta, tb = set(a.split()), set(b.split())
  if not ta or not tb:
    return 1.0 if ta == tb else 0.0
  shared = sorted(ta & tb)
  s_shared = " ".join(shared)
  s_a = " ".join(shared + sorted(ta - tb)).strip()
  s_b = " ".join(shared + sorted(tb - ta)).strip()
  return max(
      _char_ratio(s_shared, s_a),
      _char_ratio(s_shared, s_b),
      _char_ratio(s_a, s_b),
  )


def _token_set_ratio(a: str, b: str) -> float:
  if _rapidfuzz_fuzz is not None:
    return float(_rapidfuzz_fuzz.token_set_ratio(a, b)) / 100.0
  return _stdlib_token_set_ratio(a, b)


# --- individual signals ---------------------------------------------------


def _tag_overlap(query_stems: Set[str], tag_stems: Set[str]) -> float:
  """Fraction of the query's distinct content words that hit a curated tag."""
  if not query_stems or not tag_stems:
    return 0.0
  return len(query_stems & tag_stems) / len(query_stems)


def _partial_credit(query_tokens: Set[str], tag_tokens: Set[str]) -> float:
  """Mean best per-query-token similarity against the tag vocabulary.

  Containment either way counts in full -- "landholding" in a scene and "land"
  on the asset are talking about the same picture -- and anything else only
  counts above PARTIAL_SIM_FLOOR.
  """
  if not query_tokens or not tag_tokens:
    return 0.0
  total = 0.0
  for q in query_tokens:
    best = 0.0
    for tag in tag_tokens:
      if q == tag or q in tag or tag in q:
        best = 1.0
        break
      sim = _char_ratio(q, tag)
      if sim >= PARTIAL_SIM_FLOOR and sim > best:
        best = sim
    total += best
  return total / len(query_tokens)


def _category_bonus(query_stems: Set[str], category: str) -> float:
  """1.0 when the scene names the asset's category outright, else 0."""
  if not category or not query_stems:
    return 0.0
  cat_stems = _stems(tokenize(category.replace("_", " ")))
  return 1.0 if query_stems & cat_stems else 0.0


# --- scoring --------------------------------------------------------------


def _tag_vocabulary(record: AssetRecord) -> Set[str]:
  """Tags and domains as tokens. Multi-word tags are split so "rural district"
  can be matched a word at a time."""
  vocab: Set[str] = set()
  for raw in tuple(record.tags) + tuple(record.domains):
    vocab.update(tokenize(raw))
  return vocab


def score_asset(query: str, record: AssetRecord) -> float:
  """Blended similarity of `record` to `query`, in [0, 1]. Higher is better."""
  query_tokens = tokenize(query)
  if not query_tokens:
    # Nothing but stopwords (or nothing at all) is not evidence of anything, and
    # scoring it would rank the whole library on punctuation.
    return 0.0

  query_set = set(query_tokens)
  query_stems = _stems(query_set)
  tag_tokens = _tag_vocabulary(record)
  tag_stems = _stems(tag_tokens)

  doc_tokens = tokenize(record.embedding_text())
  token_set = _token_set_ratio(" ".join(query_tokens), " ".join(doc_tokens))

  score = (
      WEIGHT_TAG_OVERLAP * _tag_overlap(query_stems, tag_stems)
      + WEIGHT_TOKEN_SET * token_set
      + WEIGHT_PARTIAL * _partial_credit(query_set, tag_tokens)
      + WEIGHT_CATEGORY * _category_bonus(query_stems, record.category)
  )
  return max(0.0, min(1.0, score))


def _tiebreak(asset_id: str, query: str) -> str:
  """Stable hash pick, never random -- mirrors _pick_deterministic in
  services/image_library.py. Two assets that describe a scene equally well are
  a genuine tie, and resolving it by dict or filesystem order means a demo
  visibly reshuffles its own backgrounds between identical re-renders."""
  return hashlib.sha256(f"{asset_id}|{query}".encode("utf-8")).hexdigest()


def search(
    query: str,
    records: Optional[Sequence[AssetRecord]] = None,
    n_results: int = 5,
    category: Optional[str] = None,
    min_score: float = DEFAULT_MIN_SCORE,
) -> List[Tuple[AssetRecord, float]]:
  """The best `n_results` assets for `query`, strongest first.

  `records` defaults to the on-disk catalogue; pass an explicit sequence to
  search a subset (or to keep tests off the real library). `category`
  restricts to one category name, compared case-insensitively. Assets scoring
  0 are dropped regardless of `min_score` -- a zero means no signal fired at
  all, so returning one would be worse than returning nothing and letting the
  caller fall back.
  """
  pool = load_catalog() if records is None else records
  if not pool or n_results <= 0:
    return []
  if category:
    wanted = category.strip().lower()
    pool = [r for r in pool if r.category.lower() == wanted]
  if not pool:
    return []

  if not tokenize(query):
    return []

  scored: List[Tuple[AssetRecord, float]] = []
  for record in pool:
    # Rounded so that two assets whose signals are identical tie exactly rather
    # than differing in the last float ulp and ordering unpredictably.
    value = round(score_asset(query, record), 6)
    if value > 0.0 and value >= min_score:
      scored.append((record, value))

  scored.sort(key=lambda pair: (-pair[1], _tiebreak(pair[0].asset_id, query), pair[0].asset_id))
  return scored[:n_results]


def is_available() -> bool:
  """Always True. Unlike the vector layer there is no model to download and no
  index to build, which is exactly why this sits underneath it."""
  return True
