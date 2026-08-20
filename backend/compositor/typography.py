"""Font resolution, text measurement and drawing (README §5.4, §7.3, Appendix C).

Fonts are always loaded from assets/fonts/ — never resolved from the OS.
Layout and rasterisation go through compositor/shaping.py (HarfBuzz +
FreeType) so Indic scripts reorder and ligate correctly; Pillow's own text
path is only a fallback when those libraries are unavailable.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

# README §5.4 documents running this file directly ("python
# compositor/typography.py --selftest"), which puts compositor/ on sys.path
# rather than the repo root. Make the package importable either way.
if __package__ in (None, ""):  # pragma: no cover - script invocation only
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compositor import shaping

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# language -> weight -> filename (Appendix C). Only "en" is bundled in this slice;
# the others are declared so the fallback chain has a documented, correct target
# even before the files exist.
FONT_FILES: Dict[str, Dict[str, str]] = {
    "en": {"bold": "NotoSans-Bold.ttf", "regular": "NotoSans-Regular.ttf"},
    "hi": {"bold": "NotoSansDevanagari-Bold.ttf"},
    "mr": {"bold": "NotoSansDevanagari-Bold.ttf"},
    "ta": {"bold": "NotoSansTamil-Bold.ttf"},
    "te": {"bold": "NotoSansTelugu-Bold.ttf"},
    "bn": {"bold": "NotoSansBengali-Bold.ttf"},
}

# (latin_max, indic_max) character budgets, README §7.3.
CHAR_BUDGETS: Dict[str, Tuple[int, int]] = {
    "badge_tag": (22, 18),
    "headline": (58, 46),
    "subtext": (96, 80),
    "highlight_metric": (12, 12),
    "highlight_sublabel": (32, 26),
}

_LATIN_LANGS = {"en"}

_font_cache: Dict[Tuple[str, str, int], ImageFont.FreeTypeFont] = {}


class MissingFontError(Exception):
    pass


@dataclass(frozen=True)
class Font:
    """A resolved font at a specific size.

    Wraps the file path rather than a Pillow font object, because text is
    shaped by HarfBuzz and rasterised by FreeType (see compositor/shaping.py)
    — Pillow's own text path cannot lay out Indic scripts correctly. The
    Pillow object is kept only for the no-shaping fallback.
    """

    path: str
    size: int
    lang: str

    @property
    def language_tag(self) -> str:
        return self.lang

    @property
    def pillow(self) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.path, self.size)


def _resolve_font_path(lang: str, weight: str) -> Path:
    weights = FONT_FILES.get(lang, FONT_FILES["en"])
    filename = weights.get(weight) or next(iter(weights.values()))
    return FONTS_DIR / filename


def load_font(lang: str, weight: str, size_px: int) -> Font:
    """Load a bundled font. Falls back to English if the requested language's
    font file is missing, so callers never crash mid-render for want of a
    script that has not been bundled yet."""
    key = (lang, weight, size_px)
    if key in _font_cache:
        return _font_cache[key]

    path = _resolve_font_path(lang, weight)
    if not path.exists() and lang != "en":
        logger.warning("Font missing for lang=%s weight=%s (%s); falling back to English", lang, weight, path.name)
        path = _resolve_font_path("en", weight)

    if not path.exists():
        raise MissingFontError(f"Required font not found: {path}")

    font = Font(path=str(path), size=size_px, lang=lang)
    _font_cache[key] = font
    return font


def is_indic(lang: str) -> bool:
    return lang not in _LATIN_LANGS


def char_budget(field: str, lang: str) -> int:
    latin_max, indic_max = CHAR_BUDGETS[field]
    return latin_max if not is_indic(lang) else indic_max


def enforce_budget(text: str, field: str, lang: str) -> str:
    limit = char_budget(field, lang)
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def measure_text(text: str, font: Font) -> Tuple[int, int]:
    """Advance width and ink height of `text`.

    Width is the shaped advance, not the ink extent: laying text out by ink
    width collapses the side bearings and makes words visibly collide. Height
    stays the ink extent, which is what the vertical centring callers do
    expects.
    """
    if not text:
        return (0, 0)
    if shaping.SHAPING_AVAILABLE:
        width = shaping.advance_width(text, font.path, font.size)
        top, bottom = shaping.ink_bbox(text, font.path, font.size)[1::2]
        return (int(round(width)), int(bottom - top))
    bbox = font.pillow.getbbox(text)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


def text_pixel_bbox(text: str, font: Font) -> Tuple[int, int, int, int]:
    """(left, top, right, bottom) of the drawn pixels relative to the (x, y)
    origin passed to draw_text_layer — unlike measure_text this preserves the
    top/left offsets, which matter when cropping tightly around one word
    (karaoke active-word scaling)."""
    if shaping.SHAPING_AVAILABLE:
        return shaping.ink_bbox(text, font.path, font.size)
    return font.pillow.getbbox(text)


def wrap_text(text: str, font: Font, max_width_px: int, max_lines: int = 2) -> List[str]:
    """Greedy word-wrap to at most max_lines, ellipsising the last line if it overflows."""
    words = text.split()
    if not words:
        return [""]

    lines: List[str] = []
    current: List[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if measure_text(candidate, font)[0] <= max_width_px or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))

    remaining_words = words[sum(len(l.split()) for l in lines):]
    if remaining_words and lines:
        last = lines[-1]
        while measure_text(last + "…", font)[0] > max_width_px and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last.rstrip() + "…"

    return lines[:max_lines]


def _to_rgb(color: str) -> Tuple[int, int, int]:
    from PIL import ImageColor

    return ImageColor.getrgb(color)[:3]


def draw_text_layer(
    text: str,
    font: Font,
    color: str,
    canvas_size: Tuple[int, int],
    xy: Tuple[int, int],
    align: str = "left",
) -> Image.Image:
    """Render text onto a transparent RGBA layer the size of the full canvas,
    so it can be alpha-composited directly onto other layers."""
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if not text:
        return layer

    if shaping.SHAPING_AVAILABLE:
        shaping.draw_shaped_text(
            layer, text, font.path, font.size, xy, _to_rgb(color), language=font.language_tag
        )
    else:
        ImageDraw.Draw(layer).text(xy, text, font=font.pillow, fill=color, align=align)
    return layer


def draw_text_with_shadow(
    text: str,
    font: Font,
    color: str,
    canvas_size: Tuple[int, int],
    xy: Tuple[int, int],
    shadow_color: str = "#000000",
    shadow_offset: Tuple[int, int] = (2, 4),
    shadow_alpha: int = 180,
) -> Image.Image:
    """Render text with a subtle drop shadow for crisp readability over motion backgrounds."""
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if not text:
        return layer

    sx, sy = xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]
    shadow_rgb = _to_rgb(shadow_color)
    shadow_layer = draw_text_layer(text, font, shadow_color, canvas_size, (sx, sy))
    # Apply shadow alpha
    r, g, b, a = shadow_layer.split()
    a = a.point(lambda v: int(v * (shadow_alpha / 255.0)))
    shadow_layer = Image.merge("RGBA", (r, g, b, a))

    text_layer = draw_text_layer(text, font, color, canvas_size, xy)
    layer.alpha_composite(shadow_layer)
    layer.alpha_composite(text_layer)
    return layer


def render_selftest(out_path: str = "assets/fonts/_selftest.png") -> Path:
    """One sample line per language. Missing font files render a visible
    placeholder line instead of crashing, so this stays runnable with only
    English bundled (README §5.4)."""
    samples = {
        "en": "The quick brown fox — PM-KISAN ₹2,000",
        "hi": "यह एक परीक्षण वाक्य है — पीएम-किसान",
        "ta": "இது ஒரு சோதனை வாக்கியம்",
        "te": "ఇది ఒక పరీక్ష వాక్యం",
        "bn": "এটি একটি পরীক্ষামূলক বাক্য",
        "mr": "हे एक चाचणी वाक्य आहे",
    }

    size_px = 36
    line_height = size_px + 24
    canvas_size = (1100, line_height * (len(samples) + 1) + 30)
    canvas = Image.new("RGBA", canvas_size, (17, 17, 17, 255))

    # The "[hi]" style label is Latin, so it must be drawn with the Latin face.
    # Drawing it with the language's own font renders tofu for every Indic
    # script and makes a working font look broken.
    label_font = load_font("en", "bold", size_px)
    label_width = measure_text("[xx] ", label_font)[0] + 8

    engine = "HarfBuzz+FreeType" if shaping.SHAPING_AVAILABLE else "Pillow (NO complex shaping)"
    logger.info("Typography selftest using %s", engine)

    y = 10
    for lang, text in samples.items():
        path = _resolve_font_path(lang, "bold")
        canvas.alpha_composite(draw_text_layer(f"[{lang}]", label_font, "#94A3B8", canvas_size, (10, y)))
        if path.exists():
            font = load_font(lang, "bold", size_px)
            canvas.alpha_composite(draw_text_layer(text, font, "#F8FAFC", canvas_size, (10 + label_width, y)))
        else:
            canvas.alpha_composite(draw_text_layer(
                f"MISSING: {path.name}", label_font, "#EF4444", canvas_size, (10 + label_width, y)
            ))
        y += line_height

    canvas.alpha_composite(draw_text_layer(
        f"shaping: {engine}", label_font, "#64748B", canvas_size, (10, y)
    ))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out)
    logger.info("Wrote typography selftest to %s", out)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--selftest" in sys.argv:
        render_selftest()
    else:
        print("Usage: python compositor/typography.py --selftest")
