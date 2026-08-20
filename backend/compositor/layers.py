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

from compositor import _ffmpeg, karaoke, kenburns, presenter, typography
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


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _with_alpha(layer: Image.Image, factor: float) -> Image.Image:
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * min(max(factor, 0.0), 1.0)))
    return Image.merge("RGBA", (r, g, b, a))


def build_background_source(
    asset: VisualAssetSelection,
    canvas_w: int = VIDEO_WIDTH,
    canvas_h: int = VIDEO_HEIGHT,
    z_max: float = kenburns.Z_MAX_DEFAULT,
) -> Image.Image:
    """Procedural multi-point glowing atmospheric gradient background."""
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

    if asset.dim_overlay_opacity > 0:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, round(255 * asset.dim_overlay_opacity)))
        img = Image.alpha_composite(img, overlay)

    return img


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
    lang: str = "en",
) -> Callable[[float], np.ndarray]:
    """Kinetic, audio-synchronized frame compositor with animated entrances and progress bar."""
    W, H = canvas_size
    cx0, cy0, cx1, cy1 = pan_targets
    duration = scene.scene_duration_sec or 8.0
    presenter_box = presenter_layout.panel_box[:2] if presenter_layout is not None else None
    content_box = presenter_layout.content_box if presenter_layout is not None else None

    # Base Sprites
    headline_sprite = _Sprite.from_layer(static_layers["headline_subtext"])
    branding_sprite = _Sprite.from_layer(static_layers["branding"])
    base_pill_sprite = _Sprite.from_layer(static_layers["alert_pill"])
    base_metric_sprite = _Sprite.from_layer(static_layers.get("metric_card")) if "metric_card" in static_layers else None

    caption_sprites = {id(img): _Sprite.from_layer(img) for _, img in caption_cache}

    # Core fact audio timing window for active synchronization
    core_fact_timing = _get_core_fact_timing(scene.subtitles)

    accent_rgb = _hex_to_rgb(scene.asset.accent_color)

    def frame_function(t: float) -> np.ndarray:
        # 1. Ken Burns background with smooth pan and zoom
        frame = kenburns.render_frame(
            bg_source, t, duration, W, H, cx0, cy0, cx1, cy1, resample=resample
        )
        if frame.mode != "RGB":
            frame = frame.convert("RGB")

        # 2. Split-screen Presenter if enabled
        if presenter_source is not None and presenter_box is not None:
            presenter_source.paste_onto(frame, presenter_box, t)

        # 3. Top Scene Progress Bar (Animated timeline)
        draw = ImageDraw.Draw(frame)
        progress_val = min(max(t / duration, 0.0), 1.0)
        bar_w = int(W * progress_val)
        if bar_w > 0:
            draw.rectangle([0, 6, bar_w, 10], fill=accent_rgb + (230,))
            # Glowing playhead tip
            draw.ellipse([bar_w - 4, 4, bar_w + 4, 12], fill=(255, 255, 255))

        # 4. Top Government Branding
        if branding_sprite is not None:
            branding_sprite.paste_onto(frame)

        # 5. Kinetic Alert Pill Entrance & Breathing Pulse
        pill_p = min(max(t / 0.45, 0.0), 1.0)
        pill_e = kenburns.ease_out_back(pill_p)
        pill_offset_y = int((1.0 - pill_e) * -40)
        if base_pill_sprite is not None and pill_p > 0.05:
            # Subtle breathing pulse after entrance
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

        # 7. AUDIO-SYNCHRONIZED METRIC CARD POP & GLOW
        if "metric_card" in static_layers:
            card_p = min(max((t - 0.3) / 0.55, 0.0), 1.0)
            if card_p > 0.05:
                card_e = kenburns.ease_out_back(card_p)
                card_offset_y = int((1.0 - card_e) * 45)

                # Check if core fact is currently being spoken
                is_fact_spoken = False
                glow_int = 0.0
                card_scale = 1.0

                if core_fact_timing is not None:
                    cf_start, cf_end = core_fact_timing
                    if cf_start - 0.15 <= t <= cf_end + 0.25:
                        is_fact_spoken = True
                        rel_t = t - cf_start
                        pulse_osc = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * rel_t)
                        glow_int = float(pulse_osc)
                        card_scale = 1.04

                # Dynamic Metric Card rendering during active fact delivery
                if is_fact_spoken:
                    active_card_layer = _build_metric_card(
                        scene, lang, canvas_size, content_box,
                        glow_intensity=glow_int, scale_factor=card_scale,
                    )
                    card_sprite = _Sprite.from_layer(active_card_layer)
                    if card_sprite is not None:
                        card_sprite.paste_onto(frame, offset_y=card_offset_y)
                elif base_metric_sprite is not None:
                    card_img = _with_alpha(base_metric_sprite.image, card_p)
                    frame.paste(card_img, (base_metric_sprite.box[0], base_metric_sprite.box[1] + card_offset_y), card_img)

        # 8. Modern Karaoke Subtitles (bottom layer)
        caption = karaoke.get_caption_frame_for_time(caption_cache, t)
        sprite = caption_sprites.get(id(caption))
        if sprite is not None:
            sprite.paste_onto(frame)

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


def resolve_presenter(lang: str, canvas_size: Tuple[int, int]):
    """(PresenterSource, PresenterLayout) for `lang`, or (None, None)."""
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
    static_layers = build_static_layers(scene, lang, canvas_size, content_box)
    caption_layout = karaoke.build_caption_layout(scene.subtitles, lang, canvas_size)
    caption_cache = karaoke.build_caption_frame_cache(caption_layout)
    pan_targets = kenburns.pan_targets_for_template(
        scene.template_type.value, *bg_source.size, alternate=(scene_index % 2 == 1)
    )

    frame_fn = make_frame_function(
        scene, static_layers, caption_cache, bg_source, pan_targets, canvas_size,
        presenter_source=presenter_source, presenter_layout=presenter_layout,
        lang=lang,
    )
    clip = VideoClip(frame_function=frame_fn, duration=scene.scene_duration_sec).with_fps(VIDEO_FPS)

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

    presenter_source, presenter_layout = resolve_presenter(lang, canvas_size)

    clips = [
        render_scene_clip(s, lang, i, canvas_size, presenter_source, presenter_layout)
        for i, s in enumerate(scenes)
    ]
    final = concatenate_videoclips(clips, method="chain")
    try:
        _write_with_fallback(final, out_path, codec_pref)
    finally:
        for clip in (final, *clips):
            try:
                clip.close()
            except Exception:
                logger.debug("failed to close clip", exc_info=True)
    return out_path
