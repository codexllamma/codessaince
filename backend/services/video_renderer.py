"""Final video rendering for a NoticeVideoJob.

This module keeps the public contract server.py depends on
(`render_notice_video(job, lang) -> url`) and delegates the actual frame
work to compositor/, which implements README section 8.6 properly:
Ken Burns motion, word-level karaoke captions, the 5-layer canvas, bundled
Noto fonts, and yuv420p output.

Per-language font selection lives in compositor/typography.py (FONT_FILES),
not here, so every layer — headline, subtext, metric card, badge pill and
captions — resolves the same face for a given language. Section 5.4 forbids
OS-resolved fonts entirely: a fallback to C:/Windows/Fonts only works on the
machine that has it, and silently produces tofu everywhere else.
"""

from pathlib import Path

import numpy as np

from compositor import layers
from models.schemas import NoticeVideoJob, SceneDefinition

OUTPUT_DIR = Path("static/videos")


def render_scene_card_image(scene: SceneDefinition, lang: str = "en") -> np.ndarray:
  """A single still frame of `scene`, as an RGB array.

  Used by the /api/test/preview-card endpoint. Built from the same layer
  stack as the video (minus motion and captions, which need a time), so a
  preview shows the real typography rather than an approximation of it.
  """
  canvas = (layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT)
  frame = layers.build_background_source(scene.asset, *canvas)
  frame = frame.crop((0, 0, *canvas)).convert("RGBA")

  static_layers = layers.build_static_layers(scene, lang, canvas)
  for key in ("metric_card", "headline_subtext", "alert_pill"):
    if key in static_layers:
      frame.alpha_composite(static_layers[key])

  return np.asarray(frame.convert("RGB"))


def render_notice_video(job: NoticeVideoJob, lang: str = "en") -> str:
  """Render every scene for `lang` into a single MP4. Returns the served URL."""
  scenes = (
      job.master_scenes_en if lang == "en" else job.localized_scenes.get(lang, [])
  )
  if not scenes:
    raise ValueError(f"No scenes found for language: {lang}")

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  output_filename = f"{job.job_id}_final_{lang}.mp4"
  output_path = OUTPUT_DIR / output_filename

  layers.render_job(scenes, lang, str(output_path))

  return f"/static/videos/{output_filename}"
