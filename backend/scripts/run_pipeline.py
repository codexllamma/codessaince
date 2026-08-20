"""Drive the whole continuous-narration pipeline from one command.

    cd backend
    ../.venv/Scripts/python.exe scripts/run_pipeline.py

Everything is logged as it happens -- facts, scenes, each narration segment,
the anchor loop, the lip-sync pass, and the render -- because the failure mode
that matters here is silent: a lip-sync that throws falls back to a plain loop
and still produces a video that looks finished.

    --text / --text-file   notice text to narrate
    --lang                 target language (default en)
    --out                  output mp4 (default out/<job>_<lang>.mp4)
    --no-lipsync           skip Wav2Lip; render the ping-pong loop unsynced
    --cpu                  encode with libx264 instead of NVENC
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_TEXT = (
    "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000 for small "
    "and marginal farmers. Complete e-KYC verification before 31-10-2026."
)


def _configure_logging(verbose: bool) -> None:
  # Force UTF-8 so the rupee sign in a normalised amount does not kill the run
  # on a cp1252 console, which is the Windows default.
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      try:
        stream.reconfigure(encoding="utf-8")
      except Exception:
        pass

  logging.basicConfig(
      level=logging.DEBUG if verbose else logging.INFO,
      format="%(asctime)s  %(levelname)-7s %(name)-24s %(message)s",
      datefmt="%H:%M:%S",
      stream=sys.stdout,
  )
  # These are chatty enough to bury the pipeline's own logs.
  for noisy in ("PIL", "matplotlib", "moviepy", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--text", default=None, help="notice text to narrate")
  parser.add_argument("--text-file", default=None, help="read notice text from a file")
  parser.add_argument("--job-id", default="pipeline_demo")
  parser.add_argument("--lang", default="en")
  parser.add_argument("--out", default=None)
  parser.add_argument("--voice", default=None, help="override the edge-tts voice id")
  parser.add_argument("--rate", default="+0%", help="global speech rate, e.g. -5%%")
  parser.add_argument("--no-lipsync", action="store_true")
  parser.add_argument("--cpu", action="store_true", help="encode with libx264")
  parser.add_argument("-v", "--verbose", action="store_true")
  args = parser.parse_args()

  _configure_logging(args.verbose)
  log = logging.getLogger("pipeline.run")

  if args.text_file:
    raw_text = Path(args.text_file).read_text(encoding="utf-8")
  elif args.text:
    raw_text = args.text
  else:
    raw_text = DEFAULT_TEXT
    log.info("no --text given; using the built-in sample notice")

  from services.pipeline import run_pipeline

  try:
    result = run_pipeline(
        raw_text=raw_text,
        job_id=args.job_id,
        lang=args.lang,
        out_path=Path(args.out) if args.out else None,
        codec_pref="libx264" if args.cpu else "h264_nvenc",
        use_lipsync=not args.no_lipsync,
        voice_id=args.voice,
        rate=args.rate,
    )
  except Exception:
    log.exception("pipeline failed")
    return 1

  size_mb = result.video_path.stat().st_size / (1024 * 1024) if result.video_path.exists() else 0.0
  log.info("")
  log.info("=" * 68)
  log.info("[DONE] %s", result.video_path)
  log.info("=" * 68)
  log.info("  scenes          : %d", len(result.scenes))
  log.info("  facts           : %s", ", ".join(f.category.value for f in result.facts))
  log.info("  duration        : %.2fs", result.total_duration_sec)
  log.info("  lip-synced      : %s", "yes" if result.used_lipsync else "NO (plain loop)")
  log.info("  narration wav   : %s", result.narration_wav)
  log.info("  anchor loop     : %s", result.anchor_loop)
  log.info("  output size     : %.1f MB", size_mb)
  log.info("  wall clock      : %.1fs", result.elapsed_sec)

  if not result.used_lipsync:
    log.warning("rendered WITHOUT lip-sync -- the mouth does not match the words")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
