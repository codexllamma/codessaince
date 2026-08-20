"""Local image library selection: purely offline, no network involved.

The library is a directory tree scripts/build_image_library.py seeds once,
offline, before anything runs — these tests build a throwaway tree in
tmp_path and point the module at it rather than touching the real one.
"""

import json

import pytest

from services import image_library as lib


def _seed(tmp_path, category, name, licence="CC0", artist="Test Artist"):
  cat_dir = tmp_path / category
  cat_dir.mkdir(parents=True, exist_ok=True)
  (cat_dir / f"{name}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
  (cat_dir / f"{name}.source.json").write_text(
      json.dumps({
          "category": category,
          "commons_title": f"File:{name}.jpg",
          "licence": licence,
          "artist": artist,
          "source_page": f"https://commons.wikimedia.org/wiki/File:{name}.jpg",
      }),
      encoding="utf-8",
  )
  return cat_dir / f"{name}.jpg"


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
  monkeypatch.setattr(lib, "LIBRARY_DIR", tmp_path)
  lib.reload_index()
  yield tmp_path
  lib.reload_index()  # do not leak this test's cache into the next one


def test_empty_library_returns_none():
  """No library seeded yet is the normal starting state, not an error."""
  assert lib.select_image("AMOUNT") is None


def test_selects_from_the_right_category(isolated_library):
  _seed(isolated_library, "AMOUNT", "rupees_1")
  _seed(isolated_library, "DEADLINE", "clock_1")
  picked = lib.select_image("AMOUNT")
  assert picked is not None
  assert picked.category == "AMOUNT"


def test_category_with_no_images_returns_none_even_if_others_are_populated(isolated_library):
  _seed(isolated_library, "AMOUNT", "rupees_1")
  assert lib.select_image("DEADLINE") is None


def test_selection_is_deterministic_for_the_same_seed(isolated_library):
  for i in range(5):
    _seed(isolated_library, "AMOUNT", f"rupees_{i}")
  lib.reload_index()
  first = lib.select_image("AMOUNT", seed="scene-42")
  second = lib.select_image("AMOUNT", seed="scene-42")
  assert first.path == second.path, "same scene must not reshuffle its background across renders"


def test_different_seeds_can_pick_different_images(isolated_library):
  """Not a hard guarantee for any specific pair, but across enough seeds the
  pool should not collapse onto a single image."""
  for i in range(8):
    _seed(isolated_library, "AMOUNT", f"rupees_{i}")
  lib.reload_index()
  picks = {lib.select_image("AMOUNT", seed=f"scene-{i}").path for i in range(20)}
  assert len(picks) > 1


def test_missing_sidecar_is_skipped_not_fatal(isolated_library):
  cat_dir = isolated_library / "AMOUNT"
  cat_dir.mkdir(parents=True)
  (cat_dir / "orphan.jpg").write_bytes(b"\xff\xd8\xff\xe0")
  assert lib.select_image("AMOUNT") is None


def test_malformed_sidecar_is_skipped_not_fatal(isolated_library):
  cat_dir = isolated_library / "AMOUNT"
  cat_dir.mkdir(parents=True)
  (cat_dir / "bad.jpg").write_bytes(b"\xff\xd8\xff\xe0")
  (cat_dir / "bad.source.json").write_text("{not json", encoding="utf-8")
  assert lib.select_image("AMOUNT") is None


def test_non_image_files_in_the_category_dir_are_ignored(isolated_library):
  cat_dir = isolated_library / "AMOUNT"
  cat_dir.mkdir(parents=True)
  (cat_dir / "notes.txt").write_text("not an image")
  _seed(isolated_library, "AMOUNT", "rupees_1")
  picked = lib.select_image("AMOUNT")
  assert picked is not None and picked.path.suffix == ".jpg"


def test_provenance_fields_are_exposed(isolated_library):
  _seed(isolated_library, "AUTHORITY", "building_1", licence="GODL-India", artist="Ministry of X")
  picked = lib.select_image("AUTHORITY")
  assert picked.licence == "GODL-India"
  assert picked.artist == "Ministry of X"
  assert picked.source_page.startswith("https://commons.wikimedia.org")


def test_available_categories_reflects_what_was_seeded(isolated_library):
  _seed(isolated_library, "AMOUNT", "a")
  _seed(isolated_library, "DEADLINE", "d")
  assert lib.available_categories() == ("AMOUNT", "DEADLINE")
