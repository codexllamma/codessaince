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
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from compositor import typography

# Presenter motion is a subtle idle loop — blinks and small head movement —
# so sampling it below the output frame rate is not visible, and it halves
# the frames held in memory. Raise it if a clip has fast motion.
PRESENTER_SAMPLE_FPS = 15

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


@lru_cache(maxsize=8)
def panel_mask(size: Tuple[int, int], radius: int = PANEL_RADIUS) -> Image.Image:
    """Rounded-corner alpha for the panel. Identical every frame, so it is
    built once and reused as a shared paste mask rather than baked into each
    frame's alpha channel — that keeps cached frames at 3 bytes per pixel."""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def fit_presenter_frame(frame: Image.Image, panel_size: Tuple[int, int], rounded: bool = True) -> Image.Image:
    """Cover-fit a presenter frame into the panel, centre-cropped.

    With `rounded=False` the result is RGB and the caller is expected to paste
    it through `panel_mask()`; that is the cheap path used per frame.
    """
    pw, ph = panel_size
    scale = max(pw / frame.width, ph / frame.height)
    resized = frame.resize(
        (max(round(frame.width * scale), pw), max(round(frame.height * scale), ph)), Image.BILINEAR
    )

    left = (resized.width - pw) // 2
    top = (resized.height - ph) // 2
    cropped = resized.crop((left, top, left + pw, top + ph))

    if not rounded:
        return cropped.convert("RGB")

    cropped = cropped.convert("RGBA")
    cropped.putalpha(panel_mask((pw, ph)))
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


class PresenterSource:
    """A pre-baked presenter loop, decoded once and ready for O(1) lookup.

    Decoding a video frame inside the per-frame render path would undo the
    compositing work: seeking backwards at every loop boundary is expensive,
    and the whole point of pre-baking is that no inference or decode happens
    during rendering. So the loop is decoded once at panel size, the
    disclosure strip is burnt in, and each output frame is an index lookup.

    Frames are held as RGB and pasted through one shared rounded mask rather
    than each carrying its own alpha, which is a third less memory.
    """

    def __init__(self, frames: List[Image.Image], panel_size: Tuple[int, int], sample_fps: float):
        if not frames:
            raise ValueError("presenter source has no frames")
        self.frames = frames
        self.panel_size = panel_size
        self.sample_fps = sample_fps
        self.mask = panel_mask(panel_size)
        self.clip_path: Optional[Path] = None

    @classmethod
    def load(
        cls,
        video_path: str,
        layout: PresenterLayout,
        disclosure_label: str,
        lang: str = "en",
        sample_fps: float = PRESENTER_SAMPLE_FPS,
    ) -> "PresenterSource":
        if not disclosure_label or not disclosure_label.strip():
            raise ValueError(
                "a presenter source requires a non-empty disclosure_label; "
                "an unlabelled synthetic presenter is not permitted"
            )

        from moviepy import VideoFileClip

        panel_size = layout.panel_size
        strip = build_disclosure_strip(disclosure_label, panel_size, lang)
        strip_y = panel_size[1] - DISCLOSURE_HEIGHT - 12

        frames: List[Image.Image] = []
        clip = VideoFileClip(video_path)
        try:
            for arr in clip.iter_frames(fps=sample_fps, dtype="uint8"):
                fitted = fit_presenter_frame(Image.fromarray(arr), panel_size, rounded=False)
                fitted = fitted.convert("RGBA")
                fitted.alpha_composite(strip, dest=(0, strip_y))
                frames.append(fitted.convert("RGB"))
        finally:
            clip.close()

        logger.info(
            "presenter loop %s: %d frames at %.0f fps, panel %dx%d",
            video_path, len(frames), sample_fps, *panel_size,
        )
        source = cls(frames, panel_size, sample_fps)
        # Kept so the gesture sidecar can be found beside the clip later.
        source.clip_path = Path(video_path)
        return source

    def _frame_at_source(self, source_t: float) -> Image.Image:
        """Frame at a position in the source clip. Clamped, not wrapped: a
        gesture window lies inside the clip, so an out-of-range time is a
        scheduling bug and should pin to an end rather than jump elsewhere."""
        idx = int(source_t * self.sample_fps)
        return self.frames[min(max(idx, 0), len(self.frames) - 1)]

    def frame_at(self, t: float, track=None) -> Image.Image:
        """Frame for time `t`, choreographed by `track` if one is given.

        The track is an argument rather than state on this object because one
        source is shared by every scene in a job while the choreography is per
        scene. MoviePy builds all the scene clips before pulling any frames, so
        a track stored here would be overwritten by the last scene and every
        scene would render with the wrong one.

        Without a track the whole clip loops, which is what an unsegmented
        avatar does.
        """
        if track is None:
            idx = int(t * self.sample_fps) % len(self.frames)
            return self.frames[idx]

        source_a, source_b, weight = track.sample_at(t)
        frame = self._frame_at_source(source_a)
        if weight <= 0.0:
            return frame
        return Image.blend(frame, self._frame_at_source(source_b), weight)

    def paste_onto(self, frame: Image.Image, box: Tuple[int, int], t: float, track=None) -> None:
        frame.paste(self.frame_at(t, track), box, self.mask)
