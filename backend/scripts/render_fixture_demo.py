"""Standalone driver to exercise the compositor against hand-written fixture
data, since no upstream job/worker plumbing exists yet.

Usage:
    python scripts/render_fixture_demo.py static   # single static frame -> out/static_frame.png
    python scripts/render_fixture_demo.py motion    # Ken Burns motion only -> out/motion_test.mp4
    python scripts/render_fixture_demo.py caption    # captions over static bg at sampled t -> out/caption_frames/
    python scripts/render_fixture_demo.py scene      # full single-scene render -> out/scene1_en.mp4
    python scripts/render_fixture_demo.py job [codec] # full two-scene job -> out/notice_en.mp4 (codec: h264_nvenc|libx264)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compositor import kenburns, layers
from tests.fixtures.scenes_en_fixture import get_fixture_scenes

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def render_static_frame() -> None:
    scenes = get_fixture_scenes()
    scene = scenes[1]  # METRIC_FOCUS, exercises the metric card layer too
    bg = layers.build_background_source(scene.asset)
    static_layers = layers.build_static_layers(scene, "en")

    frame = kenburns.render_frame(bg, 0.0, scene.scene_duration_sec, layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT, *(bg.width / 2, bg.height / 2, bg.width / 2, bg.height / 2)).convert("RGBA")
    for key in ("metric_card", "headline_subtext", "alert_pill"):
        if key in static_layers:
            frame.alpha_composite(static_layers[key])

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "static_frame.png"
    frame.convert("RGB").save(out_path)
    print(f"Wrote {out_path}")


def render_motion_test() -> None:
    scenes = get_fixture_scenes()
    scene = scenes[0]  # HERO_ANNOUNCEMENT, drifts right
    bg = layers.build_background_source(scene.asset)
    pan_targets = kenburns.pan_targets_for_template(scene.template_type.value, *bg.size)

    from moviepy import VideoClip

    def frame_function(t):
        import numpy as np
        img = kenburns.render_frame(bg, t, scene.scene_duration_sec, layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT, *pan_targets)
        return np.asarray(img.convert("RGB"))

    clip = VideoClip(frame_function=frame_function, duration=scene.scene_duration_sec).with_fps(layers.VIDEO_FPS)
    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "motion_test.mp4"
    from compositor import _ffmpeg
    _ffmpeg.ensure_ffmpeg_binary_env()
    clip.write_videofile(str(out_path), fps=layers.VIDEO_FPS, codec="libx264", preset="veryfast", pixel_format="yuv420p")
    print(f"Wrote {out_path}")


def render_caption_frames() -> None:
    from compositor import karaoke

    scenes = get_fixture_scenes()
    scene = scenes[1]
    bg = layers.build_background_source(scene.asset)
    frame0 = kenburns.render_frame(bg, 0.0, scene.scene_duration_sec, layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT, bg.width / 2, bg.height / 2, bg.width / 2, bg.height / 2)

    caption_layout = karaoke.build_caption_layout(scene.subtitles, "en", (layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT))
    cache = karaoke.build_caption_frame_cache(caption_layout)

    out_dir = OUT_DIR / "caption_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_times = [0.0, 1.0, 1.75, 2.6, 3.5, 4.5]
    for t in sample_times:
        frame = frame0.convert("RGBA").copy()
        frame.alpha_composite(karaoke.get_caption_frame_for_time(cache, t))
        out_path = out_dir / f"t_{t:.2f}.png"
        frame.convert("RGB").save(out_path)
        print(f"Wrote {out_path}")


def render_single_scene() -> None:
    scenes = get_fixture_scenes()
    scene = scenes[1]
    clip = layers.render_scene_clip(scene, "en", 0)
    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "scene1_en.mp4"
    from compositor import _ffmpeg
    _ffmpeg.ensure_ffmpeg_binary_env()
    layers._write_with_fallback(clip, str(out_path), "libx264")
    print(f"Wrote {out_path}")


def render_job(codec_pref: str = "h264_nvenc") -> None:
    scenes = get_fixture_scenes()
    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "notice_en.mp4"
    layers.render_job(scenes, "en", str(out_path), codec_pref=codec_pref)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mode = sys.argv[1] if len(sys.argv) > 1 else "static"
    if mode == "static":
        render_static_frame()
    elif mode == "motion":
        render_motion_test()
    elif mode == "caption":
        render_caption_frames()
    elif mode == "scene":
        render_single_scene()
    elif mode == "job":
        render_job(sys.argv[2] if len(sys.argv) > 2 else "h264_nvenc")
    else:
        print(__doc__)
        sys.exit(1)
