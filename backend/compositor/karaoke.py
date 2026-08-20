"""Word-level karaoke caption rendering (README §8.6 layer 2, Appendix D).

Optimized, high-speed direct drawing with smooth color fills.
Zero per-word highlight pills or full-canvas allocation overhead.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image, ImageDraw

from compositor import typography
from models.schemas import WordTimestamp

# README Appendix D: caption.spoken #FACC15, caption.pending #F8FAFC,
# caption.past #94A3B8. Pending is the bright one and past is the dim one, so
# the eye reads ahead and spoken text recedes once it has been said.
#
# Swapping these two gives the other common karaoke convention, where text is
# dim until spoken and then fills in bright and stays lit. That reads well too
# and arguably suits a low-literacy audience better, since narrated text stays
# legible for a slow reader instead of fading. It is not what the spec's token
# table says, though, so the spec order stands until someone decides otherwise.
COLOR_SPOKEN_RGB = (250, 204, 21)      # #FACC15 Vivid Gold
COLOR_CORE_FACT_RGB = (254, 224, 71)    # #FDE047 Radiant Highlight
COLOR_PENDING_RGB = (248, 250, 252)     # #F8FAFC Crisp White - not yet spoken
COLOR_PAST_RGB = (148, 163, 184)        # #94A3B8 Muted Gray - already spoken

SIDE_MARGIN_PX = 140
BOTTOM_SAFE_PCT = 0.22
MAX_LINES = 2
BASE_FONT_SIZE = 44
LINE_SPACING_PX = 14

FADE_IN_SEC = 0.10
FADE_OUT_SEC = 0.12


@dataclass
class _PlacedWord:
    word: WordTimestamp
    x: int
    y: int
    line_index: int


@dataclass
class CaptionLayout:
    words: List[_PlacedWord]
    canvas_size: Tuple[int, int]
    lang: str
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)


def build_caption_layout(
    subtitles: List[WordTimestamp],
    lang: str,
    canvas_size: Tuple[int, int],
    side_margin_px: int = SIDE_MARGIN_PX,
    bottom_safe_pct: float = BOTTOM_SAFE_PCT,
    max_lines: int = MAX_LINES,
) -> CaptionLayout:
    """Wrap subtitle words into <= max_lines within the bottom safe area,
    left-to-right, and record each word's draw position."""
    W, H = canvas_size
    font = typography.load_font(lang, "bold", BASE_FONT_SIZE)
    max_width = W - 2 * side_margin_px
    safe_top = H - int(H * bottom_safe_pct)
    line_height = BASE_FONT_SIZE + LINE_SPACING_PX
    space_width = typography.measure_text(" ", font)[0] or round(BASE_FONT_SIZE * 0.28)
    word_gap = space_width + round(BASE_FONT_SIZE * 0.45)

    def line_width(words: List[WordTimestamp]) -> int:
        if not words:
            return 0
        total = sum(typography.measure_text(w.word, font)[0] for w in words)
        return total + (len(words) - 1) * word_gap

    lines: List[List[WordTimestamp]] = [[]]
    for wt in subtitles:
        candidate = lines[-1] + [wt]
        if lines[-1] and line_width(candidate) > max_width:
            if len(lines) == max_lines:
                break
            lines.append([wt])
        else:
            lines[-1] = candidate
    line_widths = [line_width(l) for l in lines]

    placed: List[_PlacedWord] = []
    n_lines = len(lines)
    block_height = n_lines * line_height
    start_y = safe_top + (H - safe_top - block_height) // 2

    min_x, max_x = W, 0
    min_y, max_y = start_y, start_y + block_height

    for line_idx, line_words in enumerate(lines):
        y = start_y + line_idx * line_height
        x = side_margin_px + (max_width - line_widths[line_idx]) // 2  # centred line
        if line_words:
            min_x = min(min_x, x)
        for wt in line_words:
            placed.append(_PlacedWord(word=wt, x=x, y=y, line_index=line_idx))
            w_advance = typography.measure_text(wt.word, font)[0]
            max_x = max(max_x, x + w_advance)
            x += w_advance + word_gap

    pad_x, pad_y = 32, 16
    container_box = (
        max(min_x - pad_x, side_margin_px // 2),
        max(min_y - pad_y, safe_top),
        min(max_x + pad_x, W - side_margin_px // 2),
        min(max_y + pad_y, H - 24),
    )

    return CaptionLayout(words=placed, canvas_size=canvas_size, lang=lang, box=container_box)


def _interpolate_rgb(
    c1: Tuple[int, int, int], c2: Tuple[int, int, int], progress: float
) -> Tuple[int, int, int]:
    """Smooth cosine interpolation between RGB colors."""
    p = min(max(progress, 0.0), 1.0)
    p_eased = 0.5 - 0.5 * math.cos(math.pi * p)
    return (
        round(c1[0] + (c2[0] - c1[0]) * p_eased),
        round(c1[1] + (c2[1] - c1[1]) * p_eased),
        round(c1[2] + (c2[2] - c1[2]) * p_eased),
    )


def _word_color_rgb(t: float, wt: WordTimestamp) -> Tuple[int, int, int]:
    """Computes smooth fade-in, spoken fill, and fade-out color transitions."""
    spoken_rgb = COLOR_CORE_FACT_RGB if wt.is_core_fact else COLOR_SPOKEN_RGB

    if t < wt.start_sec - FADE_IN_SEC:
        return COLOR_PENDING_RGB
    elif t < wt.start_sec:
        # Smooth fade-in from pending gray to vibrant spoken color
        p = (t - (wt.start_sec - FADE_IN_SEC)) / FADE_IN_SEC
        return _interpolate_rgb(COLOR_PENDING_RGB, spoken_rgb, p)
    elif t <= wt.end_sec:
        # Fully illuminated active word
        return spoken_rgb
    elif t <= wt.end_sec + FADE_OUT_SEC:
        # Smooth fade-out from spoken color to past white
        p = (t - wt.end_sec) / FADE_OUT_SEC
        return _interpolate_rgb(spoken_rgb, COLOR_PAST_RGB, p)
    else:
        return COLOR_PAST_RGB


def render_caption_frame(layout: CaptionLayout, t: float) -> Image.Image:
    """Render the caption block for time t with fast direct drawing and smooth color fills."""
    frame = Image.new("RGBA", layout.canvas_size, (0, 0, 0, 0))
    if not layout.words:
        return frame

    # 1. Subtle frosted glass backing container (for whole caption box)
    bx0, by0, bx1, by1 = layout.box
    if bx1 > bx0 and by1 > by0:
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, fill=(15, 23, 42, 205))
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, outline=(255, 255, 255, 35), width=1)

    font = typography.load_font(layout.lang, "bold", BASE_FONT_SIZE)

    for pw in layout.words:
        rgb = _word_color_rgb(t, pw.word)
        word_text = pw.word.word

        # Fast direct drawing onto frame with drop shadow
        if typography.shaping.SHAPING_AVAILABLE:
            typography.shaping.draw_shaped_text(
                frame, word_text, font.path, font.size, (pw.x, pw.y + 2), (0, 0, 0), language=font.language_tag
            )
            typography.shaping.draw_shaped_text(
                frame, word_text, font.path, font.size, (pw.x, pw.y), rgb, language=font.language_tag
            )
        else:
            hex_color = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
            d = ImageDraw.Draw(frame)
            d.text((pw.x, pw.y + 2), word_text, font=font.pillow, fill="#000000")
            d.text((pw.x, pw.y), word_text, font=font.pillow, fill=hex_color)

    return frame


def build_caption_frame_cache(layout: CaptionLayout) -> List[Tuple[float, Image.Image]]:
    """Generates an optimized, fast frame cache at word transition boundaries."""
    if not layout.words:
        return [(0.0, Image.new("RGBA", layout.canvas_size, (0, 0, 0, 0)))]

    timestamps = {0.0}
    for pw in layout.words:
        timestamps.add(round(pw.word.start_sec, 3))
        timestamps.add(round(pw.word.end_sec, 3))

    sorted_times = sorted(timestamps)
    return [(ts, render_caption_frame(layout, ts)) for ts in sorted_times]


def get_caption_frame_for_time(cache: List[Tuple[float, Image.Image]], t: float) -> Image.Image:
    times = [ts for ts, _ in cache]
    idx = bisect.bisect_right(times, t) - 1
    idx = max(idx, 0)
    return cache[idx][1]
