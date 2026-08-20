"""services/narration.py

Builds ONE continuous narration track for a whole video instead of one audio
file per scene.

The driver for this is lip-sync: a single anchor clip must speak the entire
notice without the mouth resetting at every scene boundary, which is exactly
what per-scene audio files caused. So we synthesise everything, concatenate it
into a single stream, and hand the caller a timeline that says which slice of
that stream belongs to which scene.

Synthesis is done per *script segment* rather than per scene because emphasis
and pauses are segment-level properties: edge-tts prosody is set when the
connection is opened, so a segment that must be spoken slower and louder needs
its own request. Concatenating the resulting PCM is lossless, so the listener
hears one uninterrupted read.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import edge_tts
import numpy as np
import soundfile as sf

from models.schemas import SceneDefinition, WordTimestamp
from services.audio_synthesizer import SCENE_TAIL_PAD_SEC, VOICE_MAPPING

logger = logging.getLogger(__name__)


# Wav2Lip's audio frontend is hard-wired to 16 kHz mono mel spectrograms; feed
# it anything else and it either errors or silently produces garbage mouths.
# Everything downstream therefore standardises on this.
DEFAULT_SAMPLE_RATE = 16000

# Emphasis -> edge-tts prosody. Tunable at module level on purpose: this is the
# knob you reach for when a demo sounds flat.
#
# `rate_delta_pct` is added to the caller's global `rate` in percentage points
# (edge-tts rates are themselves a percentage delta from the voice's baseline,
# so "+10%" from the caller plus -15 for a strong beat becomes "-5%"). Slowing
# a phrase is what actually makes it read as emphasis to a listener -- volume
# alone just sounds like a level jump -- so every level above "none" buys its
# emphasis primarily with rate.
EMPHASIS_PROSODY: Dict[str, Dict[str, object]] = {
    "none": {"rate_delta_pct": 0, "volume": "+0%", "pitch": "+0Hz"},
    "moderate": {"rate_delta_pct": -8, "volume": "+10%", "pitch": "+0Hz"},
    "strong": {"rate_delta_pct": -15, "volume": "+20%", "pitch": "+15Hz"},
}

# edge-tts rejects extreme prosody; clamp rather than let a stacked caller rate
# plus emphasis delta blow past the service limits.
_RATE_MIN_PCT = -50
_RATE_MAX_PCT = 100

# edge-tts pads every stream with roughly 0.2 s of lead-in and up to a second
# of trailing silence. That was harmless when a stream was a whole scene, but
# we now open one stream per *segment*, so the padding would stack into ~1 s of
# dead air between every phrase and make `pause_after_ms` meaningless. Trim it
# and let the script's own pauses set the rhythm.
TRIM_EDGE_SILENCE = True
SILENCE_FLOOR = 1e-3
# Guard band so a soft consonant onset is not clipped off the front of a word.
SILENCE_KEEP_SEC = 0.03

# How much of a segment's text to put in the log line.
_LOG_TEXT_CHARS = 60

_PUNCTUATION = ".,;:!?()\"'[]{}"


# =====================================================================
# Public data shapes
# =====================================================================


@dataclass(frozen=True)
class SceneSpan:
  scene_id: int
  start_sec: float
  end_sec: float
  # Scene-local: a caller rendering scene N as its own clip needs times
  # measured from that clip's first frame, not from the top of the narration.
  subtitles: List[WordTimestamp]


@dataclass(frozen=True)
class NarrationTimeline:
  wav_path: Path
  total_duration_sec: float
  sample_rate: int
  spans: List[SceneSpan]


# =====================================================================
# Prosody
# =====================================================================


def _parse_percent(value: str) -> int:
  """'+10%' / '-5%' / '0' -> int. Unparseable input degrades to 0."""
  try:
    return int(round(float(str(value).strip().rstrip("%"))))
  except (TypeError, ValueError):
    logger.warning("Unparseable rate %r, treating as +0%%", value)
    return 0


def _format_percent(pct: int) -> str:
  return f"{pct:+d}%"


def _prosody_for(emphasis_level: str, base_rate: str) -> Tuple[str, str, str]:
  """Resolve (rate, volume, pitch) strings for one segment."""
  profile = EMPHASIS_PROSODY.get(emphasis_level, EMPHASIS_PROSODY["none"])
  pct = _parse_percent(base_rate) + int(profile["rate_delta_pct"])
  pct = max(_RATE_MIN_PCT, min(_RATE_MAX_PCT, pct))
  return _format_percent(pct), str(profile["volume"]), str(profile["pitch"])


# =====================================================================
# The network seam
# =====================================================================


async def _synthesize_segment(
    text: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
) -> Tuple[bytes, List[Tuple[str, float, float]]]:
  """Speak one segment. Returns (mp3 bytes, [(word, start_sec, end_sec)]).

  Kept deliberately small and free of decoding/timeline logic: it is the only
  function in this module that touches the network, so tests replace exactly
  this one coroutine.

  Word times are relative to the start of *this* segment.
  """
  kwargs = dict(text=text, voice=voice, rate=rate, volume=volume, pitch=pitch)
  try:
    # edge-tts >= 7 defaults to SentenceBoundary, which would give us one
    # timestamp per sentence and force the fallback path for every segment.
    communicate = edge_tts.Communicate(boundary="WordBoundary", **kwargs)
  except TypeError:
    communicate = edge_tts.Communicate(**kwargs)

  audio = bytearray()
  words: List[Tuple[str, float, float]] = []

  async for chunk in communicate.stream():
    if chunk["type"] == "audio":
      audio.extend(chunk["data"])
    elif chunk["type"] == "WordBoundary":
      # edge-tts reports offsets in 100-nanosecond ticks.
      start_sec = chunk["offset"] / 10_000_000.0
      end_sec = (chunk["offset"] + chunk["duration"]) / 10_000_000.0
      words.append((chunk["text"], start_sec, end_sec))

  return bytes(audio), words


# =====================================================================
# Audio decoding
# =====================================================================


def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
  if src_rate == dst_rate or samples.size == 0:
    return samples
  try:
    from scipy.signal import resample_poly

    gcd = math.gcd(src_rate, dst_rate)
    return resample_poly(samples, dst_rate // gcd, src_rate // gcd).astype(np.float32)
  except ImportError:
    # Naive but dependency-free. Aliases a little when downsampling; speech at
    # 24 kHz -> 16 kHz has almost no energy above 8 kHz so it is inaudible.
    n_out = int(round(samples.size * dst_rate / src_rate))
    if n_out <= 0:
      return np.zeros(0, dtype=np.float32)
    src_t = np.arange(samples.size, dtype=np.float64)
    dst_t = np.linspace(0.0, samples.size - 1, n_out, dtype=np.float64)
    return np.interp(dst_t, src_t, samples).astype(np.float32)


def _decode_with_ffmpeg(data: bytes, sample_rate: int) -> np.ndarray:
  """Last resort when libsndfile was built without MPEG support.

  Note the argument *list*: this repo lives under a path containing a space,
  and a formatted command string would be split on it.
  """
  import imageio_ffmpeg

  with tempfile.TemporaryDirectory(prefix="narration_") as tmp_dir:
    src = Path(tmp_dir) / "segment.mp3"
    dst = Path(tmp_dir) / "segment.wav"
    src.write_bytes(data)
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(dst),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    samples, _ = sf.read(str(dst), dtype="float32", always_2d=True)

  return samples[:, 0].astype(np.float32)


def _decode_to_mono(data: bytes, sample_rate: int) -> np.ndarray:
  """Decode TTS bytes to a mono float32 array at `sample_rate`."""
  if not data:
    return np.zeros(0, dtype=np.float32)

  try:
    samples, src_rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
  except Exception:
    logger.debug("soundfile could not decode segment, falling back to ffmpeg")
    return _decode_with_ffmpeg(data, sample_rate)

  # Averaging the channels rather than dropping one keeps the level right for
  # voices that are not perfectly centred.
  mono = samples.mean(axis=1).astype(np.float32)
  return _resample(mono, int(src_rate), sample_rate)


def _trim_edge_silence(audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, float]:
  """Strip the TTS engine's leading/trailing padding.

  Returns (trimmed, lead_sec_removed); the caller must shift that segment's
  word boundaries back by `lead_sec_removed`, since edge-tts reports them
  relative to the untrimmed stream.
  """
  if not TRIM_EDGE_SILENCE or audio.size == 0:
    return audio, 0.0

  voiced = np.nonzero(np.abs(audio) > SILENCE_FLOOR)[0]
  if voiced.size == 0:
    # A wholly silent segment is either a deliberate beat or a synthesis
    # failure; in both cases deleting it is worse than keeping it.
    return audio, 0.0

  keep = int(round(SILENCE_KEEP_SEC * sample_rate))
  start = max(int(voiced[0]) - keep, 0)
  end = min(int(voiced[-1]) + 1 + keep, audio.size)
  return audio[start:end], start / float(sample_rate)


def _silence(duration_sec: float, sample_rate: int) -> np.ndarray:
  return np.zeros(max(int(round(duration_sec * sample_rate)), 0), dtype=np.float32)


# =====================================================================
# Timestamps
# =====================================================================


def _distribute_words(
    text: str,
    duration_sec: float,
    offset_sec: float,
    is_core_fact: bool,
) -> List[WordTimestamp]:
  """Spread a segment's words across its measured duration by word length.

  `generate_fallback_timestamps` in audio_synthesizer solves the same problem
  but is scene-shaped: it subtracts the scene tail pad and re-derives core-fact
  membership by string matching. Here the segment already tells us both, so a
  local version is both simpler and more accurate.
  """
  words = text.split()
  if not words or duration_sec <= 0:
    return []

  weights = [max(len(w.strip(_PUNCTUATION)), 2) for w in words]
  total_weight = float(sum(weights))

  stamps: List[WordTimestamp] = []
  cursor = 0.0
  for word, weight in zip(words, weights):
    span = (weight / total_weight) * duration_sec
    stamps.append(
        WordTimestamp(
            word=word,
            start_sec=round(offset_sec + cursor, 3),
            end_sec=round(offset_sec + cursor + span, 3),
            is_core_fact=is_core_fact,
        )
    )
    cursor += span

  return stamps


def _boundaries_to_timestamps(
    boundaries: Sequence[Tuple[str, float, float]],
    offset_sec: float,
    is_core_fact: bool,
) -> List[WordTimestamp]:
  """Shift a segment's word boundaries onto the narration timeline.

  Because we know which segment produced each word, core-fact marking is a
  property of the segment rather than a string match against the fact text.
  """
  stamps: List[WordTimestamp] = []
  for word, start, end in boundaries:
    start_sec = max(offset_sec + start, 0.0)
    end_sec = max(offset_sec + end, start_sec)
    stamps.append(
        WordTimestamp(
            word=word,
            start_sec=round(start_sec, 3),
            end_sec=round(end_sec, 3),
            is_core_fact=is_core_fact,
        )
    )
  return stamps


def _truncate(text: str, limit: int = _LOG_TEXT_CHARS) -> str:
  flat = " ".join(text.split())
  return flat if len(flat) <= limit else flat[: limit - 1] + "…"


# =====================================================================
# Public API
# =====================================================================


async def build_narration(
    scenes: Sequence[SceneDefinition],
    lang: str,
    out_wav: Path,
    voice_id: Optional[str] = None,
    rate: str = "+0%",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> NarrationTimeline:
  """Synthesise every scene into one continuous wav and map scenes onto it.

  The passed-in scenes are never mutated; the caller decides what to do with
  the returned spans.
  """
  voice = voice_id or VOICE_MAPPING.get(lang) or VOICE_MAPPING["en"]
  out_wav = Path(out_wav)
  out_wav.parent.mkdir(parents=True, exist_ok=True)

  logger.info(
      "Building narration: %d scene(s), lang=%s, voice=%s, rate=%s, %d Hz mono",
      len(scenes),
      lang,
      voice,
      rate,
      sample_rate,
  )

  chunks: List[np.ndarray] = []
  spans: List[SceneSpan] = []
  # Position is tracked in samples, not seconds: accumulating floats across a
  # few hundred segments drifts enough to desync the lip-sync near the end.
  cursor_samples = 0

  for scene in scenes:
    scene_start_samples = cursor_samples
    scene_subtitles: List[WordTimestamp] = []
    logger.info("Scene %s: %d segment(s)", scene.scene_id, len(scene.script_segments))

    for seg_index, segment in enumerate(scene.script_segments):
      seg_rate, seg_volume, seg_pitch = _prosody_for(segment.emphasis_level, rate)
      mp3_bytes, boundaries = await _synthesize_segment(
          segment.text, voice, seg_rate, seg_volume, seg_pitch
      )
      audio, lead_trim_sec = _trim_edge_silence(
          _decode_to_mono(mp3_bytes, sample_rate), sample_rate
      )
      seg_duration = len(audio) / float(sample_rate)

      # Scene-local offset of this segment's first sample.
      seg_offset = (cursor_samples - scene_start_samples) / float(sample_rate)
      is_core_fact = segment.type == "core_fact"

      if boundaries:
        stamps = _boundaries_to_timestamps(
            boundaries, seg_offset - lead_trim_sec, is_core_fact
        )
      else:
        logger.warning(
            "Scene %s segment %d produced no WordBoundary events; "
            "distributing %d word(s) proportionally",
            scene.scene_id,
            seg_index,
            len(segment.text.split()),
        )
        stamps = _distribute_words(segment.text, seg_duration, seg_offset, is_core_fact)

      scene_subtitles.extend(stamps)
      chunks.append(audio)
      cursor_samples += len(audio)

      if segment.pause_after_ms > 0:
        pause = _silence(segment.pause_after_ms / 1000.0, sample_rate)
        chunks.append(pause)
        cursor_samples += len(pause)

      logger.info(
          "  [%s/%d] %-9s %-8s %5.2fs (+%dms pause) | total %6.2fs | %s",
          scene.scene_id,
          seg_index,
          segment.type,
          segment.emphasis_level,
          seg_duration,
          segment.pause_after_ms,
          cursor_samples / float(sample_rate),
          _truncate(segment.text),
      )

    # Breathing room so the next scene's first word does not clip the previous
    # scene's last one when the video cuts.
    tail = _silence(SCENE_TAIL_PAD_SEC, sample_rate)
    chunks.append(tail)
    cursor_samples += len(tail)

    span = SceneSpan(
        scene_id=scene.scene_id,
        start_sec=round(scene_start_samples / float(sample_rate), 3),
        end_sec=round(cursor_samples / float(sample_rate), 3),
        subtitles=scene_subtitles,
    )
    spans.append(span)
    logger.info(
        "Scene %s span %.2fs -> %.2fs (%.2fs, %d subtitle(s))",
        span.scene_id,
        span.start_sec,
        span.end_sec,
        span.end_sec - span.start_sec,
        len(span.subtitles),
    )

  narration = (
      np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
  ).astype(np.float32)

  # PCM_16 mono: what Wav2Lip and every downstream muxer expect.
  sf.write(str(out_wav), narration, sample_rate, subtype="PCM_16")

  total_duration_sec = round(len(narration) / float(sample_rate), 3)
  logger.info(
      "Narration written: %s (%.2fs, %d Hz mono, %d scene span(s))",
      out_wav,
      total_duration_sec,
      sample_rate,
      len(spans),
  )

  return NarrationTimeline(
      wav_path=out_wav,
      total_duration_sec=total_duration_sec,
      sample_rate=sample_rate,
      spans=spans,
  )


def build_narration_sync(
    scenes: Sequence[SceneDefinition],
    lang: str,
    out_wav: Path,
    voice_id: Optional[str] = None,
    rate: str = "+0%",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> NarrationTimeline:
  """Blocking wrapper for callers that are not already inside an event loop."""
  return asyncio.run(
      build_narration(
          scenes=scenes,
          lang=lang,
          out_wav=out_wav,
          voice_id=voice_id,
          rate=rate,
          sample_rate=sample_rate,
      )
  )
