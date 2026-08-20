import asyncio
from pathlib import Path
from typing import List, Tuple
import edge_tts
import soundfile as sf

from models.schemas import (
    NoticeVideoJob,
    SceneDefinition,
    WordTimestamp,
)

VOICE_MAPPING = {
    "en": "en-IN-PrabhatNeural",
    "hi": "hi-IN-MadhurNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "bn": "bn-IN-BashkarNeural",
    "mr": "mr-IN-ManoharNeural",
}


def generate_fallback_timestamps(
    text: str, duration_sec: float, script_segments
) -> List[WordTimestamp]:
  words = text.split()
  if not words:
    return []

  fact_words = set()
  for seg in script_segments:
    if seg.type == "core_fact":
      for token in seg.text.split():
        fact_words.add(token.strip(".,;:!?()").lower())

  time_per_word = duration_sec / len(words)
  timestamps: List[WordTimestamp] = []

  for idx, w in enumerate(words):
    start = round(idx * time_per_word, 3)
    end = round((idx + 1) * time_per_word, 3)
    clean_w = w.strip(".,;:!?()").lower()
    timestamps.append(
        WordTimestamp(
            word=w,
            start_sec=start,
            end_sec=end,
            is_core_fact=(clean_w in fact_words),
        )
    )

  return timestamps


async def synthesize_scene(
    scene: SceneDefinition,
    job_id: str,
    lang: str,
    voice_id: str,
    speed_mod: str,
    output_dir: Path,
) -> Tuple[str, float, List[WordTimestamp]]:
  file_name = f"{job_id}_{lang}_scene_{scene.scene_id}.mp3"
  file_path = output_dir / file_name

  communicate = edge_tts.Communicate(
      text=scene.full_spoken_text,
      voice=voice_id,
      rate=speed_mod,
  )

  raw_subtitles: List[WordTimestamp] = []

  with open(file_path, "wb") as audio_file:
    async for chunk in communicate.stream():
      if chunk["type"] == "audio":
        audio_file.write(chunk["data"])
      elif chunk["type"] == "WordBoundary":
        start_sec = chunk["offset"] / 10_000_000.0
        end_sec = (chunk["offset"] + chunk["duration"]) / 10_000_000.0
        raw_subtitles.append(
            WordTimestamp(
                word=chunk["text"],
                start_sec=round(start_sec, 3),
                end_sec=round(end_sec, 3),
                is_core_fact=False,
            )
        )

  info = sf.info(str(file_path))
  duration_sec = round(float(info.duration), 3)

  # Fallback to linear distribution if TTS engine provided 0 boundary events
  if not raw_subtitles:
    raw_subtitles = generate_fallback_timestamps(
        scene.full_spoken_text, duration_sec, scene.script_segments
    )
  else:
    fact_words = set()
    for seg in scene.script_segments:
      if seg.type == "core_fact":
        for token in seg.text.split():
          fact_words.add(token.strip(".,;:!?()").lower())

    for sub in raw_subtitles:
      clean_sub = sub.word.strip(".,;:!?()").lower()
      if clean_sub in fact_words:
        sub.is_core_fact = True

  return f"/static/audio/{file_name}", duration_sec, raw_subtitles


async def process_job_audio(job: NoticeVideoJob) -> NoticeVideoJob:
  output_dir = Path("static/audio")
  output_dir.mkdir(parents=True, exist_ok=True)

  en_voice = VOICE_MAPPING.get("en", "en-IN-PrabhatNeural")
  for scene in job.master_scenes_en:
    audio_path, duration, subs = await synthesize_scene(
        scene=scene,
        job_id=job.job_id,
        lang="en",
        voice_id=en_voice,
        speed_mod=job.voice_speed_modifier,
        output_dir=output_dir,
    )
    scene.audio_path = audio_path
    scene.scene_duration_sec = duration
    scene.subtitles = subs

  for lang, scenes in job.localized_scenes.items():
    voice = VOICE_MAPPING.get(lang, job.selected_voice_id)
    for scene in scenes:
      audio_path, duration, subs = await synthesize_scene(
          scene=scene,
          job_id=job.job_id,
          lang=lang,
          voice_id=voice,
          speed_mod=job.voice_speed_modifier,
          output_dir=output_dir,
      )
      scene.audio_path = audio_path
      scene.scene_duration_sec = duration
      scene.subtitles = subs

  return job