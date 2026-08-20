"""Word-level karaoke caption rendering (README §8.6 layer 2, Appendix D).

Layout is computed once per scene; a caption frame is cached once per word
transition (not once per output frame) since a ~7s/210-frame scene typically
has only 8-12 word transitions — a large reduction in per-frame Pillow work.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image

from compositor import typography
from models.schemas import WordTimestamp

COLOR_SPOKEN = "#FACC15"
COLOR_PENDING = "#F8FAFC"
COLOR_PAST = "#94A3B8"

SIDE_MARGIN_PX = 140
BOTTOM_SAFE_PCT = 0.22
MAX_LINES = 2
ACTIVE_SCALE = 1.15
BASE_FONT_SIZE = 44
LINE_SPACING_PX = 14


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
    # Reserved headroom beyond the space so an active word's 1.15x scale
    # (applied around its own centre) never collides with its neighbour —
    # sized generously since growth scales with word width, not font size.
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
                break  # remaining words simply don't get captioned this scene
            lines.append([wt])
        else:
            lines[-1] = candidate
    line_widths = [line_width(l) for l in lines]

    placed: List[_PlacedWord] = []
    n_lines = len(lines)
    block_height = n_lines * line_height
    start_y = safe_top + (H - safe_top - block_height) // 2

    for line_idx, line_words in enumerate(lines):
        y = start_y + line_idx * line_height
        x = side_margin_px + (max_width - line_widths[line_idx]) // 2  # centred line
        for wt in line_words:
            placed.append(_PlacedWord(word=wt, x=x, y=y, line_index=line_idx))
            x += typography.measure_text(wt.word, font)[0] + word_gap

    return CaptionLayout(words=placed, canvas_size=canvas_size, lang=lang)


def _word_color(t: float, wt: WordTimestamp) -> str:
    if t < wt.start_sec:
        return COLOR_PENDING
    if t <= wt.end_sec:
        return COLOR_SPOKEN
    return COLOR_PAST


def render_caption_frame(layout: CaptionLayout, t: float) -> Image.Image:
    """Render the full caption block for a given time t.

    Active-word emphasis is applied as an image-space scale around the
    word's own centre (not a larger font size drawn in place) — scaling the
    font in place would widen the glyph run and shove the next word's fixed
    layout position, causing visible overlap between adjacent words.
    """
    frame = Image.new("RGBA", layout.canvas_size, (0, 0, 0, 0))
    font = typography.load_font(layout.lang, "bold", BASE_FONT_SIZE)

    for pw in layout.words:
        color = _word_color(t, pw.word)
        is_active = color == COLOR_SPOKEN
        word_text = pw.word.word
        word_layer = typography.draw_text_layer(word_text, font, color, layout.canvas_size, (pw.x, pw.y))

        if is_active:
            left, top, right, bottom = typography.text_pixel_bbox(word_text, font)
            if right > left and bottom > top:
                pad = 6
                box = (pw.x + left - pad, pw.y + top - pad, pw.x + right + pad, pw.y + bottom + pad)
                crop = word_layer.crop(box)
                scaled = crop.resize((round(crop.width * ACTIVE_SCALE), round(crop.height * ACTIVE_SCALE)), Image.LANCZOS)
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                paste_xy = (max(round(cx - scaled.width / 2), 0), max(round(cy - scaled.height / 2), 0))
                word_layer = Image.new("RGBA", layout.canvas_size, (0, 0, 0, 0))
                word_layer.alpha_composite(scaled, dest=paste_xy)

        frame.alpha_composite(word_layer)

    return frame


def build_caption_frame_cache(layout: CaptionLayout) -> List[Tuple[float, Image.Image]]:
    """One rendered frame per word-boundary transition, sorted by time.

    Each entry's timestamp is when that frame becomes valid (i.e. holds until
    the next entry's timestamp).
    """
    if not layout.words:
        return [(0.0, Image.new("RGBA", layout.canvas_size, (0, 0, 0, 0)))]

    transition_times = sorted({0.0} | {pw.word.start_sec for pw in layout.words} | {pw.word.end_sec for pw in layout.words})
    return [(ts, render_caption_frame(layout, ts)) for ts in transition_times]


def get_caption_frame_for_time(cache: List[Tuple[float, Image.Image]], t: float) -> Image.Image:
    times = [ts for ts, _ in cache]
    idx = bisect.bisect_right(times, t) - 1
    idx = max(idx, 0)
    return cache[idx][1]
