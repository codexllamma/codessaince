"""B-roll background handling: stills, clips, and the §10.2 fallback.

Assets are generated into tmp_path rather than committed, so these run on a
clone with an empty assets/broll/ — which is the current state of the repo.
"""

import numpy as np
import pytest
from PIL import Image

from compositor import kenburns, layers
from models.schemas import VisualAssetSelection

CANVAS = (1920, 1080)
HEADROOM = (
    round(kenburns.Z_MAX_DEFAULT * CANVAS[0]),
    round(kenburns.Z_MAX_DEFAULT * CANVAS[1]),
)


def _asset(tmp_path, name, asset_type, **over):
    fields = {
        "asset_id": name,
        "asset_type": asset_type,
        "file_path": str(tmp_path / name),
        "accent_color": "#22C55E",
        "dim_overlay_opacity": 0.65,
    }
    fields.update(over)
    return VisualAssetSelection(**fields)


def _write_still(tmp_path, name, size=(2560, 1440), colour=(200, 180, 60)):
    Image.new("RGB", size, colour).save(tmp_path / name)
    return tmp_path / name


def _write_clip(tmp_path, name, size=(1920, 1080), n=15, fps=15):
    from moviepy import ImageSequenceClip

    from compositor import _ffmpeg

    _ffmpeg.ensure_ffmpeg_binary_env()
    frames = [
        np.full((size[1], size[0], 3), (30 + i * 8) % 255, dtype=np.uint8) for i in range(n)
    ]
    ImageSequenceClip(frames, fps=fps).write_videofile(
        str(tmp_path / name), codec="libx264", pixel_format="yuv420p", logger=None
    )
    return tmp_path / name


# --- stills ---------------------------------------------------------------


def test_static_graphic_is_fitted_to_kenburns_headroom(tmp_path):
    """Stills must exceed the output size so Ken Burns can pan without upscaling."""
    _write_still(tmp_path, "field.png")
    img = layers.build_background_source(_asset(tmp_path, "field.png", "static_graphic"))
    assert img.size == HEADROOM


def test_static_graphic_content_reaches_the_frame(tmp_path):
    """The still itself must survive, not just its dimensions.

    Asserting only on size passes just as happily when build_background_source
    ignores the asset and returns the procedural gradient — which is exactly
    how the B-roll still path was once dropped without a test going red.
    """
    _write_still(tmp_path, "magenta.png", colour=(255, 0, 255))
    img = layers.build_background_source(
        _asset(tmp_path, "magenta.png", "static_graphic", dim_overlay_opacity=0.0)
    )
    arr = np.asarray(img.convert("RGB")).reshape(-1, 3).mean(axis=0)
    assert arr[0] > 200 and arr[2] > 200 and arr[1] < 60, f"still ignored; got {arr}"


def test_static_graphic_is_dimmed(tmp_path):
    """Undimmed B-roll destroys caption contrast (§8.6 layer 1)."""
    _write_still(tmp_path, "bright.png", colour=(255, 255, 255))
    bright = layers.build_background_source(
        _asset(tmp_path, "bright.png", "static_graphic", dim_overlay_opacity=0.0)
    )
    dimmed = layers.build_background_source(
        _asset(tmp_path, "bright.png", "static_graphic", dim_overlay_opacity=0.65)
    )
    assert np.asarray(dimmed.convert("RGB")).mean() < np.asarray(bright.convert("RGB")).mean()


def test_portrait_still_is_cover_fitted_not_letterboxed(tmp_path):
    """A bar down the side of a government notice reads as a mistake."""
    _write_still(tmp_path, "tall.png", size=(1440, 2560))
    img = layers.build_background_source(_asset(tmp_path, "tall.png", "static_graphic"))
    assert img.size == HEADROOM


def test_missing_still_falls_back_to_gradient(tmp_path):
    """§10.2: a scene never fails for want of an asset."""
    img = layers.build_background_source(_asset(tmp_path, "absent.png", "static_graphic"))
    assert img.size == HEADROOM


def test_unreadable_file_falls_back_to_gradient(tmp_path):
    (tmp_path / "corrupt.png").write_bytes(b"not an image")
    img = layers.build_background_source(_asset(tmp_path, "corrupt.png", "static_graphic"))
    assert img.size == HEADROOM


# --- clips ----------------------------------------------------------------


def test_video_loop_yields_output_sized_frames(tmp_path):
    """Clips are fitted straight to output size — Ken Burns is skipped for
    them, so they need no headroom."""
    _write_clip(tmp_path, "loop.mp4")
    bg = layers.build_background_video(_asset(tmp_path, "loop.mp4", "video_loop"))
    assert bg is not None
    try:
        frame = bg.frame_at(0.2)
        assert frame.size == CANVAS
        assert frame.mode == "RGB"
    finally:
        bg.close()


def test_video_loop_wraps_past_its_duration(tmp_path):
    """A 1s clip must still cover a 9s scene."""
    _write_clip(tmp_path, "short.mp4", n=15, fps=15)
    bg = layers.build_background_video(_asset(tmp_path, "short.mp4", "video_loop"))
    try:
        assert bg.duration == pytest.approx(1.0, abs=0.3)
        assert bg.frame_at(bg.duration * 8 + 0.3) is not None
    finally:
        bg.close()


def test_build_background_video_returns_none_for_non_clips(tmp_path):
    _write_still(tmp_path, "still.png")
    assert layers.build_background_video(_asset(tmp_path, "still.png", "static_graphic")) is None
    assert layers.build_background_video(_asset(tmp_path, "x", "mesh_gradient")) is None


def test_corrupt_clip_degrades_instead_of_raising(tmp_path):
    (tmp_path / "broken.mp4").write_bytes(b"not a video")
    assert layers.build_background_video(_asset(tmp_path, "broken.mp4", "video_loop")) is None


def test_scene_renders_over_a_video_loop(tmp_path):
    from tests.fixtures.scenes_en_fixture import get_fixture_scenes

    _write_clip(tmp_path, "scene.mp4")
    scene = get_fixture_scenes()[1]
    scene.asset = _asset(tmp_path, "scene.mp4", "video_loop")

    clip = layers.render_scene_clip(scene, "en", 0)
    try:
        assert clip.get_frame(1.0).shape == (1080, 1920, 3)
    finally:
        background = getattr(clip, "_broll_background", None)
        if background is not None:
            background.close()
        clip.close()
