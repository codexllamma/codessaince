"""Local image library selection: purely offline, no network involved.

The library is a directory tree scripts/build_image_library.py seeds once,
offline, before anything runs — these tests build a throwaway tree in
tmp_path and point the module at it rather than touching the real one.
"""

import json

import pytest

from services import image_library as lib


def _seed(tmp_path, category, name, licence="CC0", artist="Test Artist", tags=None):
  cat_dir = tmp_path / category
  cat_dir.mkdir(parents=True, exist_ok=True)
  (cat_dir / f"{name}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
  meta = {
      "category": category,
      "commons_title": f"File:{name}.jpg",
      "licence": licence,
      "artist": artist,
      "source_page": f"https://commons.wikimedia.org/wiki/File:{name}.jpg",
  }
  if tags is not None:
    meta["tags"] = tags
  (cat_dir / f"{name}.source.json").write_text(
      json.dumps(meta),
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


def test_tag_overlap_is_preferred_over_no_overlap(isolated_library):
  _seed(isolated_library, "AUTHORITY", "matching", tags=["verification"])
  _seed(isolated_library, "AUTHORITY", "unrelated", tags=["building", "office"])
  picked = lib.select_image("AUTHORITY", scene_text="pending verification of your account")
  assert picked is not None
  assert picked.path.name == "matching.jpg"


def test_tied_tag_scores_pick_deterministically(isolated_library):
  for i in range(6):
    _seed(isolated_library, "AUTHORITY", f"office_{i}", tags=["verification"])
  lib.reload_index()
  first = lib.select_image("AUTHORITY", scene_text="verification required", seed="scene-1")
  second = lib.select_image("AUTHORITY", scene_text="verification required", seed="scene-1")
  assert first.path == second.path

  picks = {
      lib.select_image("AUTHORITY", scene_text="verification required", seed=f"scene-{i}").path
      for i in range(20)
  }
  assert len(picks) > 1, "hash should break ties among equally-scored candidates, not just pick the first"


def test_scene_text_matching_nothing_falls_back_to_full_pool_hash(isolated_library):
  for i in range(5):
    _seed(isolated_library, "AMOUNT", f"rupees_{i}", tags=["currency", "cash"])
  lib.reload_index()
  with_unmatched_text = lib.select_image("AMOUNT", scene_text="completely unrelated wording", seed="scene-7")
  without_scene_text = lib.select_image("AMOUNT", seed="scene-7")
  assert with_unmatched_text.path == without_scene_text.path


def test_empty_scene_text_matches_pre_feature_behavior(isolated_library):
  for i in range(5):
    _seed(isolated_library, "AMOUNT", f"rupees_{i}", tags=["currency"])
  lib.reload_index()
  with_empty_text = lib.select_image("AMOUNT", scene_text="", seed="scene-9")
  omitted_text = lib.select_image("AMOUNT", seed="scene-9")
  assert with_empty_text.path == omitted_text.path


def test_sidecar_without_tags_key_loads_with_empty_tags_and_is_a_valid_pick(isolated_library):
  _seed(isolated_library, "DEADLINE", "clock_1")  # no tags kwarg: no "tags" key in sidecar at all
  picked_no_scene_text = lib.select_image("DEADLINE")
  assert picked_no_scene_text is not None
  assert picked_no_scene_text.tags == ()

  picked_with_scene_text = lib.select_image("DEADLINE", scene_text="the deadline is approaching fast")
  assert picked_with_scene_text is not None
  assert picked_with_scene_text.path.name == "clock_1.jpg"


# --- select_generic_image ---------------------------------------------------


def test_generic_image_returns_none_for_an_empty_library():
  assert lib.select_generic_image() is None


def test_generic_image_picks_across_categories(isolated_library):
  """The whole point: a category with nothing still gets a real photo, from
  wherever the library actually has one."""
  _seed(isolated_library, "AUTHORITY", "building_1")
  picked = lib.select_generic_image()
  assert picked is not None
  assert picked.category == "AUTHORITY"


def test_generic_image_is_deterministic(isolated_library):
  _seed(isolated_library, "AUTHORITY", "a")
  _seed(isolated_library, "ELIGIBILITY", "b")
  lib.reload_index()
  first = lib.select_generic_image(seed="scene-1")
  second = lib.select_generic_image(seed="scene-1")
  assert first.path == second.path


def test_generic_image_still_scores_by_tags_when_possible(isolated_library):
  """'Generic' means no category filter, not 'ignore relevance' — a
  cross-category tag match should still win over one that matches nothing."""
  _seed(isolated_library, "AUTHORITY", "building_1", tags=["ministry", "official"])
  _seed(isolated_library, "ELIGIBILITY", "village_1", tags=["village", "rural"])
  lib.reload_index()
  picked = lib.select_generic_image(scene_text="visit the official ministry portal")
  assert picked.path.name == "building_1.jpg"
