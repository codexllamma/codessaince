"""Propose gesture windows in a presenter clip by hand-motion energy.

    python scripts/segment_gestures.py assets/avatars/presenter_01.mp4

Prints a motion profile and writes a starter `<clip>.gestures.json` next to
the clip, with the calm stretches marked as candidate rest poses and the
active ones as candidate gestures.

The output is a draft, not an answer. Frame differencing can tell a still
pose from a moving one, which is what picks the window boundaries; it cannot
tell an open palm from a raised finger, which is what decides the role. Open
the clip, look at each proposed window, and set `role` and `note` by eye.
Roles the scheduler understands are neutral, present and stress — see
compositor/gestures.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import numpy as np
from PIL import Image

from compositor import _ffmpeg
from compositor.gestures import MIN_GESTURE_SEC

ANALYSIS_FPS = 12.5
ANALYSIS_SIZE = (96, 104)
# Hands occupy the lower part of the panel crop; the head dominates the top and
# moves constantly while speaking, which would drown out the hand signal.
HANDS_FROM_ROW = 55
# A gesture's energy dips as it reaches its extent; gaps shorter than this are
# treated as part of the same gesture rather than a return to rest.
GAP_CLOSE_SEC = 0.4
# Fraction of the way from the median to the peak. Resting hands still drift,
# so the floor is the median rather than zero; 0.20 sits above that drift and
# well under a real stroke. 0.45 was too strict — it caught only the peaks of
# each burst, which the minimum-duration filter then discarded entirely.
THRESHOLD_FRACTION = 0.20


def motion_profile(clip, fps: float = ANALYSIS_FPS) -> Tuple[np.ndarray, np.ndarray]:
    """Per-sample hand-motion energy and the times it was sampled at."""
    frames: List[np.ndarray] = []
    times: List[float] = []
    n = max(int(clip.duration * fps), 2)
    for i in range(n):
        t = min(i / fps, clip.duration - 1e-3)
        img = Image.fromarray(clip.get_frame(t)).resize(ANALYSIS_SIZE, Image.BILINEAR)
        frames.append(np.asarray(img.convert("L"), dtype=np.float32))
        times.append(t)
    stack = np.stack(frames)[:, HANDS_FROM_ROW:, :]
    energy = np.abs(np.diff(stack, axis=0)).mean(axis=(1, 2))
    return energy, np.asarray(times[1:])


def find_windows(energy: np.ndarray, times: np.ndarray, threshold: float, fps: float = ANALYSIS_FPS) -> List[dict]:
    """Split the timeline into alternating calm and active runs.

    Energy dips mid-stroke — a gesture pauses at its extent before retracting —
    so a raw threshold chops one gesture into fragments, each too short to
    survive the minimum-duration filter. Short gaps are closed first so the
    stroke and its retraction stay one window.
    """
    active = energy > threshold
    max_gap = max(int(GAP_CLOSE_SEC * fps), 1)
    gap_start = None
    for i, is_active in enumerate(active):
        if not is_active:
            if gap_start is None:
                gap_start = i
        else:
            if gap_start is not None and gap_start > 0 and i - gap_start <= max_gap:
                active[gap_start:i] = True
            gap_start = None

    windows: List[dict] = []
    start_idx = 0
    for i in range(1, len(active) + 1):
        if i == len(active) or active[i] != active[start_idx]:
            start, end = times[start_idx], times[i - 1]
            if end - start >= MIN_GESTURE_SEC:
                windows.append(
                    {
                        "start": round(float(start), 2),
                        "end": round(float(end), 2),
                        "active": bool(active[start_idx]),
                        "peak": round(float(energy[start_idx:i].max()), 2),
                    }
                )
            if i < len(active):
                start_idx = i
    return windows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("clip", type=Path)
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="motion energy above which a sample counts as gesturing "
        "(default: midway between the profile's median and its peak)",
    )
    p.add_argument("--force", action="store_true", help="overwrite an existing sidecar")
    args = p.parse_args()

    if not args.clip.is_file():
        print(f"error: {args.clip} not found", file=sys.stderr)
        return 1

    out_path = args.clip.parent / (args.clip.stem + ".gestures.json")
    if out_path.exists() and not args.force:
        print(f"error: {out_path.name} already exists; pass --force to overwrite", file=sys.stderr)
        return 1

    _ffmpeg.ensure_ffmpeg_binary_env()
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(args.clip))
    try:
        print(f"{args.clip.name}: {clip.size[0]}x{clip.size[1]}  {clip.duration:.2f}s")
        energy, times = motion_profile(clip)
    finally:
        clip.close()

    threshold = args.threshold
    if threshold is None:
        median = float(np.median(energy))
        threshold = median + (float(energy.max()) - median) * THRESHOLD_FRACTION
    print(f"motion: median {np.median(energy):.2f}  peak {energy.max():.2f}  threshold {threshold:.2f}\n")

    for t, e in zip(times, energy):
        print(f"{t:6.2f}s {e:6.2f} {'#' * min(int(e * 3), 60)}")

    windows = find_windows(energy, times, threshold)
    if not windows:
        print("\nno windows longer than the minimum; try a different --threshold", file=sys.stderr)
        return 1

    print(f"\n{len(windows)} candidate window(s):")
    gestures = {}
    n_rest = n_gesture = 0
    for w in windows:
        if w["active"]:
            n_gesture += 1
            name, role = f"gesture_{n_gesture:02d}", "present" if n_gesture == 1 else "stress"
        else:
            n_rest += 1
            name, role = f"rest_{n_rest:02d}", "neutral"
        print(f"  {w['start']:6.2f}-{w['end']:6.2f}s  peak {w['peak']:5.2f}  -> {name} ({role})")
        gestures[name] = {
            "start": w["start"],
            "end": w["end"],
            "role": role,
            "note": "CHECK BY EYE - role was guessed from motion energy alone",
        }

    out_path.write_text(
        json.dumps(
            {
                "_comment": [
                    "DRAFT from scripts/segment_gestures.py. Roles were assigned by motion",
                    "energy, which cannot tell one gesture from another - watch the clip and",
                    "correct them. Roles: neutral (resting), present (open/explanatory, used",
                    "on core facts), stress (emphatic, used on deadline scenes).",
                    "Keep the longest calm window as neutral; it carries most of the runtime.",
                ],
                "clip": args.clip.name,
                "default": "neutral",
                "gestures": gestures,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out_path.name} - review the roles before rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
