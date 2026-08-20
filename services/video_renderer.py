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
)

WIDTH = 1920
HEIGHT = 1080
FPS = 24

LOCAL_FONTS_DIR = Path("assets/fonts")

FONT_MAPPING = {
    "hi": LOCAL_FONTS_DIR / "NotoSansDevanagari-Bold.ttf",
    "ta": LOCAL_FONTS_DIR / "NotoSansTamil-Bold.ttf",
    "te": LOCAL_FONTS_DIR / "NotoSansTelugu-Bold.ttf",
    "en": LOCAL_FONTS_DIR / "NotoSans-Bold.ttf",
}


def get_font_for_lang(lang: str, size: int) -> ImageFont.FreeTypeFont:
  font_file = FONT_MAPPING.get(lang, FONT_MAPPING["en"])

  if font_file.exists():
    return ImageFont.truetype(str(font_file), size)

  # Fallback to standard Windows Nirmala if assets folder missing
  win_nirmala = Path("C:/Windows/Fonts/NirmalaB.ttf")
  if win_nirmala.exists():
    return ImageFont.truetype(str(win_nirmala), size)

  return ImageFont.load_default()


def render_scene_card_image(
    scene: SceneDefinition, lang: str = "en"
) -> np.ndarray:
  img = Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))
  draw = ImageDraw.Draw(img)

  card_x0, card_y0 = 120, 100
  card_x1, card_y1 = WIDTH - 120, HEIGHT - 220

  # Background Container Box
  draw.rounded_rectangle(
      [card_x0, card_y0, card_x1, card_y1],
      radius=24,
      fill=(30, 41, 59),
      outline=(71, 85, 105),
      width=2,
  )

  # 1. Badge Tag
  vh = scene.visual_hierarchy
  font_badge = get_font_for_lang(lang, 24)
  badge_text = f"  {vh.badge_tag}  "
  draw.rounded_rectangle(
      [card_x0 + 60, card_y0 + 50, card_x0 + 60 + 460, card_y0 + 105],
      radius=8,
      fill=(37, 99, 235),
  )
  draw.text(
      (card_x0 + 75, card_y0 + 60),
      badge_text,
      font=font_badge,
      fill=(255, 255, 255),
  )

  # 2. Headline & Subtext
  font_head = get_font_for_lang(lang, 44)
  font_sub = get_font_for_lang(lang, 26)
  draw.text(
      (card_x0 + 60, card_y0 + 135),
      vh.headline,
      font=font_head,
      fill=(255, 255, 255),
  )
  draw.text(
      (card_x0 + 60, card_y0 + 215),
      vh.subtext,
      font=font_sub,
      fill=(148, 163, 184),
  )

  # 3. Metric Highlight Box
  if vh.highlight_metric:
    metric_y = card_y0 + 310
    draw.rounded_rectangle(
        [card_x0 + 60, metric_y, card_x1 - 60, metric_y + 190],
        radius=16,
        fill=(15, 23, 42),
        outline=(245, 158, 11),
        width=3,
    )
    font_metric = get_font_for_lang(lang, 52)
    draw.text(
        (card_x0 + 100, metric_y + 35),
        vh.highlight_metric,
        font=font_metric,
        fill=(251, 191, 36),
    )
    if vh.highlight_sublabel:
      font_metric_sub = get_font_for_lang(lang, 26)
      draw.text(
          (card_x0 + 100, metric_y + 120),
          vh.highlight_sublabel,
          font=font_metric_sub,
          fill=(203, 213, 225),
      )

  # 4. Spoken Subtitle Bar
  sub_y = HEIGHT - 180
  draw.rounded_rectangle(
      [140, sub_y, WIDTH - 140, sub_y + 80],
      radius=12,
      fill=(10, 15, 30),
  )
  font_sub_preview = get_font_for_lang(lang, 24)
  display_text = (
      scene.full_spoken_text[:90] + "..."
      if len(scene.full_spoken_text) > 90
      else scene.full_spoken_text
  )
  draw.text(
      (170, sub_y + 24),
      display_text,
      font=font_sub_preview,
      fill=(226, 232, 240),
  )

  return np.array(img)


def build_scene_clip(scene: SceneDefinition, lang: str = "en") -> ImageClip:
  duration = scene.scene_duration_sec or 5.0
  card_array = render_scene_card_image(scene, lang=lang)

  clip = ImageClip(card_array).with_duration(duration).with_fps(FPS)

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

  scene_clips = [build_scene_clip(scene, lang=lang) for scene in scenes]
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