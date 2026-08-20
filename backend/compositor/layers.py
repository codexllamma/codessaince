"""Top-level compositor orchestration (README §8.6): 5-layer canvas, dynamic
theming, kinetic typography, audio-synchronized metric reactions, and NVENC/libx264 encoding.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from compositor import _ffmpeg, gestures, karaoke, kenburns, presenter, typography
from models.schemas import SceneDefinition, VisualAssetSelection, WordTimestamp

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

ALERT_PILL_INSET = 96
ALERT_PILL_HEIGHT = 56
HEADLINE_GAP_BELOW_PILL = 28
METRIC_CARD_SIZE = (760, 340)
PULSE_HZ = 0.8

KENBURNS_RESAMPLE = Image.BILINEAR

# Presenter-mode card borders: a dark stroke plus a thin inner highlight, the
# same two-tone treatment karaoke.py already uses on the caption backing
# (glassmorphism fill + a faint top-light rim), reused here so the frame
# reads as one coherent broadcast graphic rather than two unrelated styles.
CARD_BORDER_WIDTH = 3
CARD_BORDER_COLOR = (8, 13, 26, 255)
CARD_BORDER_HIGHLIGHT = (255, 255, 255, 40)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _with_alpha(layer: Image.Image, factor: float) -> Image.Image:
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * min(max(factor, 0.0), 1.0)))
    return Image.merge("RGBA", (r, g, b, a))


def _draw_card_border(
    frame: Image.Image, box: Tuple[int, int, int, int], radius: int = presenter.PANEL_RADIUS
) -> None:
    """Dark rounded-rect stroke plus a faint inner highlight, drawn in place
    on `frame`. Mirrors the presenter panel's own corner radius so a card
    border always traces the panel it belongs to rather than clipping it.

    Drawn as the very last compositing step for a card's region so the
    border is always crisp on top — text and sprites sit inset from the
    box edges already, so nothing later in the frame paints over it.
    """
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    l, t, r, b = box
    draw.rounded_rectangle([l, t, r - 1, b - 1], radius=radius, outline=CARD_BORDER_COLOR, width=CARD_BORDER_WIDTH)
    inset = CARD_BORDER_WIDTH
    draw.rounded_rectangle(
        [l + inset, t + inset, r - 1 - inset, b - 1 - inset],
        radius=max(radius - inset, 0), outline=CARD_BORDER_HIGHLIGHT, width=1,
    )
    frame.alpha_composite(overlay) if frame.mode == "RGBA" else frame.paste(overlay, (0, 0), overlay)


def build_background_source(
    asset: VisualAssetSelection,
    canvas_w: int = VIDEO_WIDTH,
    canvas_h: int = VIDEO_HEIGHT,
    z_max: float = kenburns.Z_MAX_DEFAULT,
) -> Image.Image:
    """The still image Ken Burns pans across for this scene.

    Handles static_graphic (a real B-roll still) and mesh_gradient (the §10.2
    procedural fallback: a multi-point glowing atmospheric gradient). Anything
    present on disk is used; anything missing degrades to the gradient, which
    §10.2 specifies "always looks intentional and never looks broken" — a scene
    should never fail for want of an asset.

    Video loops are handled separately by build_background_video, because a
    clip cannot be reduced to one image.
    """
    if asset.asset_type == "static_graphic":
        image = _load_asset_image(asset, canvas_w, canvas_h, z_max)
        if image is not None:
            return _apply_dim_overlay(image, asset.dim_overlay_opacity)
    elif asset.asset_type == "video_loop":
        # The caller asks for a still even for a clip, as a fallback for when
        # the video cannot be opened. Use its first frame if we can.
        image = _first_video_frame(asset, canvas_w, canvas_h, z_max)
        if image is not None:
            return _apply_dim_overlay(image, asset.dim_overlay_opacity)

    if asset.asset_type != "mesh_gradient":
        logger.info(
            "asset %s (%s, %s) unavailable; using the mesh_gradient fallback (README §10.2)",
            asset.asset_id, asset.file_path or "<no path>", asset.asset_type,
        )

    w, h = round(z_max * canvas_w), round(z_max * canvas_h)
    accent = _hex_to_rgb(asset.accent_color)
    dark = tuple(int(c * 0.12) for c in accent)
    deep_bg = (8, 14, 28)

    yy, xx = np.mgrid[0:h, 0:w]
    diag = (xx / w + yy / h) / 2.0
    gradient = np.empty((h, w, 3), dtype=np.float32)
    for c in range(3):
        gradient[:, :, c] = deep_bg[c] + (dark[c] - deep_bg[c]) * diag

    # Light Orb 1: Primary Accent glow in upper-right / center
    cx1, cy1 = w * 0.45, h * 0.3
    dist1 = np.sqrt((xx - cx1) ** 2 + (yy - cy1) ** 2) / (0.75 * max(w, h))
    highlight1 = np.clip(1.0 - dist1, 0, 1) ** 2.2
    for c in range(3):
        gradient[:, :, c] += highlight1 * accent[c] * 0.75

    # Light Orb 2: Secondary soft ambient glow in bottom-left
    cx2, cy2 = w * 0.8, h * 0.75
    dist2 = np.sqrt((xx - cx2) ** 2 + (yy - cy2) ** 2) / (0.6 * max(w, h))
    highlight2 = np.clip(1.0 - dist2, 0, 1) ** 2.0
    for c in range(3):
        gradient[:, :, c] += highlight2 * accent[c] * 0.45

    # Subtle film grain / texture to eliminate 8-bit color banding
    rng = np.random.default_rng(abs(hash(asset.asset_id)) % (2**32))
    gradient += rng.normal(0, 3.5, size=(h, w, 1))

    gradient = np.clip(gradient, 0, 255).astype(np.uint8)
    img = Image.fromarray(gradient).convert("RGBA")
    return _apply_dim_overlay(img, asset.dim_overlay_opacity)


def _cover_fit(
    img: Image.Image, target_w: int, target_h: int, resample: int = Image.LANCZOS
) -> Image.Image:
    """Scale to cover target_w x target_h, centre-cropped. Never letterboxes:
    a bar down the side of a government notice reads as a mistake.

    Stills are fitted once per scene so they get LANCZOS; clip frames are
    fitted once per rendered frame and pass BILINEAR instead.
    """
    if img.width == target_w and img.height == target_h:
        # B-roll authored at the output size is the common case, and resizing
        # it to itself costs ~40ms a frame for nothing.
        return img.convert("RGBA")

    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize(
        (max(round(img.width * scale), target_w), max(round(img.height * scale), target_h)),
        resample,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h)).convert("RGBA")


def _apply_dim_overlay(img: Image.Image, opacity: float) -> Image.Image:
    """B-roll is a backdrop for text, so it is dimmed before anything lands on
    it (§8.6 layer 1). Without this, captions lose contrast over bright areas.

    Compositing black at alpha `a` is the same as scaling each channel by
    (1 - a), and the multiply is roughly half the cost of building an overlay
    image and alpha-compositing it — which matters because clip frames are
    dimmed once per rendered frame.
    """
    if opacity <= 0:
        return img
    keep = 1.0 - min(opacity, 1.0)
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint16)
    dimmed = (rgb * int(keep * 256) >> 8).astype(np.uint8)
    return Image.fromarray(dimmed).convert("RGBA")


def _asset_path(asset: VisualAssetSelection) -> Optional[Path]:
    if not asset.file_path:
        return None
    path = Path(asset.file_path)
    return path if path.is_file() else None


def _load_asset_image(
    asset: VisualAssetSelection, canvas_w: int, canvas_h: int, z_max: float
) -> Optional[Image.Image]:
    path = _asset_path(asset)
    if path is None:
        return None
    try:
        with Image.open(path) as raw:
            raw.load()
            source = raw.convert("RGB")
    except Exception:
        logger.warning("could not read image asset %s at %s", asset.asset_id, path, exc_info=True)
        return None

    target = (round(z_max * canvas_w), round(z_max * canvas_h))
    if source.width < target[0] or source.height < target[1]:
        # Upscaling past native resolution is exactly what §8.6 forbids, but a
        # slightly soft background beats failing the scene. Warn so the asset
        # can be replaced with one that meets the 2560x1440 recommendation.
        logger.warning(
            "asset %s is %dx%d, below the %dx%d needed for Ken Burns headroom; it will be upscaled",
            asset.asset_id, source.width, source.height, *target,
        )
    return _cover_fit(source, *target)


def _first_video_frame(
    asset: VisualAssetSelection, canvas_w: int, canvas_h: int, z_max: float
) -> Optional[Image.Image]:
    path = _asset_path(asset)
    if path is None:
        return None
    try:
        from moviepy import VideoFileClip

        with VideoFileClip(str(path)) as clip:
            frame = Image.fromarray(clip.get_frame(0))
    except Exception:
        logger.warning("could not read video asset %s at %s", asset.asset_id, path, exc_info=True)
        return None
    return _cover_fit(frame, round(z_max * canvas_w), round(z_max * canvas_h))


class VideoBackground:
    """A B-roll clip, decoded on demand and looped to any scene length.

    Not pre-decoded like the presenter loop: a full-frame background is ~6MB
    per frame, so a 10s clip would run to gigabytes. Rendering walks time
    forwards, which is what MoviePy's reader is fastest at, and the single
    backward seek per loop is cheap by comparison.

    Frames are fitted straight to the output size, not to Ken Burns headroom,
    and the compositor skips the Ken Burns pass for clips. A moving clip is
    already the "ambient motion" §8.6 wants; panning across it would mean
    upscaling every frame past its native resolution — the one thing §8.6
    explicitly forbids — to add motion that is already there. Doing both cost
    two resizes per frame and 103ms; this costs one.
    """

    def __init__(self, clip, canvas_w: int, canvas_h: int, z_max: float, dim: float):
        self.clip = clip
        self.target = (canvas_w, canvas_h)
        self.dim = dim
        self.duration = float(clip.duration or 0.0)
        self._last_key = None
        self._last_frame = None

    @classmethod
    def load(
        cls, asset: VisualAssetSelection, canvas_w: int, canvas_h: int, z_max: float
    ) -> Optional["VideoBackground"]:
        path = _asset_path(asset)
        if path is None or asset.asset_type != "video_loop":
            return None
        try:
            from moviepy import VideoFileClip

            clip = VideoFileClip(str(path))
        except Exception:
            logger.warning("could not open video asset %s at %s", asset.asset_id, path, exc_info=True)
            return None
        if not clip.duration:
            clip.close()
            return None
        logger.info("B-roll %s: %.1fs loop from %s", asset.asset_id, clip.duration, path)
        return cls(clip, canvas_w, canvas_h, z_max, asset.dim_overlay_opacity)

    def frame_at(self, t: float) -> Image.Image:
        """The dimmed, output-sized frame for time `t`, as RGB.

        Deliberately numpy-first: the naive route (fromarray, convert RGBA,
        convert back to RGB to dim, convert to RGBA again) spent most of its
        time on full-frame mode conversions the compositor then undoes, since
        frame_function wants RGB anyway.
        """
        wrapped = t % self.duration if self.duration else 0.0
        # Quantise so repeated calls at the same output frame reuse the decode.
        key = round(wrapped * VIDEO_FPS)
        if key == self._last_key and self._last_frame is not None:
            return self._last_frame

        arr = self.clip.get_frame(wrapped)
        target_w, target_h = self.target
        if (arr.shape[1], arr.shape[0]) != (target_w, target_h):
            fitted = _cover_fit(Image.fromarray(arr), target_w, target_h, resample=KENBURNS_RESAMPLE)
            arr = np.asarray(fitted.convert("RGB"))

        if self.dim > 0:
            keep = int((1.0 - min(self.dim, 1.0)) * 256)
            arr = ((arr.astype(np.uint16) * keep) >> 8).astype(np.uint8)

        frame = Image.fromarray(arr)
        self._last_key, self._last_frame = key, frame
        return frame

    def close(self) -> None:
        try:
            self.clip.close()
        except Exception:
            logger.debug("failed to close background clip", exc_info=True)


def build_background_video(
    asset: VisualAssetSelection,
    canvas_w: int = VIDEO_WIDTH,
    canvas_h: int = VIDEO_HEIGHT,
    z_max: float = kenburns.Z_MAX_DEFAULT,
) -> Optional[VideoBackground]:
    """A VideoBackground for video_loop assets, or None for everything else."""
    return VideoBackground.load(asset, canvas_w, canvas_h, z_max)


def _build_metric_card(
    scene: SceneDefinition,
    lang: str,
    canvas_size: Tuple[int, int],
    content_box: Optional[Tuple[int, int, int, int]] = None,
    glow_intensity: float = 0.0,
    scale_factor: float = 1.0,
) -> Image.Image:
    """Glassmorphism Metric Card with glowing borders and dynamic typography."""
    W, H = canvas_size
    card_w, card_h = METRIC_CARD_SIZE
    if content_box is None:
        x0, y0 = (W - card_w) // 2, (H - card_h) // 2 + 10
    else:
        cl, ct, cr, cb = content_box
        card_w = min(card_w, (cr - cl) - 80)
        card_h = min(card_h, (cb - ct) // 2)
        x0 = cl + ((cr - cl) - card_w) // 2
        y0 = cb - card_h - 48

    accent = _hex_to_rgb(scene.asset.accent_color)
    radius = 28

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # 1. Multi-layered Outer Glow Rings (intensifies when fact is actively spoken)
    glow_layers = 10 if glow_intensity > 0.1 else 6
    base_alpha = 45 if glow_intensity > 0.1 else 25
    for i in range(glow_layers, 0, -1):
        alpha = int((base_alpha + glow_intensity * 60) * (i / glow_layers))
        draw.rounded_rectangle(
            [x0 - i * 2, y0 - i * 2, x0 + card_w + i * 2, y0 + card_h + i * 2],
            radius=radius + i * 2,
            outline=accent + (min(alpha, 255),),
            width=2,
        )

    # 2. Frosted Glass Dark Fill with inner specular highlight
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=radius, fill=(13, 20, 38, 225))
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=radius, outline=accent + (240,), width=3)
    # Subtle top edge light
    draw.line([x0 + radius, y0 + 1, x0 + card_w - radius, y0 + 1], fill=(255, 255, 255, 120), width=2)

    # 3. Typography & Badges inside Metric Card
    vh = scene.visual_hierarchy
    metric_text = typography.enforce_budget(vh.highlight_metric or "", "highlight_metric", lang)
    sublabel_text = typography.enforce_budget(vh.highlight_sublabel or "", "highlight_sublabel", lang)

    metric_size = 96 if content_box is None else 72
    metric_font = typography.load_font(lang, "bold", metric_size)
    sublabel_font = typography.load_font(lang, "regular" if lang == "en" else "bold", 32)

    # Metric Value (e.g. ₹2,000 / 31st October 2026) with crisp drop shadow
    mw, mh = typography.measure_text(metric_text, metric_font)
    metric_color = "#FEF08A" if glow_intensity > 0.3 else "#F8FAFC"
    layer.alpha_composite(typography.draw_text_with_shadow(
        metric_text, metric_font, metric_color, (W, H),
        (x0 + (card_w - mw) // 2, y0 + card_h // 2 - mh - 8),
        shadow_offset=(0, 4), shadow_alpha=160,
    ))

    # Sublabel with pill container
    if sublabel_text:
        sw, sh = typography.measure_text(sublabel_text, sublabel_font)
        sub_x = x0 + (card_w - sw) // 2
        sub_y = y0 + card_h // 2 + 18
        # Micro pill backing behind sublabel
        draw.rounded_rectangle(
            [sub_x - 16, sub_y - 4, sub_x + sw + 16, sub_y + sh + 8],
            radius=12,
            fill=(255, 255, 255, 18),
            outline=(255, 255, 255, 35),
            width=1,
        )
        layer.alpha_composite(typography.draw_text_layer(
            sublabel_text, sublabel_font, "#E2E8F0", (W, H),
            (sub_x, sub_y),
        ))

    # Scale transform around center if animated
    if abs(scale_factor - 1.0) > 0.005:
        cx, cy = x0 + card_w // 2, y0 + card_h // 2
        bbox = (x0 - 24, y0 - 24, x0 + card_w + 24, y0 + card_h + 24)
        cropped = layer.crop(bbox)
        new_w = round(cropped.width * scale_factor)
        new_h = round(cropped.height * scale_factor)
        scaled = cropped.resize((new_w, new_h), Image.LANCZOS)
        res = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        res.alpha_composite(scaled, dest=(cx - new_w // 2, cy - new_h // 2))
        return res

    return layer


def _build_alert_pill(
    scene: SceneDefinition,
    lang: str,
    canvas_size: Tuple[int, int],
    content_box: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    """Glowing Badge Pill with icon accent and sharp typography."""
    W, H = canvas_size
    badge_text = typography.enforce_budget(scene.visual_hierarchy.badge_tag, "badge_tag", lang)
    font = typography.load_font(lang, "bold", 26)
    tw, th = typography.measure_text(badge_text, font)
    pad_x = 26
    pill_w, pill_h = tw + 2 * pad_x + 12, ALERT_PILL_HEIGHT

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    accent = _hex_to_rgb(scene.asset.accent_color)
    if content_box is None:
        x0, y0 = ALERT_PILL_INSET, ALERT_PILL_INSET + 8
    else:
        cl, ct, _cr, _cb = content_box
        x0, y0 = cl + 40, ct + 32

    # Outer soft glow
    for i in range(4, 0, -1):
        draw.rounded_rectangle(
            [x0 - i, y0 - i, x0 + pill_w + i, y0 + pill_h + i],
            radius=(pill_h + i * 2) // 2,
            outline=accent + (int(40 * (i / 4)),),
            width=2,
        )

    # Solid accent pill with dark ink
    draw.rounded_rectangle([x0, y0, x0 + pill_w, y0 + pill_h], radius=pill_h // 2, fill=accent + (245,))
    # Mini blinking dot inside badge pill
    dot_radius = 5
    dot_x, dot_y = x0 + 18, y0 + pill_h // 2
    draw.ellipse([dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius], fill=(11, 17, 32, 220))

    layer.alpha_composite(typography.draw_text_layer(
        badge_text, font, "#0B1120", (W, H), (x0 + pad_x + 10, y0 + (pill_h - th) // 2 - 4),
    ))
    return layer


def _build_header_branding(
    lang: str,
    canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT),
    content_box: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    """Official Government Header with Tricolor accent ribbon and verified badge."""
    W, H = canvas_size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if content_box is None:
        # 1. National Tricolor Ribbon across the top edge (y=0..6)
        seg_w = W // 3
        draw.rectangle([0, 0, seg_w, 6], fill=(255, 153, 51, 240))           # Saffron
        draw.rectangle([seg_w, 0, seg_w * 2, 6], fill=(255, 255, 255, 240))    # White
        draw.rectangle([seg_w * 2, 0, W, 6], fill=(19, 136, 8, 240))           # India Green

        # 2. Official Authority Micro-Badge (top-right) localized per language
        auth_labels = {
            "en": "GOVERNMENT OF INDIA",
            "hi": "भारत सरकार",
            "mr": "भारत सरकार",
            "ta": "இந்திய அரசு",
            "te": "భారత ప్రభుత్వం",
            "bn": "ভারত সরকার",
        }
        auth_label = auth_labels.get(lang, "GOVERNMENT OF INDIA")
        badge_font = typography.load_font(lang, "bold", 20)
        bw, bh = typography.measure_text(auth_label, badge_font)
        bx0, by0 = W - bw - 130, 22
        bw_total = bw + 42

        draw.rounded_rectangle([bx0, by0, bx0 + bw_total, by0 + 36], radius=18, fill=(15, 23, 42, 170), outline=(255, 255, 255, 40), width=1)
        draw.ellipse([bx0 + 10, by0 + 10, bx0 + 26, by0 + 26], fill=(59, 130, 246, 255))
        draw.line([bx0 + 14, by0 + 18, bx0 + 17, by0 + 22], fill=(255, 255, 255, 255), width=2)
        draw.line([bx0 + 17, by0 + 22, bx0 + 23, by0 + 14], fill=(255, 255, 255, 255), width=2)

        layer.alpha_composite(typography.draw_text_layer(
            auth_label, badge_font, "#E2E8F0", (W, H), (bx0 + 32, by0 + 6)
        ))
    else:
        cl, ct, cr, _cb = content_box
        box_w = cr - cl
        seg_w = box_w // 3
        draw.rectangle([cl, ct, cl + seg_w, ct + 4], fill=(255, 153, 51, 240))
        draw.rectangle([cl + seg_w, ct, cl + seg_w * 2, ct + 4], fill=(255, 255, 255, 240))
        draw.rectangle([cl + seg_w * 2, ct, cr, ct + 4], fill=(19, 136, 8, 240))

    return layer


def build_static_layers(
    scene: SceneDefinition,
    lang: str,
    canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT),
    content_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Image.Image]:
    """Base visual layers: headline/subtext, metric card, alert pill, branding."""
    W, H = canvas_size
    vh = scene.visual_hierarchy
    layers: Dict[str, Image.Image] = {}

    compact = content_box is not None
    headline_size = 58 if compact else 76
    subtext_size = 32 if compact else 38

    headline_text = typography.enforce_budget(vh.headline, "headline", lang)
    subtext_text = typography.enforce_budget(vh.subtext, "subtext", lang)
    headline_font = typography.load_font(lang, "bold", headline_size)
    subtext_font = typography.load_font(lang, "regular" if lang == "en" else "bold", subtext_size)

    if content_box is None:
        left_margin = 96
        max_text_width = W - 2 * left_margin
        y = ALERT_PILL_INSET + ALERT_PILL_HEIGHT + HEADLINE_GAP_BELOW_PILL + 8
    else:
        cl, ct, cr, _cb = content_box
        left_margin = cl + 40
        max_text_width = (cr - cl) - 80
        y = ct + 32 + ALERT_PILL_HEIGHT + HEADLINE_GAP_BELOW_PILL

    layer4 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    max_headline_lines = 3 if content_box is not None else 2
    for line in typography.wrap_text(headline_text, headline_font, max_text_width, max_lines=max_headline_lines):
        layer4.alpha_composite(typography.draw_text_with_shadow(
            line, headline_font, "#F8FAFC", (W, H), (left_margin, y),
            shadow_offset=(0, 4), shadow_alpha=170,
        ))
        y += headline_font.size + 12
    y += 12
    for line in typography.wrap_text(subtext_text, subtext_font, max_text_width, max_lines=2):
        layer4.alpha_composite(typography.draw_text_with_shadow(
            line, subtext_font, "#CBD5E1", (W, H), (left_margin, y),
            shadow_offset=(0, 2), shadow_alpha=140,
        ))
        y += subtext_font.size + 8
    layers["headline_subtext"] = layer4

    if scene.template_type.value == "METRIC_FOCUS" and vh.highlight_metric:
        layers["metric_card"] = _build_metric_card(scene, lang, canvas_size, content_box)

    layers["alert_pill"] = _build_alert_pill(scene, lang, canvas_size, content_box)
    layers["branding"] = _build_header_branding(lang, canvas_size, content_box)

    return layers


@dataclass(frozen=True)
class _Sprite:
    image: Image.Image
    box: Tuple[int, int]

    @classmethod
    def from_layer(cls, layer: Image.Image) -> Optional["_Sprite"]:
        bbox = layer.getbbox()
        if bbox is None:
            return None
        return cls(image=layer.crop(bbox), box=(bbox[0], bbox[1]))

    def paste_onto(self, frame: Image.Image, offset_y: int = 0) -> None:
        x, y = self.box
        frame.paste(self.image, (x, y + offset_y), self.image)


def _get_core_fact_timing(subtitles: Optional[List[WordTimestamp]]) -> Optional[Tuple[float, float]]:
    """Returns (start_sec, end_sec) for when core facts are spoken in the scene."""
    if not subtitles:
        return None
    fact_subs = [s for s in subtitles if s.is_core_fact]
    if not fact_subs:
        return None
    return (min(s.start_sec for s in fact_subs), max(s.end_sec for s in fact_subs))


def make_frame_function(
    scene: SceneDefinition,
    static_layers: Dict[str, Image.Image],
    caption_cache,
    bg_source: Image.Image,
    pan_targets: Tuple[float, float, float, float],
    canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT),
    resample: int = KENBURNS_RESAMPLE,
    presenter_source=None,
    presenter_layout=None,
    presenter_track=None,
    lang: str = "en",
) -> Callable[[float], np.ndarray]:
    """Kinetic, audio-synchronized frame compositor with animated entrances and progress bar."""
    import time
    W, H = canvas_size
    cx0, cy0, cx1, cy1 = pan_targets
    duration = scene.scene_duration_sec or 8.0
    total_frames = max(1, round(duration * VIDEO_FPS))
    presenter_panel_box = presenter_layout.panel_box if presenter_layout is not None else None
    presenter_box = presenter_panel_box[:2] if presenter_panel_box is not None else None
    content_box = presenter_layout.content_box if presenter_layout is not None else None

    # Base Sprites
    headline_sprite = _Sprite.from_layer(static_layers["headline_subtext"])
    branding_sprite = _Sprite.from_layer(static_layers["branding"])
    base_pill_sprite = _Sprite.from_layer(static_layers["alert_pill"])
    base_metric_sprite = _Sprite.from_layer(static_layers.get("metric_card")) if "metric_card" in static_layers else None

    # Pre-cache active metric card sprite to eliminate expensive re-rendering during playback
    active_metric_sprite = None
    if "metric_card" in static_layers:
        active_card_layer = _build_metric_card(
            scene, lang, canvas_size, content_box, glow_intensity=0.85, scale_factor=1.03
        )
        active_metric_sprite = _Sprite.from_layer(active_card_layer)

    caption_sprites = {id(img): _Sprite.from_layer(img) for _, img in caption_cache}

    # Core fact audio timing window for active synchronization
    core_fact_timing = _get_core_fact_timing(scene.subtitles)

    accent_rgb = _hex_to_rgb(scene.asset.accent_color)

    frame_counter = 0
    t_last_log = time.time()

    def frame_function(t: float) -> np.ndarray:
        nonlocal frame_counter, t_last_log
        frame_counter += 1

        # Real-time frame rendering progress log
        now = time.time()
        if frame_counter == 1 or frame_counter % 15 == 0 or frame_counter >= total_frames:
            elapsed = now - t_last_log
            inst_fps = 15.0 / elapsed if elapsed > 0 and frame_counter > 1 else 0.0
            pct = (frame_counter / total_frames) * 100
            print(
                f"  [FRAME] Scene {scene.scene_id} ({lang.upper()}) | Frame {frame_counter:03d}/{total_frames:03d} ({pct:5.1f}%) | t={t:5.2f}s | Speed: {inst_fps:4.1f} fps",
                flush=True,
            )
            t_last_log = now

        # 1. Ken Burns background with smooth pan and zoom
        frame = kenburns.render_frame(
            bg_source, t, duration, W, H, cx0, cy0, cx1, cy1, resample=resample
        )
        if frame.mode != "RGB":
            frame = frame.convert("RGB")

        # 2. Split-screen Presenter if enabled
        if presenter_source is not None and presenter_box is not None:
            presenter_source.paste_onto(frame, presenter_box, t, presenter_track)

        # 3. Top Scene Progress Bar (Animated timeline)
        draw = ImageDraw.Draw(frame)
        progress_val = min(max(t / duration, 0.0), 1.0)
        bar_w = int(W * progress_val)
        if bar_w > 0:
            draw.rectangle([0, 6, bar_w, 10], fill=accent_rgb + (230,))
            draw.ellipse([bar_w - 4, 4, bar_w + 4, 12], fill=(255, 255, 255))

        # 4. Top Government Branding
        if branding_sprite is not None:
            branding_sprite.paste_onto(frame)

        # 5. Kinetic Alert Pill Entrance & Breathing Pulse
        pill_p = min(max(t / 0.45, 0.0), 1.0)
        pill_e = kenburns.ease_out_back(pill_p)
        pill_offset_y = int((1.0 - pill_e) * -40)
        if base_pill_sprite is not None and pill_p > 0.05:
            pulse_factor = 0.90 + 0.10 * math.sin(2 * math.pi * PULSE_HZ * t)
            pill_img = _with_alpha(base_pill_sprite.image, pill_p * pulse_factor)
            frame.paste(pill_img, (base_pill_sprite.box[0], base_pill_sprite.box[1] + pill_offset_y), pill_img)

        # 6. Kinetic Headline & Subtext Staggered Entrance
        text_p = min(max((t - 0.1) / 0.5, 0.0), 1.0)
        if headline_sprite is not None and text_p > 0.05:
            text_e = kenburns.ease_out_cubic(text_p)
            text_offset_y = int((1.0 - text_e) * 30)
            text_img = _with_alpha(headline_sprite.image, text_p)
            frame.paste(text_img, (headline_sprite.box[0], headline_sprite.box[1] + text_offset_y), text_img)

        # 7. AUDIO-SYNCHRONIZED METRIC CARD POP & GLOW (Cached Fast Path)
        if "metric_card" in static_layers:
            card_p = min(max((t - 0.3) / 0.55, 0.0), 1.0)
            if card_p > 0.05:
                card_e = kenburns.ease_out_back(card_p)
                card_offset_y = int((1.0 - card_e) * 45)

                is_fact_spoken = False
                if core_fact_timing is not None:
                    cf_start, cf_end = core_fact_timing
                    if cf_start - 0.15 <= t <= cf_end + 0.25:
                        is_fact_spoken = True

                if is_fact_spoken and active_metric_sprite is not None:
                    active_metric_sprite.paste_onto(frame, offset_y=card_offset_y)
                elif base_metric_sprite is not None:
                    card_img = _with_alpha(base_metric_sprite.image, card_p)
                    frame.paste(card_img, (base_metric_sprite.box[0], base_metric_sprite.box[1] + card_offset_y), card_img)

        # 8. Modern Karaoke Subtitles (bottom layer)
        caption = karaoke.get_caption_frame_for_time(caption_cache, t)
        sprite = caption_sprites.get(id(caption))
        if sprite is not None:
            sprite.paste_onto(frame)

        # 9. Broadcast-style card borders — presenter panel and content area
        # each read as a distinct framed card, the way a TV news split-screen
        # does, rather than floating text over a bare background.
        if presenter_panel_box is not None:
            _draw_card_border(frame, presenter_panel_box)
        if content_box is not None:
            _draw_card_border(frame, content_box)

        return np.asarray(frame)

    return frame_function


def resolve_audio_path(audio_path: Optional[str]) -> Optional[Path]:
    """Locate a scene's audio file on disk, or None if it isn't there."""
    if not audio_path:
        return None
    direct = Path(audio_path)
    if direct.exists():
        return direct
    relative = Path(audio_path.lstrip("/\\"))
    if relative.exists():
        return relative
    return None


def resolve_presenter(
    lang: str,
    canvas_size: Tuple[int, int],
    scene: Optional[SceneDefinition] = None,
    use_wav2lip: bool = True,
):
    """(PresenterSource, PresenterLayout) for `lang`, with dynamic Wav2Lip-HD lip-sync and fallback."""
    from services import avatar_registry

    H = canvas_size[1]
    caption_reserve = int(H * karaoke.BOTTOM_SAFE_PCT)
    layout = presenter.compute_layout(canvas_size, caption_reserve)

    # 1. Dynamic Wav2Lip-HD Lip-Sync Synthesis
    if use_wav2lip and scene is not None and scene.audio_path:
        audio_file = resolve_audio_path(scene.audio_path)
        anchor_img = Path("assets/avatars/anchor_source.png")
        if audio_file is not None and anchor_img.is_file():
            try:
                from services.wav2lip_service import generate_lip_sync

                cache_dir = Path("static/avatars")
                cache_dir.mkdir(parents=True, exist_ok=True)
                lip_sync_mp4 = cache_dir / f"{audio_file.stem}_wav2lip.mp4"

                if not lip_sync_mp4.exists() or lip_sync_mp4.stat().st_size < 1000:
                    generate_lip_sync(
                        face_image_path=anchor_img,
                        audio_path=audio_file,
                        output_path=lip_sync_mp4,
                        batch_size=32,
                        enhance_face=True,
                    )

                source = presenter.PresenterSource.load(
                    str(lip_sync_mp4), layout, "AI-GENERATED PRESENTER", lang
                )
                logger.info("Wav2Lip-HD presenter active for scene %s lang=%s", scene.scene_id, lang)
                return source, layout
            except Exception as e:
                logger.warning(
                    "Wav2Lip-HD synthesis failed (%s); falling back to static/registered avatar loop",
                    e,
                    exc_info=True,
                )

    # 2. Pre-baked / Registered Avatar Loop Fallback
    avatar = avatar_registry.resolve(lang)
    if avatar is None:
        return None, None

    try:
        source = presenter.PresenterSource.load(
            str(avatar.file_path), layout, avatar.disclosure_label, lang
        )
    except Exception:
        logger.warning(
            "failed to load avatar %r; rendering without a presenter", avatar.avatar_id, exc_info=True
        )
        return None, None

    logger.info("presenter %r active for lang=%s", avatar.avatar_id, lang)
    return source, layout


def render_scene_clip(scene: SceneDefinition, lang: str, scene_index: int, canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT), presenter_source=None, presenter_layout=None):
    from moviepy import AudioFileClip, VideoClip

    if scene.scene_duration_sec is None or scene.subtitles is None:
        raise ValueError(f"scene {scene.scene_id} is missing synthesized duration/subtitles (mixed state, see README §7.4 invariant 1)")

    if presenter_source is None and presenter_layout is not None:
        p_source, _ = resolve_presenter(lang, canvas_size, scene=scene)
    else:
        p_source = presenter_source

    content_box = presenter_layout.content_box if presenter_layout is not None else None

    # Choreograph the presenter against this scene's word timings. Built per
    # scene against the same decoded frames, so it costs no extra decoding.
    # Keyed off p_source, not the presenter_source parameter: render_job now
    # passes None deliberately so each scene resolves its own lip-synced clip.
    presenter_track = None
    if p_source is not None and getattr(p_source, "clip_path", None) is not None:
        presenter_track = gestures.build_track(
            scene.subtitles, scene.template_type,
            scene.scene_duration_sec, p_source.clip_path,
        )

    bg_source = build_background_source(scene.asset, *canvas_size)
    bg_video = build_background_video(scene.asset, *canvas_size)
    static_layers = build_static_layers(scene, lang, canvas_size, content_box)
    caption_layout = karaoke.build_caption_layout(scene.subtitles, lang, canvas_size)
    caption_cache = karaoke.build_caption_frame_cache(caption_layout)
    pan_targets = kenburns.pan_targets_for_template(
        scene.template_type.value, *bg_source.size, alternate=(scene_index % 2 == 1)
    )

    frame_fn = make_frame_function(
        scene, static_layers, caption_cache, bg_source, pan_targets, canvas_size,
        presenter_source=p_source, presenter_layout=presenter_layout,
        presenter_track=presenter_track, lang=lang,
    )
    clip = VideoClip(frame_function=frame_fn, duration=scene.scene_duration_sec).with_fps(VIDEO_FPS)
    if bg_video is not None:
        clip._broll_background = bg_video

    audio_file = resolve_audio_path(scene.audio_path)
    if audio_file is not None:
        clip = clip.with_audio(AudioFileClip(str(audio_file)))
    elif scene.audio_path:
        logger.warning(
            "scene %s audio_path %r could not be resolved on disk; rendering silent",
            scene.scene_id, scene.audio_path,
        )
    return clip


_nvenc_unavailable = False


def _write_with_fallback(clip, out_path: str, codec_pref: str) -> None:
    global _nvenc_unavailable

    if codec_pref == "h264_nvenc" and not _nvenc_unavailable:
        try:
            clip.write_videofile(
                out_path, fps=VIDEO_FPS, codec="h264_nvenc", preset="p4",
                threads=4,
                ffmpeg_params=["-rc", "vbr", "-cq", "23", "-b:v", "8M", "-maxrate", "12M"],
                audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
                logger="bar",
            )
            return
        except Exception:
            _nvenc_unavailable = True
            logger.warning(
                "NVENC encode failed; using accelerated libx264 for this and subsequent renders", exc_info=True
            )

    clip.write_videofile(
        out_path, fps=VIDEO_FPS, codec="libx264", preset="ultrafast",
        threads=4,
        ffmpeg_params=["-threads", "4"],
        audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
        logger="bar",
    )


def render_job(scenes, lang: str, out_path: str, codec_pref: str = "h264_nvenc", canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)) -> str:
    import time
    _ffmpeg.ensure_ffmpeg_binary_env()
    from moviepy import concatenate_videoclips

    t0 = time.time()
    total_dur = sum(s.scene_duration_sec or 0.0 for s in scenes)
    print(f"\n=======================================================", flush=True)
    print(f"[RENDER JOB START] Language: {lang.upper()} | Scenes: {len(scenes)} | Total Duration: {total_dur:.1f}s", flush=True)
    print(f"[RENDER JOB TARGET] Output Path: {out_path}", flush=True)
    print(f"=======================================================", flush=True)

    _, presenter_layout = resolve_presenter(lang, canvas_size)

    clips = [
        render_scene_clip(s, lang, i, canvas_size, presenter_source=None, presenter_layout=presenter_layout)
        for i, s in enumerate(scenes)
    ]
    final = concatenate_videoclips(clips, method="chain")
    try:
        _write_with_fallback(final, out_path, codec_pref)
        elapsed = time.time() - t0
        print(f"[RENDER JOB COMPLETE] {lang.upper()} finished in {elapsed:.2f}s (Avg Speed: {(total_dur*VIDEO_FPS)/elapsed:.1f} fps)\n", flush=True)
    finally:
        for clip in (final, *clips):
            background = getattr(clip, "_broll_background", None)
            if background is not None:
                background.close()
            try:
                clip.close()
            except Exception:
                logger.debug("failed to close clip", exc_info=True)
    return out_path
