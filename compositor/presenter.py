"""Split-screen presenter panel (pre-baked avatar loop + disclosure label).

The presenter is a looping MP4 read from disk, never generated at render
time, so a frame of output is still an auditable asset rather than something
a model invented mid-render (README section 3.1's stated rationale).

Two hard rules are enforced here rather than left to the caller:

1. The disclosure label is drawn for as long as the presenter is on screen.
   `build_presenter_panel` has no way to switch it off.
2. Layout is derived from the panel split, so the fact card's text budgets
   shrink with it. A presenter halves the usable width; section 7.3's
   character budgets assume full width and will overflow if reused as-is.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image, ImageDraw

from compositor import typography

logger = logging.getLogger(__name__)

# Fraction of the frame width given to the presenter panel.
PRESENTER_WIDTH_FRAC = 0.38
PANEL_MARGIN = 48
PANEL_RADIUS = 24
DISCLOSURE_HEIGHT = 40
DISCLOSURE_BG = (15, 23, 42, 225)
DISCLOSURE_FG = "#FACC15"


@dataclass(frozen=True)
class PresenterLayout:
    """Geometry for a split-screen frame."""

    panel_box: Tuple[int, int, int, int]      # presenter panel (l, t, r, b)
    content_box: Tuple[int, int, int, int]    # remaining area for the fact card

    @property
    def panel_size(self) -> Tuple[int, int]:
        l, t, r, b = self.panel_box
        return (r - l, b - t)

    @property
    def content_width(self) -> int:
        l, _, r, _ = self.content_box
        return r - l


def compute_layout(
    canvas_size: Tuple[int, int],
    caption_reserve: int,
    width_frac: float = PRESENTER_WIDTH_FRAC,
) -> PresenterLayout:
    """Split the frame into presenter and content panels.

    `caption_reserve` is the height the subtitle bar occupies at the bottom;
    both panels stop above it so captions stay full-width and unobstructed.
    """
    W, H = canvas_size
    usable_bottom = H - caption_reserve
    panel_w = int(W * width_frac) - PANEL_MARGIN

    panel_box = (PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN + panel_w, usable_bottom - PANEL_MARGIN)
    content_box = (panel_box[2] + PANEL_MARGIN, PANEL_MARGIN, W - PANEL_MARGIN, usable_bottom - PANEL_MARGIN)
    return PresenterLayout(panel_box=panel_box, content_box=content_box)


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def fit_presenter_frame(frame: Image.Image, panel_size: Tuple[int, int]) -> Image.Image:
    """Cover-fit a presenter frame into the panel, centre-cropped and rounded."""
    pw, ph = panel_size
    scale = max(pw / frame.width, ph / frame.height)
    resized = frame.resize((max(round(frame.width * scale), pw), max(round(frame.height * scale), ph)), Image.BILINEAR)

    left = (resized.width - pw) // 2
    top = (resized.height - ph) // 2
    cropped = resized.crop((left, top, left + pw, top + ph)).convert("RGBA")
    cropped.putalpha(_rounded_mask((pw, ph), PANEL_RADIUS))
    return cropped


def build_disclosure_strip(
    label: str, panel_size: Tuple[int, int], lang: str = "en"
) -> Image.Image:
    """The 'AI-generated presenter' bar pinned to the bottom of the panel."""
    pw, _ph = panel_size
    strip = Image.new("RGBA", (pw, DISCLOSURE_HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(strip).rounded_rectangle(
        [0, 0, pw - 1, DISCLOSURE_HEIGHT - 1], radius=12, fill=DISCLOSURE_BG
    )

    font = typography.load_font(lang, "bold", 20)
    text_w, text_h = typography.measure_text(label, font)
    strip.alpha_composite(
        typography.draw_text_layer(
            label, font, DISCLOSURE_FG, (pw, DISCLOSURE_HEIGHT),
            (max((pw - text_w) // 2, 8), max((DISCLOSURE_HEIGHT - text_h) // 2 - 4, 0)),
        )
    )
    return strip


def build_presenter_panel(
    presenter_frame: Image.Image,
    disclosure_label: str,
    layout: PresenterLayout,
    lang: str = "en",
) -> Image.Image:
    """A complete presenter panel: fitted video frame plus disclosure strip.

    The label is always drawn. There is deliberately no flag to disable it.
    """
    if not disclosure_label or not disclosure_label.strip():
        raise ValueError(
            "a presenter panel requires a non-empty disclosure_label; "
            "an unlabelled synthetic presenter is not permitted"
        )

    panel_size = layout.panel_size
    panel = fit_presenter_frame(presenter_frame, panel_size)

    strip = build_disclosure_strip(disclosure_label, panel_size, lang)
    panel.alpha_composite(strip, dest=(0, panel_size[1] - DISCLOSURE_HEIGHT - 12))
    return panel
