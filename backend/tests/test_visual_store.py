"""Vector store behaviour: indexing, retrieval, scoring, and graceful absence.

Nothing here downloads a model or touches a GPU. The real embedder is swapped
for a deterministic bag-of-words hash so the tests assert what the *store* does
with vectors -- upsert semantics, the filter, the distance-to-score conversion --
rather than re-testing MiniLM. Chroma is pointed at a tmp_path so the real index
under backend/data/chroma is never opened, let alone written.
"""

import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from services.visual_rag import embeddings, store
from services.visual_rag.catalog import AssetRecord

FAKE_DIM = 64


def _fake_vector(text):
    """Unit-length bag-of-words over FAKE_DIM buckets.

    md5 rather than hash(): PYTHONHASHSEED randomises str hashing per process,
    and a retrieval test whose winner changes between runs proves nothing.
    """
    vec = np.zeros(FAKE_DIM, dtype=np.float32)
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % FAKE_DIM
        vec[bucket] += 1.0
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def _fake_embed_texts(texts):
    items = list(texts)
    if not items:
        return np.zeros((0, FAKE_DIM), dtype=np.float32)
    return np.stack([_fake_vector(t) for t in items])


def _fake_embed_query(text):
    return _fake_vector(text)


def _record(asset_id, category, title, tags=(), domains=(), description=""):
    return AssetRecord(
        asset_id=asset_id,
        path=Path("assets/broll/library") / category / f"{asset_id.split('/')[-1]}.jpg",
        media_type="image",
        category=category,
        title=title,
        tags=tags,
        domains=domains,
        description=description,
        licence="CC BY-SA 4.0",
        artist="Someone",
        source_page="https://commons.wikimedia.org/wiki/File:X.jpg",
        width=1920,
        height=1080,
    )


FARM = _record(
    "ELIGIBILITY/farm",
    "ELIGIBILITY",
    "Agriculture land around Palayam",
    tags=("farmer", "agriculture", "crop", "irrigation"),
    domains=("agriculture",),
)
GOVT = _record(
    "AUTHORITY/secretariat",
    "AUTHORITY",
    "Government secretariat building Delhi",
    tags=("government", "ministry", "official", "bureaucracy"),
    domains=("governance",),
)
CLOCK = _record(
    "DEADLINE/clock",
    "DEADLINE",
    "Wall clock closeup",
    tags=("clock", "deadline", "calendar", "hourglass"),
    domains=("time",),
)
# Same subject as FARM but filed under AUTHORITY, so the category filter has to
# do real work to separate them -- a filter that is only ever handed one
# candidate per category cannot fail.
FARM_OFFICE = _record(
    "AUTHORITY/agri-office",
    "AUTHORITY",
    "Agriculture department office",
    tags=("farmer", "agriculture", "office"),
    domains=("agriculture",),
)

ALL_RECORDS = [FARM, GOVT, CLOCK, FARM_OFFICE]


@pytest.fixture
def vector_store(tmp_path, monkeypatch):
    """A throwaway Chroma index driven by the deterministic fake embedder."""
    persist = tmp_path / "chroma"
    monkeypatch.setattr(store, "CHROMA_DIR", persist)
    monkeypatch.setattr(embeddings, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(embeddings, "embed_query", _fake_embed_query)
    yield store
    # Drop the per-path client so a later test never reuses a handle to a tmp
    # dir pytest is about to delete.
    store._COLLECTIONS.pop(str(persist), None)
    store._CLIENTS.pop(str(persist), None)


# --- indexing -------------------------------------------------------------


def test_upsert_writes_every_record(vector_store):
    assert vector_store.upsert_assets(ALL_RECORDS) == len(ALL_RECORDS)
    assert vector_store.count() == len(ALL_RECORDS)


def test_upsert_of_nothing_is_a_no_op(vector_store):
    assert vector_store.upsert_assets([]) == 0
    assert vector_store.count() == 0


def test_upsert_is_idempotent(vector_store):
    """Re-running the build script must refresh, not duplicate or explode."""
    vector_store.upsert_assets(ALL_RECORDS)
    first = vector_store.count()
    vector_store.upsert_assets(ALL_RECORDS)
    assert vector_store.count() == first


def test_upsert_refreshes_changed_metadata(vector_store):
    vector_store.upsert_assets([FARM])
    renamed = _record(FARM.asset_id, FARM.category, "Paddy fields at dawn", tags=FARM.tags)
    vector_store.upsert_assets([renamed])

    hits = vector_store.query("farmer agriculture crop irrigation", n_results=1)
    assert hits[0][0].title == "Paddy fields at dawn"
    assert vector_store.count() == 1


def test_reset_empties_the_collection(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    vector_store.reset()
    assert vector_store.count() == 0


# --- retrieval ------------------------------------------------------------


def test_query_returns_the_intended_record(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    hits = vector_store.query("farmer agriculture crop irrigation land", n_results=3)
    assert hits, "expected at least one hit"
    assert hits[0][0].asset_id == FARM.asset_id


def test_query_discriminates_between_subjects(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    top = vector_store.query("clock calendar deadline hourglass", n_results=1)[0][0]
    assert top.asset_id == CLOCK.asset_id


def test_query_respects_n_results(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    assert len(vector_store.query("agriculture", n_results=2)) <= 2


def test_category_filter_restricts_results(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    hits = vector_store.query(
        "farmer agriculture crop irrigation land", n_results=4, category="AUTHORITY"
    )
    assert hits, "the filter should not empty an index that has AUTHORITY assets"
    assert {r.category for r, _ in hits} == {"AUTHORITY"}
    assert FARM.asset_id not in {r.asset_id for r, _ in hits}


def test_scores_are_bounded_and_descending(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    hits = vector_store.query("agriculture government clock", n_results=4)
    scores = [s for _, s in hits]
    assert scores, "expected scored hits"
    assert all(0.0 <= s <= 1.0 for s in scores), scores
    assert scores == sorted(scores, reverse=True), scores


def test_exact_document_text_scores_near_one(vector_store):
    """score = 1 - cosine_distance, so an identical vector must land at 1.0."""
    vector_store.upsert_assets([FARM])
    _, score = vector_store.query(FARM.embedding_text(), n_results=1)[0]
    assert score == pytest.approx(1.0, abs=1e-4)


def test_empty_query_returns_nothing(vector_store):
    vector_store.upsert_assets(ALL_RECORDS)
    assert vector_store.query("   ", n_results=3) == []


def test_query_on_an_empty_index_degrades_quietly(vector_store):
    """No index yet is the normal state before the build script runs."""
    assert vector_store.query("anything at all", n_results=3) == []


# --- availability ---------------------------------------------------------


def test_store_is_available_reports_false_when_chromadb_is_missing(tmp_path, monkeypatch):
    """The pipeline asks this to choose vector vs fuzzy search; it may not raise."""
    monkeypatch.setattr(store, "CHROMA_DIR", tmp_path / "chroma")

    def _missing():
        raise ImportError("No module named 'chromadb'")

    monkeypatch.setattr(store, "_chromadb", _missing)
    assert store.is_available() is False
    assert store.count() == 0
    assert store.query("farmer", n_results=3) == []


def test_embeddings_is_available_reports_false_when_model_cannot_load(monkeypatch):
    monkeypatch.setattr(embeddings, "_MODEL", None)
    monkeypatch.setattr(embeddings, "_LOAD_FAILED", False)

    def _missing():
        raise ImportError("No module named 'sentence_transformers'")

    monkeypatch.setattr(embeddings, "_sentence_transformers", _missing)
    assert embeddings.is_available() is False


def test_embeddings_module_constants_match_the_model():
    assert embeddings.MODEL_NAME == "all-MiniLM-L6-v2"
    assert embeddings.EMBED_DIM == 384


# --- metadata round-trip --------------------------------------------------


def test_metadata_round_trip_preserves_sequences():
    """Chroma stores flat scalars only, so tags and domains survive as joined
    strings -- the split back has to give the tuples again, not one long one."""
    restored = AssetRecord.from_metadata(FARM.as_metadata())

    assert restored.asset_id == FARM.asset_id
    assert restored.path == FARM.path
    assert restored.media_type == FARM.media_type
    assert restored.category == FARM.category
    assert restored.title == FARM.title
    assert restored.tags == FARM.tags
    assert restored.domains == FARM.domains
    assert restored.licence == FARM.licence
    assert restored.artist == FARM.artist
    assert restored.source_page == FARM.source_page
    assert restored.width == FARM.width
    assert restored.height == FARM.height
    assert restored.duration_sec == pytest.approx(FARM.duration_sec)


def test_metadata_round_trip_of_a_video_keeps_duration():
    clip = AssetRecord(
        asset_id="DEADLINE/countdown",
        path=Path("assets/broll/library/DEADLINE/countdown.mp4"),
        media_type="video",
        category="DEADLINE",
        title="Countdown timer",
        tags=("timer",),
        duration_sec=4.25,
    )
    restored = AssetRecord.from_metadata(clip.as_metadata())
    assert restored.media_type == "video"
    assert restored.duration_sec == pytest.approx(4.25, abs=1e-3)


def test_empty_sequences_round_trip_to_empty_tuples():
    bare = AssetRecord(
        asset_id="X/y", path=Path("y.jpg"), media_type="image", category="X", title="Y"
    )
    restored = AssetRecord.from_metadata(bare.as_metadata())
    assert restored.tags == ()
    assert restored.domains == ()


def test_a_stored_record_survives_the_index(vector_store):
    """End to end: the record that comes back out of Chroma is the one that
    went in, not a stub built from the document text."""
    vector_store.upsert_assets([FARM])
    hit, _ = vector_store.query(FARM.embedding_text(), n_results=1)[0]
    assert hit.asset_id == FARM.asset_id
    assert hit.tags == FARM.tags
    assert hit.domains == FARM.domains
    assert hit.width == FARM.width
