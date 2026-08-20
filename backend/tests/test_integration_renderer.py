"""Integration: the compositor must satisfy the contract server.py depends on.

These cover the seams that broke when the compositor met the pipeline —
schema field availability, the video_loop asset fallback, and web-style
audio paths — without rendering a full video (that is slow; see
scripts/render_fixture_demo.py for the end-to-end render).
"""

import pytest

from compositor import layers
from models.schemas import SceneDefinition, VisualAssetSelection
from tests.fixtures.scenes_en_fixture import get_fixture_scenes


def test_asset_carries_accent_color():
    """The compositor reads asset.accent_color for card glow and gradient tint."""
    for scene in get_fixture_scenes():
        assert scene.asset.accent_color.startswith("#")
        assert len(scene.asset.accent_color) == 7


def test_video_loop_asset_falls_back_to_gradient():
    """scene_generator emits video_loop paths for B-roll that isn't in the repo
    yet; §10.2 says fall back to a tinted gradient rather than fail."""
    asset = VisualAssetSelection(
        asset_id="broll_bank_01",
        asset_type="video_loop",
        file_path="assets/broll/does_not_exist.mp4",
        accent_color="#38BDF8",
        dim_overlay_opacity=0.70,
    )
    img = layers.build_background_source(asset, 320, 180)
    assert img.width >= 320 and img.height >= 180


def test_static_graphic_asset_also_falls_back():
    asset = VisualAssetSelection(
        asset_id="graphic_01",
        asset_type="static_graphic",
        file_path="assets/graphics/missing.png",
    )
    img = layers.build_background_source(asset, 320, 180)
    assert img.width >= 320


@pytest.mark.parametrize("audio_path", [None, "", "/static/audio/missing.mp3"])
def test_unresolvable_audio_paths_return_none(audio_path):
    assert layers.resolve_audio_path(audio_path) is None


def test_web_style_audio_path_resolves(tmp_path, monkeypatch):
    """Synthesis records audio_path as '/static/audio/x.mp3'; the file lives at
    'static/audio/x.mp3' relative to the server's working directory."""
    monkeypatch.chdir(tmp_path)
    served = tmp_path / "static" / "audio"
    served.mkdir(parents=True)
    (served / "scene_1_en.mp3").write_bytes(b"stub")

    resolved = layers.resolve_audio_path("/static/audio/scene_1_en.mp3")
    assert resolved is not None
    assert resolved.name == "scene_1_en.mp3"


def test_fixture_scenes_satisfy_media_invariant():
    """README §7.4 invariant 1, enforced by the shared schema's validator."""
    for scene in get_fixture_scenes():
        assert isinstance(scene, SceneDefinition)
        assert scene.audio_path and scene.scene_duration_sec and scene.subtitles


def test_per_scene_presenter_reaches_the_frame(monkeypatch):
    """render_job resolves the presenter per scene (each scene has its own
    audio, so each gets its own lip-synced clip) and passes presenter_source
    as None to say so. The source render_scene_clip resolves must actually be
    the one composited — otherwise the narrator silently vanishes from every
    render while every layer around it still looks correct.
    """
    scene = get_fixture_scenes()[0]

    class _Layout:
        content_box = (0, 0, 10, 10)
        panel_box = (0, 0, 10, 10)

    class _Source:
        clip_path = None
        pasted = False

        def paste_onto(self, frame, box, t, track=None):
            _Source.pasted = True

    monkeypatch.setattr(layers, "resolve_presenter", lambda *a, **k: (_Source(), _Layout()))

    captured = {}
    real_make = layers.make_frame_function

    def _spy(*args, **kwargs):
        captured["presenter_source"] = kwargs.get("presenter_source")
        return real_make(*args, **kwargs)

    monkeypatch.setattr(layers, "make_frame_function", _spy)

    layers.render_scene_clip(
        scene, "en", 0, (320, 180), presenter_source=None, presenter_layout=_Layout()
    )

    assert captured["presenter_source"] is not None, (
        "presenter resolved for the scene was dropped before compositing"
    )
