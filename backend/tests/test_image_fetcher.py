"""Image fetching: query building, caching, and degradation.

Nothing here touches the network. The API allows 100 queries a day and a test
suite that spent them would be unrunnable by lunchtime, so every call is
mocked and the quota is untouched.
"""

import json

import pytest

from services import image_fetcher as imf


@pytest.fixture(autouse=True)
def isolate_dirs(tmp_path, monkeypatch):
  """Point the module's cache and download dirs at tmp_path."""
  monkeypatch.setattr(imf, "CACHE_DIR", tmp_path / "cache")
  monkeypatch.setattr(imf, "FETCHED_DIR", tmp_path / "fetched")
  return tmp_path


class _Response:
  def __init__(self, status=200, payload=None):
    self.status_code = status
    self._payload = payload if payload is not None else {}

  @property
  def ok(self):
    return 200 <= self.status_code < 300

  def json(self):
    return self._payload


def _payload(*sizes):
  return {
      "items": [
          {
              "link": f"https://example.test/img{i}.jpg",
              "mime": "image/jpeg",
              "image": {"contextLink": f"https://example.test/page{i}", "width": w, "height": h},
          }
          for i, (w, h) in enumerate(sizes)
      ]
  }


def _with_creds(monkeypatch):
  monkeypatch.setattr(imf, "_credentials", lambda: ("test-key", "test-cx"))


# --- query building -------------------------------------------------------


def test_amount_query_avoids_the_literal_number():
  """'2000' returns charts and banknote montages covered in figures, which
  README 10.3 rules out. The subject is money, not the digits."""
  q = imf.build_query("AMOUNT", "Rs 2000")
  assert "2000" not in q
  assert "rupee" in q.lower()


def test_scheme_name_query_avoids_the_scheme_name():
  """Searching 'PM-KISAN' returns logos and portal screenshots."""
  q = imf.build_query("SCHEME_NAME", "PM-KISAN")
  assert "kisan" not in q.lower().replace("indian farmer", "")
  assert "farmer" in q.lower()


def test_deadline_query_avoids_the_date():
  q = imf.build_query("DEADLINE", "31-10-2026")
  assert "31" not in q and "2026" not in q


def test_free_text_category_uses_its_own_words():
  """Who is eligible actually describes a scene, unlike a date or an amount."""
  q = imf.build_query("ELIGIBILITY", "smallholder tribal households")
  assert "smallholder" in q or "tribal" in q or "households" in q


def test_unknown_category_falls_back_to_a_default():
  assert imf.build_query("NOT_A_CATEGORY") == imf.DEFAULT_QUERY


# --- searching and caching ------------------------------------------------


def test_search_caches_results_so_a_repeat_costs_no_quota(monkeypatch):
  _with_creds(monkeypatch)
  calls = []

  def fake_get(url, params=None, timeout=None):
    calls.append(params["q"])
    return _Response(200, _payload((3000, 2000)))

  monkeypatch.setattr("requests.get", fake_get)

  first = imf.search_images("wheat field")
  second = imf.search_images("wheat field")

  assert len(first) == 1 and len(second) == 1
  assert len(calls) == 1, "second identical search must be served from cache"


def test_different_rights_filter_is_a_different_search(monkeypatch):
  _with_creds(monkeypatch)
  calls = []
  monkeypatch.setattr(
      "requests.get",
      lambda url, params=None, timeout=None: (calls.append(1), _Response(200, _payload((3000, 2000))))[1],
  )
  imf.search_images("wheat", rights="cc_publicdomain")
  imf.search_images("wheat", rights=None)
  assert len(calls) == 2


def test_creative_commons_filter_is_sent_by_default(monkeypatch):
  _with_creds(monkeypatch)
  seen = {}

  def fake_get(url, params=None, timeout=None):
    seen.update(params)
    return _Response(200, _payload((3000, 2000)))

  monkeypatch.setattr("requests.get", fake_get)
  imf.search_images("wheat field")
  assert seen["rights"] == imf.DEFAULT_RIGHTS
  assert seen["safe"] == "active", "a government notice must not surface unsafe imagery"


def test_missing_credentials_returns_empty_not_an_error(monkeypatch):
  monkeypatch.setattr(imf, "_credentials", lambda: (None, None))
  assert imf.search_images("anything") == []


def test_quota_exhaustion_degrades_quietly(monkeypatch):
  _with_creds(monkeypatch)
  monkeypatch.setattr("requests.get", lambda *a, **k: _Response(429))
  assert imf.search_images("wheat") == []


def test_api_not_enabled_degrades_quietly(monkeypatch):
  _with_creds(monkeypatch)
  monkeypatch.setattr("requests.get", lambda *a, **k: _Response(403))
  assert imf.search_images("wheat") == []


def test_network_failure_degrades_quietly(monkeypatch):
  _with_creds(monkeypatch)

  def boom(*a, **k):
    raise OSError("no route to host")

  monkeypatch.setattr("requests.get", boom)
  assert imf.search_images("wheat") == []


def test_malformed_cache_is_discarded_not_fatal(monkeypatch, isolate_dirs):
  _with_creds(monkeypatch)
  imf.CACHE_DIR.mkdir(parents=True, exist_ok=True)
  imf._cache_path("wheat", imf.DEFAULT_RIGHTS, 5).write_text("{not json", encoding="utf-8")
  monkeypatch.setattr("requests.get", lambda *a, **k: _Response(200, _payload((3000, 2000))))
  assert len(imf.search_images("wheat")) == 1


# --- candidate filtering --------------------------------------------------


def test_small_images_are_rejected_for_kenburns():
  """Ken Burns pans across a source larger than the output; a 1920x1080 image
  would have to be upscaled to move at all."""
  small = imf.ImageCandidate("u", "c", "image/jpeg", 1920, 1080)
  big = imf.ImageCandidate("u", "c", "image/jpeg", 3000, 2000)
  assert not small.is_large_enough
  assert big.is_large_enough


def test_fetch_returns_none_when_every_candidate_is_too_small(monkeypatch):
  _with_creds(monkeypatch)
  monkeypatch.setattr("requests.get", lambda *a, **k: _Response(200, _payload((800, 600), (1024, 768))))
  assert imf.fetch_image_for_query("wheat field") is None


def test_provenance_is_recorded_beside_the_image(monkeypatch, isolate_dirs):
  """An officer can only vet an image if they can see where it came from."""
  from io import BytesIO

  from PIL import Image

  buf = BytesIO()
  Image.new("RGB", (3000, 2000), (90, 140, 60)).save(buf, format="PNG")
  body = buf.getvalue()

  class _Download:
    ok = True
    status_code = 200

    def iter_content(self, n):
      yield body

    def __enter__(self):
      return self

    def __exit__(self, *a):
      return False

  monkeypatch.setattr("requests.get", lambda *a, **k: _Download())

  candidate = imf.ImageCandidate(
      "https://example.test/w.png", "https://example.test/page", "image/png", 3000, 2000
  )
  path = imf.download_image(candidate, "wheat field")
  assert path is not None and path.is_file()

  meta = json.loads(path.with_suffix(".source.json").read_text(encoding="utf-8"))
  assert meta["image_url"] == "https://example.test/w.png"
  assert meta["source_page"] == "https://example.test/page"
  assert meta["query"] == "wheat field"
  assert meta["declared_rights_filter"] == imf.DEFAULT_RIGHTS


def test_undecodable_download_is_rejected(monkeypatch, isolate_dirs):
  """A .jpg URL is not proof of an image; it has to decode."""

  class _Download:
    ok = True
    status_code = 200

    def iter_content(self, n):
      yield b"this is not an image"

    def __enter__(self):
      return self

    def __exit__(self, *a):
      return False

  monkeypatch.setattr("requests.get", lambda *a, **k: _Download())
  candidate = imf.ImageCandidate("https://example.test/x.jpg", "", "image/jpeg", 3000, 2000)
  assert imf.download_image(candidate, "wheat") is None
