"""Avatar registry resolution and its two non-negotiable rules."""

import json

import pytest
from PIL import Image

from compositor import layers, presenter
from services import avatar_registry


def _write_manifest(tmp_path, avatars, make_files=True):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"avatars": avatars}), encoding="utf-8")
    if make_files:
        for a in avatars:
            (tmp_path / a["file"]).write_bytes(b"stub")
    avatar_registry.load_registry.cache_clear()
    return str(manifest)


def _entry(avatar_id="pres_01", languages=("hi",), source="synthetic", **over):
    entry = {
        "avatar_id": avatar_id,
        "file": f"{avatar_id}.mp4",
        "languages": list(languages),
        "display_name": "Test Presenter",
        "source": source,
        "licence": "CC0 / synthetic, no real person depicted",
        "disclosure_label": "AI-GENERATED PRESENTER",
    }
    entry.update(over)
    return entry


def test_no_manifest_resolves_to_none(tmp_path):
    """The pipeline must work before any presenter exists."""
    avatar_registry.load_registry.cache_clear()
    assert avatar_registry.resolve("hi", str(tmp_path / "absent.json")) is None


def test_empty_manifest_resolves_to_none(tmp_path):
    path = _write_manifest(tmp_path, [])
    assert avatar_registry.resolve("hi", path) is None


def test_resolves_exact_language(tmp_path):
    path = _write_manifest(tmp_path, [_entry("hi_01", ["hi"]), _entry("ta_01", ["ta"])])
    assert avatar_registry.resolve("hi", path).avatar_id == "hi_01"
    assert avatar_registry.resolve("ta", path).avatar_id == "ta_01"


def test_falls_back_to_catch_all(tmp_path):
    path = _write_manifest(tmp_path, [_entry("hi_01", ["hi"]), _entry("any_01", ["*"])])
    assert avatar_registry.resolve("bn", path).avatar_id == "any_01"


def test_unmatched_language_resolves_to_none(tmp_path):
    path = _write_manifest(tmp_path, [_entry("hi_01", ["hi"])])
    assert avatar_registry.resolve("bn", path) is None


def test_manifest_entry_without_file_on_disk_is_skipped(tmp_path):
    """A packaging mistake must degrade to the normal layout, not fail a render."""
    path = _write_manifest(tmp_path, [_entry("ghost_01", ["hi"])], make_files=False)
    assert avatar_registry.resolve("hi", path) is None


def test_real_person_source_is_rejected(tmp_path):
    """Animating a named official's likeness is refused at load time."""
    path = _write_manifest(tmp_path, [_entry(source="real_official")])
    with pytest.raises(avatar_registry.AvatarManifestError, match="real"):
        avatar_registry.resolve("hi", path)


@pytest.mark.parametrize("field", ["licence", "disclosure_label", "source"])
def test_required_disclosure_fields_are_enforced(tmp_path, field):
    path = _write_manifest(tmp_path, [_entry(**{field: ""})])
    with pytest.raises(avatar_registry.AvatarManifestError, match=field):
        avatar_registry.resolve("hi", path)


def test_presenter_panel_requires_a_disclosure_label():
    """There is no code path that renders an unlabelled synthetic presenter."""
    layout = presenter.compute_layout((1920, 1080), caption_reserve=240)
    frame = Image.new("RGB", (720, 1280), (40, 40, 40))
    with pytest.raises(ValueError, match="disclosure_label"):
        presenter.build_presenter_panel(frame, "", layout)


def test_presenter_panel_carries_the_label_and_fits_the_panel():
    layout = presenter.compute_layout((1920, 1080), caption_reserve=240)
    frame = Image.new("RGB", (720, 1280), (40, 40, 40))
    panel = presenter.build_presenter_panel(frame, "AI-GENERATED PRESENTER", layout)
    assert panel.size == layout.panel_size


PLACEHOLDER = avatar_registry.AVATARS_DIR / "placeholder_m01.mp4"
needs_placeholder = pytest.mark.skipif(
    not PLACEHOLDER.is_file(), reason="placeholder avatar clip not present"
)


@needs_placeholder
def test_presenter_source_loads_and_wraps_around():
    """A short loop must cover a longer scene by wrapping, not running out."""
    layout = presenter.compute_layout((1920, 1080), caption_reserve=238)
    src = presenter.PresenterSource.load(
        str(PLACEHOLDER), layout, "AI-GENERATED PRESENTER", "en"
    )
    assert len(src.frames) > 0
    assert src.frames[0].size == layout.panel_size

    loop_len = len(src.frames) / src.sample_fps
    # Well past the end of the clip: must wrap, not raise or clamp.
    assert src.frame_at(loop_len * 3 + 1.7) is not None
    assert src.frame_at(0.0) is src.frame_at(loop_len)


@needs_placeholder
def test_scene_renders_with_presenter_active():
    from tests.fixtures.scenes_en_fixture import get_fixture_scenes

    canvas = (1920, 1080)
    layout = presenter.compute_layout(canvas, caption_reserve=238)
    src = presenter.PresenterSource.load(str(PLACEHOLDER), layout, "AI-GENERATED PRESENTER", "en")

    scene = get_fixture_scenes()[1]
    clip = layers.render_scene_clip(scene, "en", 0, canvas, src, layout)
    try:
        frame = clip.get_frame(1.0)
        assert frame.shape == (1080, 1920, 3)
    finally:
        clip.close()


def test_resolve_presenter_is_none_when_no_avatar(monkeypatch):
    """With no avatar installed the compositor must fall back silently."""
    monkeypatch.setattr(avatar_registry, "resolve", lambda lang, manifest_path=None: None)
    src, layout = layers.resolve_presenter("en", (1920, 1080))
    assert src is None and layout is None


def test_broken_avatar_degrades_instead_of_failing_render(monkeypatch, tmp_path):
    """A corrupt clip should cost the presenter, not the whole video."""
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"not a video")
    fake = avatar_registry.Avatar(
        avatar_id="broken_01", file_path=bad, languages=("en",),
        display_name="Broken", source="synthetic", licence="n/a",
        disclosure_label="AI-GENERATED PRESENTER",
    )
    monkeypatch.setattr(avatar_registry, "resolve", lambda lang, manifest_path=None: fake)
    src, layout = layers.resolve_presenter("en", (1920, 1080))
    assert src is None and layout is None


def test_content_box_keeps_static_layers_clear_of_the_presenter():
    """Fact-card layers must not stray into the presenter panel."""
    from tests.fixtures.scenes_en_fixture import get_fixture_scenes

    canvas = (1920, 1080)
    layout = presenter.compute_layout(canvas, caption_reserve=238)
    scene = get_fixture_scenes()[1]
    built = layers.build_static_layers(scene, "en", canvas, layout.content_box)

    panel_right = layout.panel_box[2]
    for name, layer in built.items():
        bbox = layer.getbbox()
        if bbox is None:
            continue
        assert bbox[0] >= panel_right, f"{name} starts at x={bbox[0]}, inside the presenter panel"


def test_layout_leaves_room_for_captions_and_content():
    W, H = 1920, 1080
    reserve = 240
    layout = presenter.compute_layout((W, H), caption_reserve=reserve)
    assert layout.panel_box[3] <= H - reserve
    assert layout.content_box[3] <= H - reserve
    # Panels must not overlap, or the fact card would sit on the presenter.
    assert layout.content_box[0] > layout.panel_box[2]
    assert layout.content_width > 0
