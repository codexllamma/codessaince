"""Top-level compositor orchestration (README §8.6): 5-layer canvas, per-scene
rendering, job concatenation, and NVENC/libx264 fallback encoding.

Only VisualAssetSelection.asset_type == "mesh_gradient" is implemented in
this slice (README §10.2 fallback) — real B-roll video loops are out of
scope until the asset tag-matcher (§10) exists.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from compositor import _ffmpeg, karaoke, kenburns, presenter, typography
from models.schemas import SceneDefinition, VisualAssetSelection

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

ALERT_PILL_INSET = 96
ALERT_PILL_HEIGHT = 56
HEADLINE_GAP_BELOW_PILL = 28
METRIC_CARD_SIZE = (720, 320)
PULSE_HZ = 0.8

# LANCZOS costs ~43ms per 1080p frame against ~28ms for BILINEAR, and on the
# smooth gradients and video loops used as backgrounds the two differ by at
# most 3/255 per channel. Raise this to LANCZOS for stills with fine detail
# where the extra 15ms per frame is worth paying.
KENBURNS_RESAMPLE = Image.BILINEAR


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _with_alpha(layer: Image.Image, factor: float) -> Image.Image:
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * factor))
    return Image.merge("RGBA", (r, g, b, a))


def build_background_source(
    asset: VisualAssetSelection,
    canvas_w: int = VIDEO_WIDTH,
    canvas_h: int = VIDEO_HEIGHT,
    z_max: float = kenburns.Z_MAX_DEFAULT,
) -> Image.Image:
    """The still image Ken Burns pans across for this scene.

    Handles static_graphic (a real B-roll still) and mesh_gradient (the §10.2
    procedural fallback). Anything present on disk is used; anything missing
    degrades to the gradient, which §10.2 specifies "always looks intentional
    and never looks broken" — a scene should never fail for want of an asset.

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
    dark = tuple(int(c * 0.15) for c in accent)

    yy, xx = np.mgrid[0:h, 0:w]
    diag = (xx / w + yy / h) / 2.0
    gradient = np.empty((h, w, 3), dtype=np.float32)
    for c in range(3):
        gradient[:, :, c] = dark[c] + (accent[c] - dark[c]) * diag

    cx, cy = w * 0.3, h * 0.25
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (0.7 * max(w, h))
    highlight = np.clip(1.0 - dist, 0, 1) ** 2 * 40
    gradient += highlight[:, :, None]

    rng = np.random.default_rng(abs(hash(asset.asset_id)) % (2**32))
    gradient += rng.normal(0, 4, size=(h, w, 1))

    gradient = np.clip(gradient, 0, 255).astype(np.uint8)
    # Mode is inferred from the (h, w, 3) uint8 shape; passing it explicitly is
    # deprecated and removed in Pillow 13.
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
) -> Image.Image:
    W, H = canvas_size
    card_w, card_h = METRIC_CARD_SIZE
    if content_box is None:
        x0, y0 = (W - card_w) // 2, (H - card_h) // 2
    else:
        cl, ct, cr, cb = content_box
        # Shrink to fit the panel, then sit in its lower portion so the
        # headline above keeps its room.
        card_w = min(card_w, (cr - cl) - 80)
        card_h = min(card_h, (cb - ct) // 2)
        x0 = cl + ((cr - cl) - card_w) // 2
        y0 = cb - card_h - 48
    accent = _hex_to_rgb(scene.asset.accent_color)
    radius = 24

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=radius, fill=(15, 23, 42, 200))
    for i in range(6, 0, -1):
        alpha = int(30 * (i / 6))
        draw.rounded_rectangle(
            [x0 - i, y0 - i, x0 + card_w + i, y0 + card_h + i],
            radius=radius + i, outline=accent + (alpha,), width=2,
        )
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=radius, outline=accent + (255,), width=3)

    vh = scene.visual_hierarchy
    metric_text = typography.enforce_budget(vh.highlight_metric or "", "highlight_metric", lang)
    sublabel_text = typography.enforce_budget(vh.highlight_sublabel or "", "highlight_sublabel", lang)

    metric_size = 96 if content_box is None else 72
    metric_font = typography.load_font(lang, "bold", metric_size)
    sublabel_font = typography.load_font(lang, "regular" if lang == "en" else "bold", 32)

    mw, mh = typography.measure_text(metric_text, metric_font)
    layer.alpha_composite(typography.draw_text_layer(
        metric_text, metric_font, "#F8FAFC", (W, H),
        (x0 + (card_w - mw) // 2, y0 + card_h // 2 - mh - 6),
    ))
    if sublabel_text:
        sw, _sh = typography.measure_text(sublabel_text, sublabel_font)
        layer.alpha_composite(typography.draw_text_layer(
            sublabel_text, sublabel_font, "#94A3B8", (W, H),
            (x0 + (card_w - sw) // 2, y0 + card_h // 2 + 14),
        ))
    return layer


def _build_alert_pill(
    scene: SceneDefinition,
    lang: str,
    canvas_size: Tuple[int, int],
    content_box: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    W, H = canvas_size
    badge_text = typography.enforce_budget(scene.visual_hierarchy.badge_tag, "badge_tag", lang)
    font = typography.load_font(lang, "bold", 26)
    tw, th = typography.measure_text(badge_text, font)
    pad_x = 24
    pill_w, pill_h = tw + 2 * pad_x, ALERT_PILL_HEIGHT

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    accent = _hex_to_rgb(scene.asset.accent_color)
    if content_box is None:
        x0, y0 = ALERT_PILL_INSET, ALERT_PILL_INSET
    else:
        # The pill belongs to the fact card, so it moves inside the panel —
        # at the canvas edge it would sit on top of the presenter, and above
        # the panel it would run off the top of the frame.
        cl, ct, _cr, _cb = content_box
        x0, y0 = cl + 40, ct + 24
    draw.rounded_rectangle([x0, y0, x0 + pill_w, y0 + pill_h], radius=pill_h // 2, fill=accent + (235,))
    layer.alpha_composite(typography.draw_text_layer(
        badge_text, font, "#0B1120", (W, H), (x0 + pad_x, y0 + (pill_h - th) // 2 - 4),
    ))
    return layer


def alert_pill_alpha(t: float, pulse_hz: float = 0.8) -> float:
    """0.7-1.0 pulse (README §8.6)."""
    return 0.85 + 0.15 * math.sin(2 * math.pi * pulse_hz * t)


def build_static_layers(
    scene: SceneDefinition,
    lang: str,
    canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT),
    content_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Image.Image]:
    """Layers built once per scene (not per frame): headline/subtext (layer 4),
    metric card if METRIC_FOCUS (layer 3), alert pill base (layer 5).

    `content_box` confines them to a sub-region — the right-hand panel when a
    presenter occupies the left. Text is wrapped against the real available
    width, so the narrower panel produces more lines or an ellipsis rather
    than overrunning into the presenter.
    """
    W, H = canvas_size
    vh = scene.visual_hierarchy
    layers: Dict[str, Image.Image] = {}

    # Type sizes step down in a presenter panel: a 76pt headline in a
    # ~1100px column wraps to three lines and crowds the metric card.
    compact = content_box is not None
    headline_size = 56 if compact else 76
    subtext_size = 32 if compact else 38

    headline_text = typography.enforce_budget(vh.headline, "headline", lang)
    subtext_text = typography.enforce_budget(vh.subtext, "subtext", lang)
    headline_font = typography.load_font(lang, "bold", headline_size)
    subtext_font = typography.load_font(lang, "regular" if lang == "en" else "bold", subtext_size)

    if content_box is None:
        left_margin = 96
        max_text_width = W - 2 * left_margin
        # Start below the alert pill rather than at a fixed fraction of the
        # height. A proportional 12% put the headline's top at y=130 while the
        # pill runs to y=152; Latin caps do not reach the top of the em box so
        # the 22px overlap was invisible, but the Devanagari shirorekha does.
        y = ALERT_PILL_INSET + ALERT_PILL_HEIGHT + HEADLINE_GAP_BELOW_PILL
    else:
        cl, ct, cr, _cb = content_box
        left_margin = cl + 40
        max_text_width = (cr - cl) - 80
        # Below the pill, which now sits inside the panel at ct + 24.
        y = ct + 24 + ALERT_PILL_HEIGHT + HEADLINE_GAP_BELOW_PILL

    layer4 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    max_headline_lines = 3 if content_box is not None else 2
    for line in typography.wrap_text(headline_text, headline_font, max_text_width, max_lines=max_headline_lines):
        layer4.alpha_composite(typography.draw_text_layer(line, headline_font, "#F8FAFC", (W, H), (left_margin, y)))
        y += headline_font.size + 10
    y += 12
    for line in typography.wrap_text(subtext_text, subtext_font, max_text_width, max_lines=2):
        layer4.alpha_composite(typography.draw_text_layer(line, subtext_font, "#CBD5E1", (W, H), (left_margin, y)))
        y += subtext_font.size + 8
    layers["headline_subtext"] = layer4

    if scene.template_type.value == "METRIC_FOCUS" and vh.highlight_metric:
        layers["metric_card"] = _build_metric_card(scene, lang, canvas_size, content_box)

    layers["alert_pill"] = _build_alert_pill(scene, lang, canvas_size, content_box)

    return layers


@dataclass(frozen=True)
class _Sprite:
    """A layer cropped to its non-transparent bounds, plus where to paste it.

    Compositing a full 1920x1080 RGBA layer costs ~6ms even when only a
    fraction of it is inked. Most layers occupy a band — the headline sits in
    the upper third, captions in the bottom 22% — so pasting just the inked
    region is several times cheaper for an identical result.
    """

    image: Image.Image
    box: Tuple[int, int]

    @classmethod
    def from_layer(cls, layer: Image.Image) -> Optional["_Sprite"]:
        bbox = layer.getbbox()
        if bbox is None:
            return None
        return cls(image=layer.crop(bbox), box=(bbox[0], bbox[1]))

    def paste_onto(self, frame: Image.Image) -> None:
        frame.paste(self.image, self.box, self.image)


# Discrete steps for the alert pill pulse. Re-deriving the alpha per frame cost
# ~7ms in channel splitting; at 0.8Hz one cycle spans ~37 frames at 30fps, so
# 24 precomputed steps is past the point of visible banding.
_PILL_ALPHA_STEPS = 24


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
    bg_video: Optional["VideoBackground"] = None,
) -> Callable[[float], np.ndarray]:
    W, H = canvas_size
    cx0, cy0, cx1, cy1 = pan_targets
    duration = scene.scene_duration_sec
    presenter_box = presenter_layout.panel_box[:2] if presenter_layout is not None else None

    # Merge everything that never changes into one sprite: two composites
    # become one, and the merge happens once instead of 30 times a second.
    static_merged = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if "metric_card" in static_layers:
        static_merged.alpha_composite(static_layers["metric_card"])
    static_merged.alpha_composite(static_layers["headline_subtext"])
    static_sprite = _Sprite.from_layer(static_merged)

    pill_sprites = [
        _Sprite.from_layer(_with_alpha(static_layers["alert_pill"], 0.85 + 0.15 * math.sin(2 * math.pi * i / _PILL_ALPHA_STEPS)))
        for i in range(_PILL_ALPHA_STEPS)
    ]
    caption_sprites = {id(img): _Sprite.from_layer(img) for _, img in caption_cache}

    def frame_function(t: float) -> np.ndarray:
        if bg_video is not None:
            # The clip already carries the motion; it arrives at output size
            # and needs no Ken Burns pass on top. See VideoBackground.
            frame = bg_video.frame_at(t)
        else:
            frame = kenburns.render_frame(
                bg_source, t, duration, W, H, cx0, cy0, cx1, cy1, resample=resample
            )
        if frame.mode != "RGB":
            frame = frame.convert("RGB")

        # Presenter goes down before the text layers so the fact card and
        # captions always read on top of it.
        if presenter_source is not None and presenter_box is not None:
            presenter_source.paste_onto(frame, presenter_box, t)

        caption = karaoke.get_caption_frame_for_time(caption_cache, t)
        sprite = caption_sprites.get(id(caption))
        if sprite is not None:
            sprite.paste_onto(frame)
        if static_sprite is not None:
            static_sprite.paste_onto(frame)

        pill = pill_sprites[int(t * PULSE_HZ * _PILL_ALPHA_STEPS) % _PILL_ALPHA_STEPS]
        if pill is not None:
            pill.paste_onto(frame)
        # Already RGB — pasting with a mask blends in place, so no final
        # convert() copy of two million pixels is needed.
        return np.asarray(frame)

    return frame_function


def resolve_audio_path(audio_path: Optional[str]) -> Optional[Path]:
    """Locate a scene's audio file on disk, or None if it isn't there.

    The synthesis stage records audio_path as a web-style URL served by the
    API ("/static/audio/scene_1_en.mp3"), while fixtures use ordinary
    filesystem paths. Accept both rather than making callers normalise.
    """
    if not audio_path:
        return None
    direct = Path(audio_path)
    if direct.exists():
        return direct
    relative = Path(audio_path.lstrip("/\\"))
    if relative.exists():
        return relative
    return None


def resolve_presenter(lang: str, canvas_size: Tuple[int, int]):
    """(PresenterSource, PresenterLayout) for `lang`, or (None, None).

    Returning None is the normal case until an avatar is installed, and the
    caller then renders the full-width layout. A presenter that fails to load
    is logged and skipped rather than failing the render — a broken avatar
    should cost you the presenter, not the video.
    """
    from services import avatar_registry

    avatar = avatar_registry.resolve(lang)
    if avatar is None:
        return None, None

    H = canvas_size[1]
    caption_reserve = int(H * karaoke.BOTTOM_SAFE_PCT)
    layout = presenter.compute_layout(canvas_size, caption_reserve)
    try:
        source = presenter.PresenterSource.load(
            str(avatar.file_path), layout, avatar.disclosure_label, lang
        )
    except Exception:
        logger.warning("failed to load avatar %r; rendering without a presenter", avatar.avatar_id, exc_info=True)
        return None, None

    logger.info("presenter %r active for lang=%s", avatar.avatar_id, lang)
    return source, layout


def render_scene_clip(scene: SceneDefinition, lang: str, scene_index: int, canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT), presenter_source=None, presenter_layout=None):
    from moviepy import AudioFileClip, VideoClip

    if scene.scene_duration_sec is None or scene.subtitles is None:
        raise ValueError(f"scene {scene.scene_id} is missing synthesized duration/subtitles (mixed state, see README §7.4 invariant 1)")

    content_box = presenter_layout.content_box if presenter_layout is not None else None

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
        presenter_source=presenter_source, presenter_layout=presenter_layout,
        bg_video=bg_video,
    )
    clip = VideoClip(frame_function=frame_fn, duration=scene.scene_duration_sec).with_fps(VIDEO_FPS)
    if bg_video is not None:
        # Tie the reader's lifetime to the clip so render_job's close() loop
        # releases it; a leaked reader keeps an ffmpeg subprocess alive.
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
    """Encode with NVENC when it works, else libx264 (README §15).

    An `ffmpeg -encoders` probe is not sufficient to detect a working NVENC:
    the encoder can be compiled in and still fail at runtime if the installed
    driver is older than the build's SDK. So we attempt it and remember the
    failure — otherwise a 6-language job pays six doomed encode attempts.
    """
    global _nvenc_unavailable

    if codec_pref == "h264_nvenc" and not _nvenc_unavailable:
        try:
            clip.write_videofile(
                out_path, fps=VIDEO_FPS, codec="h264_nvenc", preset="p5",
                ffmpeg_params=["-rc", "vbr", "-cq", "23", "-b:v", "8M", "-maxrate", "12M"],
                audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
            )
            return
        except Exception:
            _nvenc_unavailable = True
            logger.warning(
                "NVENC encode failed; using libx264 for this and subsequent renders", exc_info=True
            )

    clip.write_videofile(
        out_path, fps=VIDEO_FPS, codec="libx264", preset="veryfast",
        audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
    )


def render_job(scenes, lang: str, out_path: str, codec_pref: str = "h264_nvenc", canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)) -> str:
    _ffmpeg.ensure_ffmpeg_binary_env()
    from moviepy import concatenate_videoclips

    # Resolved once per job: the presenter loop is the same for every scene in
    # a language, and decoding it per scene would repeat the whole cost.
    presenter_source, presenter_layout = resolve_presenter(lang, canvas_size)

    clips = [
        render_scene_clip(s, lang, i, canvas_size, presenter_source, presenter_layout)
        for i, s in enumerate(scenes)
    ]
    final = concatenate_videoclips(clips, method="chain")
    try:
        _write_with_fallback(final, out_path, codec_pref)
    finally:
        # Windows keeps the reader subprocess and the audio file handle open
        # until the clip is closed; a leaked handle blocks the next render of
        # the same job from overwriting its own output.
        for clip in (final, *clips):
            background = getattr(clip, "_broll_background", None)
            if background is not None:
                background.close()
            try:
                clip.close()
            except Exception:
                logger.debug("failed to close clip", exc_info=True)
    return out_path
