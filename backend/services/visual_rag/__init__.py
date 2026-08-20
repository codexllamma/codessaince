"""Retrieval-augmented visual selection.

Picking the background for a scene is a retrieval problem: given what the
narrator is about to say, find the asset whose metadata best describes it.
Three strategies sit behind one interface, tried in order and each degrading
into the next, so the pipeline keeps working when the layer above is missing:

    vector  -- MiniLM sentence embeddings in ChromaDB; matches meaning, so
               "eligible farmer families" can find an asset described as
               "smallholder agriculture", with no shared words at all
    fuzzy   -- rapidfuzz over the sidecar JSON; no model, no index, no
               network. Catches typos and morphology ("farmers"/"farming")
    tags    -- the original exact-substring tag scoring in image_library.py

The vector layer needs a model download and a built index; the fuzzy layer
needs neither and is always available. That ordering is deliberate: the demo
must still select sensible visuals on a machine that has never run the
indexer.
"""

from services.visual_rag.catalog import (  # noqa: F401
    AssetRecord,
    load_catalog,
    reload_catalog,
    scan_library,
)

__all__ = ["AssetRecord", "load_catalog", "reload_catalog", "scan_library"]
