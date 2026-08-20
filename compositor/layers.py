"""Top-level compositor orchestration (README §8.6): 5-layer canvas, per-scene
rendering, job concatenation, and NVENC/libx264 fallback encoding.

Only VisualAssetSelection.asset_type == "mesh_gradient" is implemented in
this slice (README §10.2 fallback) — real B-roll video loops are out of
scope until the asset tag-matcher (§10) exists.
"""

from __future__ import annotations

import logging
import math
from typing import Callable, Dict, Tuple

import numpy as np
from PIL import Image, ImageDraw

from compositor import _ffmpeg, karaoke, kenburns, typography
from models.schemas import SceneDefinition, VisualAssetSelection

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

ALERT_PILL_INSET = 96
ALERT_PILL_HEIGHT = 56
METRIC_CARD_SIZE = (720, 320)


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
    """Procedural tinted gradient background (README §10.2 fallback), pre-rendered
    once at >= z_max * canvas size so Ken Burns can crop/pan without upscaling."""
    if asset.asset_type != "mesh_gradient":
        raise NotImplementedError(
            f"asset_type={asset.asset_type!r} not supported in this slice; only mesh_gradient is implemented"
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
    img = Image.fromarray(gradient, mode="RGB").convert("RGBA")

    if asset.dim_overlay_opacity > 0:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, round(255 * asset.dim_overlay_opacity)))
        img = Image.alpha_composite(img, overlay)

    return img


def _build_metric_card(scene: SceneDefinition, lang: str, canvas_size: Tuple[int, int]) -> Image.Image:
    W, H = canvas_size
    card_w, card_h = METRIC_CARD_SIZE
    x0, y0 = (W - card_w) // 2, (H - card_h) // 2
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

    metric_font = typography.load_font(lang, "bold", 96)
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


def _build_alert_pill(scene: SceneDefinition, lang: str, canvas_size: Tuple[int, int]) -> Image.Image:
    W, H = canvas_size
    badge_text = typography.enforce_budget(scene.visual_hierarchy.badge_tag, "badge_tag", lang)
    font = typography.load_font(lang, "bold", 26)
    tw, th = typography.measure_text(badge_text, font)
    pad_x = 24
    pill_w, pill_h = tw + 2 * pad_x, ALERT_PILL_HEIGHT

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    accent = _hex_to_rgb(scene.asset.accent_color)
    x0, y0 = ALERT_PILL_INSET, ALERT_PILL_INSET
    draw.rounded_rectangle([x0, y0, x0 + pill_w, y0 + pill_h], radius=pill_h // 2, fill=accent + (235,))
    layer.alpha_composite(typography.draw_text_layer(
        badge_text, font, "#0B1120", (W, H), (x0 + pad_x, y0 + (pill_h - th) // 2 - 4),
    ))
    return layer


def alert_pill_alpha(t: float, pulse_hz: float = 0.8) -> float:
    """0.7-1.0 pulse (README §8.6)."""
    return 0.85 + 0.15 * math.sin(2 * math.pi * pulse_hz * t)


def build_static_layers(
    scene: SceneDefinition, lang: str, canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)
) -> Dict[str, Image.Image]:
    """Layers built once per scene (not per frame): headline/subtext (layer 4),
    metric card if METRIC_FOCUS (layer 3), alert pill base (layer 5)."""
    W, H = canvas_size
    vh = scene.visual_hierarchy
    layers: Dict[str, Image.Image] = {}

    headline_text = typography.enforce_budget(vh.headline, "headline", lang)
    subtext_text = typography.enforce_budget(vh.subtext, "subtext", lang)
    headline_font = typography.load_font(lang, "bold", 76)
    subtext_font = typography.load_font(lang, "regular" if lang == "en" else "bold", 38)

    left_margin = 96
    max_text_width = W - 2 * left_margin
    layer4 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = round(H * 0.12)
    for line in typography.wrap_text(headline_text, headline_font, max_text_width, max_lines=2):
        layer4.alpha_composite(typography.draw_text_layer(line, headline_font, "#F8FAFC", (W, H), (left_margin, y)))
        y += headline_font.size + 10
    y += 12
    for line in typography.wrap_text(subtext_text, subtext_font, max_text_width, max_lines=2):
        layer4.alpha_composite(typography.draw_text_layer(line, subtext_font, "#CBD5E1", (W, H), (left_margin, y)))
        y += subtext_font.size + 8
    layers["headline_subtext"] = layer4

    if scene.template_type.value == "METRIC_FOCUS" and vh.highlight_metric:
        layers["metric_card"] = _build_metric_card(scene, lang, canvas_size)

    layers["alert_pill"] = _build_alert_pill(scene, lang, canvas_size)

    return layers


def make_frame_function(
    scene: SceneDefinition,
    static_layers: Dict[str, Image.Image],
    caption_cache,
    bg_source: Image.Image,
    pan_targets: Tuple[float, float, float, float],
    canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT),
) -> Callable[[float], np.ndarray]:
    W, H = canvas_size
    cx0, cy0, cx1, cy1 = pan_targets
    duration = scene.scene_duration_sec

    def frame_function(t: float) -> np.ndarray:
        frame = kenburns.render_frame(bg_source, t, duration, W, H, cx0, cy0, cx1, cy1).convert("RGBA")
        frame.alpha_composite(karaoke.get_caption_frame_for_time(caption_cache, t))
        if "metric_card" in static_layers:
            frame.alpha_composite(static_layers["metric_card"])
        frame.alpha_composite(static_layers["headline_subtext"])
        frame.alpha_composite(_with_alpha(static_layers["alert_pill"], alert_pill_alpha(t)))
        return np.asarray(frame.convert("RGB"))

    return frame_function


def render_scene_clip(scene: SceneDefinition, lang: str, scene_index: int, canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)):
    from moviepy import AudioFileClip, VideoClip

    if scene.scene_duration_sec is None or scene.subtitles is None:
        raise ValueError(f"scene {scene.scene_id} is missing synthesized duration/subtitles (mixed state, see README §7.4 invariant 1)")

    bg_source = build_background_source(scene.asset, *canvas_size)
    static_layers = build_static_layers(scene, lang, canvas_size)
    caption_layout = karaoke.build_caption_layout(scene.subtitles, lang, canvas_size)
    caption_cache = karaoke.build_caption_frame_cache(caption_layout)
    pan_targets = kenburns.pan_targets_for_template(
        scene.template_type.value, *bg_source.size, alternate=(scene_index % 2 == 1)
    )

    frame_fn = make_frame_function(scene, static_layers, caption_cache, bg_source, pan_targets, canvas_size)
    clip = VideoClip(frame_function=frame_fn, duration=scene.scene_duration_sec).with_fps(VIDEO_FPS)
    if scene.audio_path:
        clip = clip.with_audio(AudioFileClip(scene.audio_path))
    return clip


def _write_with_fallback(clip, out_path: str, codec_pref: str) -> None:
    if codec_pref == "h264_nvenc":
        try:
            clip.write_videofile(
                out_path, fps=VIDEO_FPS, codec="h264_nvenc", preset="p5",
                ffmpeg_params=["-rc", "vbr", "-cq", "23", "-b:v", "8M", "-maxrate", "12M"],
                audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
            )
            return
        except Exception:
            logger.warning("NVENC encode failed, falling back to libx264", exc_info=True)

    clip.write_videofile(
        out_path, fps=VIDEO_FPS, codec="libx264", preset="veryfast",
        audio_codec="aac", audio_bitrate="192k", pixel_format="yuv420p",
    )


def render_job(scenes, lang: str, out_path: str, codec_pref: str = "h264_nvenc", canvas_size: Tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)) -> str:
    _ffmpeg.ensure_ffmpeg_binary_env()
    from moviepy import concatenate_videoclips

    clips = [render_scene_clip(s, lang, i, canvas_size) for i, s in enumerate(scenes)]
    final = concatenate_videoclips(clips, method="chain")
    _write_with_fallback(final, out_path, codec_pref)
    return out_path
