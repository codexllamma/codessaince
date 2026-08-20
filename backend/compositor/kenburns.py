"""Ken Burns motion math (README.md §8.6).

Pure functions only — no MoviePy, no I/O beyond PIL image resampling — so
this module is directly and cheaply unit-testable (tests/test_kenburns.py).
"""

from __future__ import annotations

from typing import Tuple

from PIL import Image

Z_MAX_DEFAULT = 1.12  # KENBURNS_ZOOM_MAX


def ease(p: float) -> float:
    """Smoothstep easing — removes the linear-pan feel (README §8.6)."""
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


def ease_out_cubic(p: float) -> float:
    """Fast-out, gentle settle curve for smooth card & text entrances."""
    p = min(max(p, 0.0), 1.0)
    return 1.0 - (1.0 - p) ** 3


def ease_out_back(p: float, s: float = 1.70158) -> float:
    """Spring-like overshoot curve for lively metric pops."""
    p = min(max(p, 0.0), 1.0)
    return 1.0 + (s + 1.0) * ((p - 1.0) ** 3) + s * ((p - 1.0) ** 2)


def progress(t: float, duration: float) -> float:
    if duration <= 0:
        return 1.0
    return min(max(t / duration, 0.0), 1.0)


def zoom(t: float, duration: float, z_max: float = Z_MAX_DEFAULT) -> float:
    """zoom(t) = 1 + (Z_max - 1) * ease(p(t))."""
    return 1 + (z_max - 1) * ease(progress(t, duration))


def crop_box(
    t: float,
    duration: float,
    output_w: int,
    output_h: int,
    cx0: float,
    cy0: float,
    cx1: float,
    cy1: float,
    source_w: int,
    source_h: int,
    z_max: float = Z_MAX_DEFAULT,
) -> Tuple[float, float, float, float]:
    """(left, top, right, bottom) crop box in source-pixel coordinates.

    Centre drift is clamped so the box never exceeds the source bounds —
    this is the invariant tests/test_kenburns.py checks across all t.
    """
    z = zoom(t, duration, z_max)
    e = ease(progress(t, duration))
    crop_w = output_w / z
    crop_h = output_h / z

    cx = cx0 + (cx1 - cx0) * e
    cy = cy0 + (cy1 - cy0) * e

    half_w, half_h = crop_w / 2, crop_h / 2
    # Degenerate case: crop larger than source (shouldn't happen once the
    # source has been upscaled via upscale_source, but clamp defensively).
    cx = min(max(cx, half_w), max(source_w - half_w, half_w))
    cy = min(max(cy, half_h), max(source_h - half_h, half_h))

    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def pan_targets_for_template(
    template_type: str,
    source_w: int,
    source_h: int,
    alternate: bool = False,
) -> Tuple[float, float, float, float]:
    """(cx0, cy0, cx1, cy1) centre-drift endpoints, per README §8.6.

    - HERO_ANNOUNCEMENT drifts right.
    - DEADLINE_ALERT pushes in centre with no pan (reads as urgency).
    - Other templates get a subtle diagonal drift; direction alternates
      between consecutive scenes via `alternate` (based on scene index parity)
      so the video doesn't feel like one continuous slow zoom.
    """
    center_x, center_y = source_w / 2, source_h / 2
    drift_x = source_w * 0.06
    drift_y = source_h * 0.035

    if template_type == "DEADLINE_ALERT":
        return (center_x, center_y, center_x, center_y)

    if template_type == "HERO_ANNOUNCEMENT":
        return (center_x - drift_x / 2, center_y, center_x + drift_x / 2, center_y)

    sign = -1 if alternate else 1
    return (
        center_x - sign * drift_x / 2,
        center_y - drift_y / 2,
        center_x + sign * drift_x / 2,
        center_y + drift_y / 2,
    )


def upscale_source(img: Image.Image, output_w: int, output_h: int, z_max: float = Z_MAX_DEFAULT) -> Image.Image:
    """Ensure the source is >= z_max*output_w x z_max*output_h before any crop.

    Guarantees the frame never samples above native resolution (README §8.6)
    and gives headroom for centre-drift panning without hitting source edges.
    """
    min_w, min_h = z_max * output_w, z_max * output_h
    if img.width >= min_w and img.height >= min_h:
        return img
    scale = max(min_w / img.width, min_h / img.height)
    new_size = (max(round(img.width * scale), round(min_w)), max(round(img.height * scale), round(min_h)))
    return img.resize(new_size, Image.LANCZOS)


def render_frame(
    source_img: Image.Image,
    t: float,
    duration: float,
    output_w: int,
    output_h: int,
    cx0: float,
    cy0: float,
    cx1: float,
    cy1: float,
    z_max: float = Z_MAX_DEFAULT,
    resample: int = Image.LANCZOS,
) -> Image.Image:
    """Crop the source at time t per the Ken Burns transform and resample to output size.

    `resample` is the caller's speed/quality dial — the resize dominates
    per-frame cost, so it is worth choosing deliberately per source type.
    """
    box = crop_box(
        t, duration, output_w, output_h, cx0, cy0, cx1, cy1,
        source_img.width, source_img.height, z_max,
    )
    box = tuple(round(v) for v in box)
    return source_img.crop(box).resize((output_w, output_h), resample)
