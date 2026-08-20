from pathlib import Path
from typing import List
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from models.schemas import (
    NoticeVideoJob,
    SceneDefinition,
    WordTimestamp,
)

WIDTH = 1920
HEIGHT = 1080
FPS = 24


def get_system_font(
    size: int, is_bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
  font_candidates = [
      "C:\\Windows\\Fonts\\arialbd.ttf" if is_bold else "C:\\Windows\\Fonts\\arial.ttf",
      "C:\\Windows\\Fonts\\NirmalaB.ttf"
      if is_bold
      else "C:\\Windows\\Fonts\\Nirmala.ttf",
      "C:\\Windows\\Fonts\\segoeui.ttf",
  ]
  for path in font_candidates:
    if Path(path).exists():
      try:
        return ImageFont.truetype(path, size)
      except Exception:
        continue
  return ImageFont.load_default()


def render_scene_card_image(scene: SceneDefinition) -> np.ndarray:
  img = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))
  draw = ImageDraw.Draw(img)

  card_x0, card_y0 = 120, 100
  card_x1, card_y1 = WIDTH - 120, HEIGHT - 220

  draw.rounded_rectangle(
      [card_x0, card_y0, card_x1, card_y1],
      radius=24,
      fill=(30, 41, 59),
      outline=(71, 85, 105),
      width=2,
  )

  # Badge Tag
  vh = scene.visual_hierarchy
  badge_text = f"  {vh.badge_tag.upper()}  "
  draw.rounded_rectangle(
      [card_x0 + 60, card_y0 + 50, card_x0 + 60 + 340, card_y0 + 105],
      radius=8,
      fill=(37, 99, 235),
  )
  draw.text((card_x0 + 75, card_y0 + 62), badge_text, fill=(255, 255, 255))

  # Headline & Subtext
  draw.text((card_x0 + 60, card_y0 + 140), vh.headline, fill=(255, 255, 255))
  draw.text((card_x0 + 60, card_y0 + 220), vh.subtext, fill=(148, 163, 184))

  # Metric Highlight Box
  if vh.highlight_metric:
    metric_y = card_y0 + 320
    draw.rounded_rectangle(
        [card_x0 + 60, metric_y, card_x1 - 60, metric_y + 180],
        radius=16,
        fill=(15, 23, 42),
        outline=(245, 158, 11),
        width=3,
    )
    draw.text(
        (card_x0 + 100, metric_y + 40),
        vh.highlight_metric,
        fill=(251, 191, 36),
    )
    if vh.highlight_sublabel:
      draw.text(
          (card_x0 + 100, metric_y + 120),
          vh.highlight_sublabel,
          fill=(203, 213, 225),
      )

  # Static Subtitle Preview Bar
  sub_y = HEIGHT - 180
  draw.rounded_rectangle(
      [140, sub_y, WIDTH - 140, sub_y + 80],
      radius=12,
      fill=(10, 15, 30),
  )
  display_text = (
      scene.full_spoken_text[:90] + "..."
      if len(scene.full_spoken_text) > 90
      else scene.full_spoken_text
  )
  draw.text((170, sub_y + 25), display_text, fill=(226, 232, 240))

  return np.array(img)


def build_scene_clip(scene: SceneDefinition) -> ImageClip:
  duration = scene.scene_duration_sec or 5.0
  card_array = render_scene_card_image(scene)

  clip = (
      ImageClip(card_array)
      .with_duration(duration)
      .with_fps(FPS)
  )

  if scene.audio_path:
    audio_full_path = Path(scene.audio_path.lstrip("/"))
    if audio_full_path.exists():
      audio_clip = AudioFileClip(str(audio_full_path))
      clip = clip.with_audio(audio_clip)

  return clip


def render_notice_video(job: NoticeVideoJob, lang: str = "en") -> str:
  scenes = (
      job.master_scenes_en if lang == "en" else job.localized_scenes.get(lang, [])
  )
  if not scenes:
    raise ValueError(f"No scenes found for language: {lang}")

  out_dir = Path("static/videos")
  out_dir.mkdir(parents=True, exist_ok=True)
  output_filename = f"{job.job_id}_final_{lang}.mp4"
  output_path = out_dir / output_filename

  scene_clips = [build_scene_clip(scene) for scene in scenes]
  final_video = concatenate_videoclips(scene_clips, method="compose")

  final_video.write_videofile(
      str(output_path),
      fps=FPS,
      codec="libx264",
      audio_codec="aac",
      preset="ultrafast",
      threads=1,
      logger=None,
  )

  final_video.close()
  for c in scene_clips:
    c.close()

  return f"/static/videos/{output_filename}"