"""Fuzzy metadata search: tokenisation, blended scoring, and stable ordering.

Every test builds its own AssetRecords and passes them in explicitly, so none
of this reads the real assets/broll/library on disk -- the point of this layer
is that it works with no model and no index, and a test that depended on
whatever happens to be seeded would not prove that.
"""

from pathlib import Path

import pytest

from services.visual_rag import fuzzy
from services.visual_rag.catalog import AssetRecord


def _rec(asset_id, title="", tags=(), domains=(), category="ELIGIBILITY", description=""):
    return AssetRecord(
        asset_id=asset_id,
        path=Path("assets") / "broll" / "library" / category / f"{asset_id}.jpg",
        media_type="image",
        category=category,
        title=title,
        tags=tuple(tags),
        domains=tuple(domains),
        description=description,
    )


def _library():
    """A small stand-in catalogue spanning three categories."""
    return [
        _rec(
            "farm",
            title="Agriculture land around P.N.Palayam",
            tags=("agriculture", "farming", "rural", "village", "land"),
            category="ELIGIBILITY",
        ),
        _rec(
            "govt",
            title="Delhi India Government",
            tags=("ministry", "government", "authority", "secretariat", "delhi"),
            category="AUTHORITY",
        ),
        _rec(
            "calendar",
            title="Wall calendar close-up",
            tags=("deadline", "date", "calendar", "schedule"),
            category="DEADLINE",
        ),
    ]


def _ids(results):
    return [record.asset_id for record, _ in results]


# --- tokenisation ---------------------------------------------------------


def test_tokenize_lowercases_and_strips_punctuation():
    assert fuzzy.tokenize("Agriculture land, around P.N.Palayam!") == [
        "agriculture",
        "land",
        "around",
        "palayam",
    ]


def test_tokenize_drops_stopwords_and_single_characters():
    """'P.N.' becomes ['p', 'n'] -- initials that would match half the library."""
    assert fuzzy.tokenize("the farmer is in a village of P.N. district") == [
        "farmer",
        "village",
        "district",
    ]


def test_tokenize_of_empty_text_is_empty():
    assert fuzzy.tokenize("") == []


# --- scoring signals ------------------------------------------------------


def test_exact_tag_match_outranks_a_mere_title_match():
    """Curated tags are the trustworthy signal; a title is incidental prose."""
    tagged = _rec("tagged", title="Untitled photograph", tags=("irrigation",))
    titled = _rec("titled", title="Irrigation canal at dawn", tags=("canal", "water"))
    assert fuzzy.score_asset("irrigation", tagged) > fuzzy.score_asset("irrigation", titled)


def test_morphological_variant_still_matches():
    """A scene says 'farmers'; the asset is tagged 'farming'."""
    farm = _rec("farm", title="Fields at harvest", tags=("farming", "agriculture"))
    other = _rec("other", title="Wall calendar close-up", tags=("deadline", "calendar"))
    assert fuzzy.score_asset("farmers", farm) > fuzzy.score_asset("farmers", other)
    assert _ids(fuzzy.search("farmers", records=[other, farm])) == ["farm"]


def test_substring_credit_for_a_compound_query_word():
    land = _rec("land", title="Open field", tags=("land", "crop"))
    assert fuzzy.score_asset("landholding records", land) > 0.0


def test_category_named_in_the_query_is_a_bonus_not_a_verdict():
    """Category is a filing decision, so naming it nudges rather than decides."""
    on_topic = _rec("on_topic", title="Fields", tags=("farming", "rural"), category="ELIGIBILITY")
    named = _rec("named", title="Fields", tags=("farming", "rural"), category="DEADLINE")
    assert fuzzy.score_asset("rural farming eligibility", on_topic) > fuzzy.score_asset(
        "rural farming eligibility", named
    )


def test_scores_stay_inside_the_unit_interval():
    records = _library()
    for query in ("rural village farming agriculture land eligibility", "", "zzzqqq", "the of and"):
        for record in records:
            assert 0.0 <= fuzzy.score_asset(query, record) <= 1.0


# --- search ---------------------------------------------------------------


def test_results_are_sorted_descending():
    results = fuzzy.search("rural farming village deadline", records=_library(), min_score=0.0)
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_n_results_caps_the_list():
    assert len(fuzzy.search("rural farming deadline government", records=_library(), n_results=1)) == 1


def test_category_filter_restricts_results():
    results = fuzzy.search("rural farming government ministry", records=_library(), category="AUTHORITY")
    assert _ids(results) == ["govt"]


def test_category_filter_is_case_insensitive():
    results = fuzzy.search("government ministry", records=_library(), category="authority")
    assert _ids(results) == ["govt"]


def test_min_score_drops_a_nonsense_query():
    assert fuzzy.search("zzzqqq wobblefrump vlorptastic", records=_library()) == []


def test_raising_min_score_prunes_the_weaker_half():
    library = _library()
    loose = fuzzy.search("rural farming deadline calendar", records=library, min_score=0.0)
    strict = fuzzy.search("rural farming deadline calendar", records=library, min_score=0.4)
    assert len(strict) < len(loose)
    assert all(score >= 0.4 for _, score in strict)


def test_zero_scoring_assets_are_never_returned_even_at_min_score_zero():
    """A zero means no signal fired; handing that back is worse than nothing."""
    library = _library()
    for record, score in fuzzy.search("rural", records=library, min_score=0.0, n_results=99):
        assert score > 0.0


def test_stopword_only_query_matches_nothing():
    assert fuzzy.search("the and of in it is", records=_library(), min_score=0.0) == []


def test_empty_query_is_handled_without_raising():
    assert fuzzy.search("", records=_library()) == []
    assert fuzzy.score_asset("", _library()[0]) == 0.0


def test_empty_catalogue_is_handled_without_raising():
    assert fuzzy.search("rural farming", records=[]) == []


def test_default_min_score_sits_between_noise_and_a_real_hit():
    library = _library()
    noise = max(fuzzy.score_asset("zzzqqq wobblefrump", r) for r in library)
    hit = fuzzy.score_asset("rural farming village", library[0])
    assert noise < fuzzy.DEFAULT_MIN_SCORE < hit


# --- determinism ----------------------------------------------------------


def test_repeated_calls_return_the_identical_order():
    """Demos must not visibly reshuffle their backgrounds between re-renders."""
    library = _library()
    first = _ids(fuzzy.search("rural farming deadline government", records=library, min_score=0.0))
    for _ in range(5):
        assert _ids(fuzzy.search("rural farming deadline government", records=library, min_score=0.0)) == first


def test_equal_scoring_records_resolve_in_a_stable_order():
    """Two assets with identical metadata tie exactly; the sha256 tie-break --
    not input order -- has to decide which comes first."""
    a = _rec("alpha", title="Fields at harvest", tags=("farming", "rural"))
    b = _rec("bravo", title="Fields at harvest", tags=("farming", "rural"))
    assert fuzzy.score_asset("rural farming", a) == fuzzy.score_asset("rural farming", b)

    forwards = _ids(fuzzy.search("rural farming", records=[a, b]))
    backwards = _ids(fuzzy.search("rural farming", records=[b, a]))
    assert forwards == backwards
    assert sorted(forwards) == ["alpha", "bravo"]


def test_tie_break_depends_on_the_query_not_a_global_seed():
    """The pick is a hash of (asset_id, query), so it is reproducible per query
    rather than fixed for the life of the process."""
    seen = set()
    for query in ("rural farming", "farming rural fields", "rural crops farming"):
        a = _rec("alpha", title="Fields", tags=("farming", "rural"))
        b = _rec("bravo", title="Fields", tags=("farming", "rural"))
        seen.add(tuple(_ids(fuzzy.search(query, records=[a, b]))))
    assert len(seen) > 1, "hashing should not collapse to one fixed order"


# --- optional rapidfuzz ---------------------------------------------------


def test_is_available_is_unconditional():
    assert fuzzy.is_available() is True


def test_ranking_survives_without_rapidfuzz(monkeypatch):
    """rapidfuzz is an optimisation; the stdlib path must rank the same way."""
    monkeypatch.setattr(fuzzy, "_rapidfuzz_fuzz", None)
    library = _library()
    assert _ids(fuzzy.search("eligible farmer families in rural districts", records=library))[0] == "farm"
    assert _ids(fuzzy.search("notice issued by the ministry in delhi", records=library))[0] == "govt"
    assert fuzzy.search("zzzqqq wobblefrump vlorptastic", records=library) == []


def test_token_set_ratio_agrees_across_both_backends():
    """Not identical numbers -- different algorithms -- but both must treat full
    query coverage as a full match and unrelated text as near-zero."""
    doc = "agriculture land around palayam rural village farming"
    assert fuzzy._stdlib_token_set_ratio("rural village", doc) == pytest.approx(1.0)
    assert fuzzy._stdlib_token_set_ratio("zzzqqq wobblefrump", doc) < 0.5
    assert fuzzy._token_set_ratio("rural village", doc) == pytest.approx(1.0)
    assert fuzzy._token_set_ratio("zzzqqq wobblefrump", doc) < 0.5
