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

from compositor import layers
from models.schemas import NoticeVideoJob

OUTPUT_DIR = Path("static/videos")


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
