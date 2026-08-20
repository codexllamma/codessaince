"""Normalise a downloaded clip into a presenter loop and register it.

Stock footage never arrives in the shape the presenter panel wants: it is
landscape, too long, and its last frame looks nothing like its first, so
looping it visibly jumps. This turns an arbitrary MP4 into a clip the
compositor can loop for the whole scene without the seam showing.

    python scripts/prepare_avatar.py in.mp4 --id presenter_m01 \
        --source licensed_stock \
        --licence "Pexels License - https://www.pexels.com/video/..." \
        --label "STOCK FOOTAGE - NOT A GOVERNMENT SPOKESPERSON" \
        --register

What it does, in order: centre-crop to the panel's aspect, trim to a window
of the source, crossfade the tail back onto the head so the loop is seamless,
and encode H.264 / yuv420p.

The disclosure label is required and is not defaulted. A photoreal presenter
delivering government scheme information is misleading unless the viewer can
tell what they are looking at, and the honest label differs by source: a
synthetic face is "AI-GENERATED PRESENTER", whereas real licensed footage is
a real person who never agreed to speak for a ministry, and must not be
labelled as AI. avatar_registry enforces that the field is non-empty; only
you can make it true.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import numpy as np
from PIL import Image

from compositor import _ffmpeg
from services.avatar_registry import ALLOWED_SOURCES, AVATARS_DIR, MANIFEST_PATH

# The panel is 681x744 at a 240px caption reserve — near square, so a centred
# medium close-up survives the crop and a wide two-shot does not. Encoding a
# little above panel size leaves room for the rounded-corner fit without
# upscaling; both dimensions stay even because yuv420p subsamples by two.
DEFAULT_WIDTH = 768
DEFAULT_ASPECT = 0.92
DEFAULT_DURATION = 8.0
DEFAULT_CROSSFADE = 1.0
OUTPUT_FPS = 30


def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1


def centre_crop(frame: np.ndarray, aspect: float) -> Image.Image:
    """Crop to `aspect` (w/h) about the centre, keeping as much height as possible."""
    img = Image.fromarray(frame)
    w, h = img.size
    if w / h > aspect:
        new_w = int(round(h * aspect))
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = int(round(w / aspect))
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def build_loop(src, start: float, duration: float, crossfade: float, size, aspect: float):
    """Frame function whose end blends back into its beginning.

    Plays [start, start+duration) but overlays the tail onto the head: at t=0
    the output is the source at the very end of the window, ramping to the
    plain source by t=crossfade. The last output frame is therefore already
    what the first output frame shows, so the wrap is invisible.
    """
    out_w, out_h = size

    def fetch(t: float) -> np.ndarray:
        clamped = min(max(start + t, 0.0), max(src.duration - 1e-3, 0.0))
        cropped = centre_crop(src.get_frame(clamped), aspect)
        if cropped.size != size:
            cropped = cropped.resize(size, Image.LANCZOS)
        return np.asarray(cropped.convert("RGB"), dtype=np.float32)

    def frame_function(t: float) -> np.ndarray:
        base = fetch(t)
        if crossfade > 0 and t < crossfade:
            a = 1.0 - (t / crossfade)  # 1 at t=0 -> 0 at t=crossfade
            base = base * (1.0 - a) + fetch(t + duration) * a
        return np.clip(base, 0, 255).astype(np.uint8)

    return frame_function


def register(entry: dict, manifest_path: Path) -> None:
    """Add or replace an entry in the manifest, preserving the comments."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    avatars = [a for a in data.get("avatars", []) if a.get("avatar_id") != entry["avatar_id"]]
    avatars.append(entry)
    data["avatars"] = avatars
    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source_clip", type=Path, help="downloaded MP4 to normalise")
    p.add_argument("--id", required=True, help="avatar_id, also the output filename")
    p.add_argument("--source", required=True, choices=ALLOWED_SOURCES)
    p.add_argument("--licence", required=True, help="licence text and the URL it came from")
    p.add_argument("--label", required=True, help="on-screen disclosure label")
    p.add_argument("--languages", default="*", help="comma-separated codes, or * (default)")
    p.add_argument("--display-name", default=None)
    p.add_argument("--start", type=float, default=0.0, help="seconds into the source to begin")
    p.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    p.add_argument("--crossfade", type=float, default=DEFAULT_CROSSFADE)
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    p.add_argument("--aspect", type=float, default=DEFAULT_ASPECT, help="w/h of the output")
    p.add_argument("--register", action="store_true", help="also add it to manifest.json")
    args = p.parse_args()

    if not args.source_clip.is_file():
        print(f"error: {args.source_clip} not found", file=sys.stderr)
        return 1
    if not args.label.strip():
        print("error: --label must be non-empty; the presenter is never rendered unlabelled", file=sys.stderr)
        return 1

    _ffmpeg.ensure_ffmpeg_binary_env()
    from moviepy import VideoClip, VideoFileClip

    src = VideoFileClip(str(args.source_clip))
    try:
        print(f"source: {src.size[0]}x{src.size[1]}  {src.duration:.2f}s  {src.fps:g}fps")

        available = src.duration - args.start
        if available <= 0:
            print(f"error: --start {args.start}s is beyond the {src.duration:.2f}s source", file=sys.stderr)
            return 1

        # The crossfade consumes real footage: the window must hold the loop
        # body plus the tail it blends back in, or the two would overlap.
        duration = min(args.duration, available - args.crossfade)
        if duration < 2.0:
            print(
                f"error: only {available:.2f}s usable after --start; need "
                f"{args.crossfade + 2.0:.2f}s minimum for a {args.crossfade}s crossfade",
                file=sys.stderr,
            )
            return 1
        if duration < args.duration:
            print(f"note: trimmed to {duration:.2f}s to leave room for the crossfade")

        out_w = _even(args.width)
        out_h = _even(int(round(out_w / args.aspect)))
        size = (out_w, out_h)

        AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = AVATARS_DIR / f"{args.id}.mp4"

        clip = VideoClip(
            frame_function=build_loop(src, args.start, duration, args.crossfade, size, args.aspect),
            duration=duration,
        ).with_fps(OUTPUT_FPS)

        print(f"writing {out_path.name}: {out_w}x{out_h}  {duration:.2f}s  loop seam {args.crossfade:g}s")
        clip.write_videofile(
            str(out_path),
            codec="libx264",
            preset="veryfast",
            pixel_format="yuv420p",
            audio=False,  # narration is edge-tts; a presenter loop is silent
            logger=None,
        )
        clip.close()
    finally:
        src.close()

    entry = {
        "avatar_id": args.id,
        "file": out_path.name,
        "languages": [s.strip() for s in args.languages.split(",") if s.strip()],
        "display_name": args.display_name or args.id,
        "source": args.source,
        "licence": args.licence,
        "disclosure_label": args.label,
    }

    if args.register:
        register(entry, MANIFEST_PATH)
        print(f"registered {args.id} in {MANIFEST_PATH.name}")
    else:
        print("\nnot registered. Add this to 'avatars' in assets/avatars/manifest.json:\n")
        print(json.dumps(entry, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
