"""Build a seamless anchor loop long enough to cover a whole narration.

A presenter clip is a few seconds long and a finished video is half a minute
or more, so the clip has to repeat. Repeating it head-to-tail jumps visibly at
the seam: the anchor is mid-gesture on the last frame and back at rest on the
first. Playing it forwards then backwards -- ping-pong -- ends every cycle on
the frame it started from, so the seam lands on identical pixels and the only
artefact is the motion reversing, which on a mostly-still news anchor reads as
natural shifting rather than a cut.

This is the method loop_video.py applies by hand; here it is a function the
pipeline can call for an arbitrary target duration.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _ffmpeg() -> str:
  try:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
  except Exception:  # pragma: no cover - only when imageio-ffmpeg is absent
    import shutil

    return shutil.which("ffmpeg") or "ffmpeg"


def probe_duration(video_path: Path) -> float:
  from moviepy import VideoFileClip

  clip = VideoFileClip(str(video_path))
  try:
    return float(clip.duration)
  finally:
    clip.close()


def build_ping_pong_loop(
    source: Path,
    out_path: Path,
    target_duration_sec: float,
    crf: int = 18,
    preset: str = "fast",
) -> Path:
  """Ping-pong `source` until it covers `target_duration_sec`.

  One ping-pong cycle is twice the source length. Enough cycles are chained to
  reach the target and the result is cut back to exactly the target, so the
  caller can rely on the returned clip being at least as long as the audio it
  has to carry.

  Everything is done in one ffmpeg pass rather than by concatenating files:
  re-encoding each repetition separately would compound generation loss across
  a long narration.
  """
  source = Path(source).resolve()
  out_path = Path(out_path).resolve()
  out_path.parent.mkdir(parents=True, exist_ok=True)

  if not source.is_file():
    raise FileNotFoundError(f"anchor clip not found: {source}")

  src_dur = probe_duration(source)
  if src_dur <= 0:
    raise ValueError(f"anchor clip has no duration: {source}")

  cycle = src_dur * 2.0
  cycles = max(1, int(target_duration_sec / cycle) + 1)

  logger.info(
      "ping-pong loop: source %.2fs -> %d cycle(s) of %.2fs to cover %.2fs",
      src_dur, cycles, cycle, target_duration_sec,
  )

  # [0:v]reverse[r] then alternate forward/reverse `cycles` times. concat wants
  # each input segment listed once, so the same two labels are split as many
  # times as they are consumed.
  parts = [
      "[0:v]split=%d%s" % (cycles, "".join(f"[f{i}]" for i in range(cycles))),
      "[0:v]reverse,split=%d%s" % (cycles, "".join(f"[r{i}]" for i in range(cycles))),
  ]
  order = "".join(f"[f{i}][r{i}]" for i in range(cycles))
  parts.append(f"{order}concat=n={cycles * 2}:v=1:a=0[v]")
  filter_complex = ";".join(parts)

  cmd = [
      _ffmpeg(), "-y", "-loglevel", "error",
      "-i", str(source),
      "-filter_complex", filter_complex,
      "-map", "[v]",
      "-t", f"{target_duration_sec:.3f}",
      "-c:v", "libx264",
      "-preset", preset,
      "-crf", str(crf),
      "-pix_fmt", "yuv420p",
      "-an",
      str(out_path),
  ]
  subprocess.run(cmd, check=True)

  if not out_path.is_file() or out_path.stat().st_size < 1000:
    raise RuntimeError(f"ping-pong loop produced no usable output at {out_path}")

  final_dur = probe_duration(out_path)
  logger.info("ping-pong loop written: %s (%.2fs)", out_path.name, final_dur)
  return out_path


def ensure_anchor_loop(
    source: Path,
    target_duration_sec: float,
    cache_dir: Optional[Path] = None,
) -> Path:
  """Cached wrapper: loops are deterministic, so the same clip and duration
  never needs building twice within a run."""
  cache_dir = cache_dir or (BACKEND_DIR / "static" / "avatars")
  cache_dir.mkdir(parents=True, exist_ok=True)
  out_path = cache_dir / f"{Path(source).stem}_pingpong_{int(target_duration_sec)}s.mp4"

  if out_path.is_file() and out_path.stat().st_size > 1000:
    logger.info("ping-pong loop cache hit: %s", out_path.name)
    return out_path

  return build_ping_pong_loop(source, out_path, target_duration_sec)
