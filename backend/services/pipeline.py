"""End-to-end continuous-narration pipeline.

The per-scene pipeline synthesises one audio file per scene and lip-syncs the
anchor once per scene. That makes the anchor restart at every cut: the head
snaps back to the clip's first frame and the voice re-attacks mid-sentence,
which is exactly the seam a news broadcast never has.

This assembles the video the other way round. The whole script is spoken once
as a single narration, the anchor is lip-synced once against that narration,
and the scenes only change what is *behind* him. The anchor and his voice are
one uninterrupted stream from the first frame to the last; the visuals cut
underneath.

    facts -> scenes -> one narration wav -> ping-pong anchor loop
          -> one Wav2Lip pass -> composite with per-scene backgrounds

Every stage logs what it produced, because when this goes wrong it tends to
go wrong quietly: a failed lip-sync falls back to a plain loop and still
renders a perfectly good-looking video with the wrong presenter in it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from models.schemas import ExtractedFact, SceneDefinition

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Wav2Lip is trained on 16 kHz mono speech; anything else is resampled
# internally anyway, so producing it directly avoids a lossy round trip.
NARRATION_SAMPLE_RATE = 16000


@dataclass
class PipelineResult:
  job_id: str
  lang: str
  video_path: Path
  narration_wav: Path
  anchor_loop: Path
  lipsync_video: Optional[Path]
  scenes: List[SceneDefinition]
  facts: List[ExtractedFact]
  total_duration_sec: float
  elapsed_sec: float
  used_lipsync: bool


def _banner(step: str, title: str) -> None:
  logger.info("")
  logger.info("=" * 68)
  logger.info("[%s] %s", step, title)
  logger.info("=" * 68)


def run_pipeline(
    raw_text: str = "",
    job_id: str = "pipeline_demo",
    lang: str = "en",
    out_path: Optional[Path] = None,
    codec_pref: str = "h264_nvenc",
    use_lipsync: bool = True,
    voice_id: Optional[str] = None,
    rate: str = "+0%",
    facts: Optional[List[ExtractedFact]] = None,
    avatar_id: Optional[str] = None,
) -> PipelineResult:
  """Run notice text all the way to a rendered MP4."""
  from compositor import layers, presenter as presenter_mod
  from services import anchor_loop, avatar_registry, narration
  from services.fact_extractor import FactExtractor
  from services.scene_generator import build_scenes_from_facts

  t0 = time.time()
  out_path = Path(out_path) if out_path else (BACKEND_DIR / "out" / f"{job_id}_{lang}.mp4")
  out_path.parent.mkdir(parents=True, exist_ok=True)
  work_dir = BACKEND_DIR / "static" / "avatars"
  work_dir.mkdir(parents=True, exist_ok=True)

  # ---------------------------------------------------------------- 1. facts
  _banner("1/7", "Fact extraction")
  if facts is None:
      logger.info("input text (%d chars): %s", len(raw_text), raw_text[:160])
      extractor = FactExtractor()
      facts = extractor.extract_facts(raw_text)
  else:
      logger.info("Using %d pre-extracted facts.", len(facts))
      
  if not facts:
    raise ValueError("no facts extracted; nothing to narrate")
  for f in facts:
    logger.info(
        "  %-16s %-42s conf=%.2f  chars[%d:%d]",
        f.category.value, f.normalized_value[:42],
        f.confidence_score, f.source_char_start, f.source_char_end,
    )

  # --------------------------------------------------------------- 2. scenes
  _banner("2/7", "Scene generation + visual retrieval")
  # Which retrieval layer answered is invisible in the finished video, so it
  # is worth stating: a run that silently fell back to fuzzy matching looks
  # exactly like one that used the vector index.
  try:
    from services.visual_rag import retriever as _visual_retriever

    logger.info("visual backends: %s", _visual_retriever.describe_backends())
  except Exception:
    logger.info("visual backends: retrieval unavailable, using tag scoring")

  scenes = build_scenes_from_facts(facts)
  for s in scenes:
    asset = s.asset
    logger.info(
        "  scene %d  %-22s asset=%s (%s)",
        s.scene_id, s.template_type.value, asset.asset_id, asset.asset_type,
    )
    for seg in s.script_segments:
      logger.info(
          "      %-9s emph=%-8s pause=%4dms  %s",
          seg.type, seg.emphasis_level, seg.pause_after_ms, seg.text[:64],
      )

  # ------------------------------------------------------------ 3. narration
  _banner("3/7", "Continuous narration (single stream)")
  narration_wav = work_dir / f"{job_id}_{lang}_narration.wav"
  timeline = narration.build_narration_sync(
      scenes=scenes,
      lang=lang,
      out_wav=narration_wav,
      voice_id=voice_id,
      rate=rate,
      sample_rate=NARRATION_SAMPLE_RATE,
  )
  logger.info(
      "narration: %s  %.2fs @ %d Hz mono",
      timeline.wav_path.name, timeline.total_duration_sec, timeline.sample_rate,
  )

  # Scene timings come from where the speech actually fell, so a caption can
  # never drift from the voice: both are derived from the same measurement.
  _banner("4/7", "Binding scene timings to the narration")
  by_id = {s.scene_id: s for s in scenes}
  for span in timeline.spans:
    scene = by_id[span.scene_id]
    scene.scene_duration_sec = round(span.end_sec - span.start_sec, 3)
    scene.subtitles = span.subtitles
    scene.audio_path = None  # the stream is global now, not per scene
    logger.info(
        "  scene %d  %7.2fs -> %7.2fs  (%5.2fs, %d words)",
        span.scene_id, span.start_sec, span.end_sec,
        scene.scene_duration_sec, len(span.subtitles),
    )

  total_scene_dur = sum(s.scene_duration_sec or 0.0 for s in scenes)
  drift = abs(total_scene_dur - timeline.total_duration_sec)
  logger.info("scene total %.2fs vs narration %.2fs (drift %.3fs)",
              total_scene_dur, timeline.total_duration_sec, drift)
  if drift > 0.25:
    logger.warning("scene durations and narration disagree by %.3fs; "
                   "captions will drift from the voice", drift)

  # ----------------------------------------------------------- 5. anchor loop
  _banner("5/7", "Ping-pong anchor loop")
  if avatar_id:
    registry = avatar_registry.load_registry()
    avatar = next((a for a in registry if a.avatar_id == avatar_id), None)
  else:
    avatar = avatar_registry.resolve(lang)
  if avatar is None:
    raise RuntimeError(f"no avatar registered or found for lang={lang!r}, avatar_id={avatar_id!r}")
  logger.info("avatar %r -> %s", avatar.avatar_id, avatar.file_path.name)
  logger.info("disclosure: %s", avatar.disclosure_label)

  loop_path = anchor_loop.ensure_anchor_loop(
      source=avatar.file_path,
      target_duration_sec=timeline.total_duration_sec,
      cache_dir=work_dir,
  )

  # -------------------------------------------------------------- 6. lip-sync
  _banner("6/7", "Wav2Lip (one pass over the whole narration)")
  lipsync_path: Optional[Path] = None
  presenter_source = None
  used_lipsync = False

  H = 1080
  from compositor import karaoke
  layout = presenter_mod.compute_layout((1920, H), int(H * karaoke.BOTTOM_SAFE_PCT))

  if use_lipsync:
    try:
      from services.wav2lip_service import generate_lip_sync_video

      lipsync_path = work_dir / f"{job_id}_{lang}_narration_w2l.mp4"
      if lipsync_path.exists() and lipsync_path.stat().st_size > 1000:
        logger.info("lip-sync cache hit: %s", lipsync_path.name)
      else:
        generate_lip_sync_video(
            face_video_path=loop_path,
            audio_path=timeline.wav_path,
            output_path=lipsync_path,
        )
      presenter_source = presenter_mod.PresenterSource.load(
          str(lipsync_path), layout, avatar.disclosure_label, lang
      )
      used_lipsync = True
      logger.info("lip-synced presenter ready: %s", lipsync_path.name)
    except Exception:
      logger.warning(
          "Wav2Lip failed; falling back to the un-synced ping-pong loop. "
          "The anchor will move but the mouth will not match the words.",
          exc_info=True,
      )

  if presenter_source is None:
    presenter_source = presenter_mod.PresenterSource.load(
        str(loop_path), layout, avatar.disclosure_label, lang
    )
    logger.info("presenter ready (no lip-sync): %s", loop_path.name)

  # The gesture scheduler must not re-cut a stream that is already synced to
  # the audio, so the source deliberately carries no sidecar path here.
  presenter_source.clip_path = None

  # ----------------------------------------------------------------- 7. render
  _banner("7/7", "Render")
  layers.render_job(
      scenes=scenes,
      lang=lang,
      out_path=str(out_path),
      codec_pref=codec_pref,
      presenter_source=presenter_source,
      narration_wav=str(timeline.wav_path),
  )

  elapsed = time.time() - t0
  result = PipelineResult(
      job_id=job_id,
      lang=lang,
      video_path=out_path,
      narration_wav=timeline.wav_path,
      anchor_loop=loop_path,
      lipsync_video=lipsync_path if used_lipsync else None,
      scenes=list(scenes),
      facts=list(facts),
      total_duration_sec=timeline.total_duration_sec,
      elapsed_sec=elapsed,
      used_lipsync=used_lipsync,
  )
  return result
