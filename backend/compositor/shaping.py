"""Complex text layout via HarfBuzz + FreeType.

Pillow's Windows wheels are built without Raqm, so ImageDraw.text() performs
no complex text layout: it emits glyphs in codepoint order. For Indic scripts
that is wrong, not merely ugly — vowel signs that render to the left of their
consonant are not reordered, and conjuncts do not ligate. "किसान" comes out as
"कसिान", which is misspelt rather than obviously broken, so it survives review
by anyone who does not read the script.

This module shapes with HarfBuzz and rasterises the resulting glyph IDs with
FreeType, which is what Raqm would have done inside Pillow.

Coordinate conventions match Pillow's default text anchor ("la"): the y passed
to draw_shaped_text is the top of the line, not the baseline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised by availability, not by branch
  import freetype
  import uharfbuzz as hb

  SHAPING_AVAILABLE = True
except ImportError:  # pragma: no cover
  freetype = None
  hb = None
  SHAPING_AVAILABLE = False


# FreeType and HarfBuzz both work in 26.6 fixed point: 64 units per pixel.
_FIXED = 64


@dataclass(frozen=True)
class ShapedGlyph:
  glyph_id: int
  x_offset: float
  y_offset: float
  x_advance: float
  cluster: int


@lru_cache(maxsize=32)
def _load_faces(font_path: str, size_px: int):
  """FreeType face for rasterising, HarfBuzz font for shaping, same size."""
  ft_face = freetype.Face(font_path)
  ft_face.set_char_size(size_px * _FIXED)

  blob = hb.Blob.from_file_path(font_path)
  hb_font = hb.Font(hb.Face(blob))
  # Map upem to size_px in 26.6 so advances come back in the same units
  # FreeType is rasterising at.
  hb_font.scale = (size_px * _FIXED, size_px * _FIXED)
  return ft_face, hb_font


def shape(text: str, font_path: str, size_px: int, language: Optional[str] = None) -> List[ShapedGlyph]:
  """Shape `text`, returning positioned glyph IDs in visual order."""
  _, hb_font = _load_faces(font_path, size_px)

  buf = hb.Buffer()
  buf.add_str(text)
  buf.guess_segment_properties()
  if language:
    try:
      buf.language = language
    except Exception:
      pass  # an unknown tag is not worth failing a render over

  hb.shape(hb_font, buf)

  return [
      ShapedGlyph(
          glyph_id=info.codepoint,
          x_offset=pos.x_offset / _FIXED,
          y_offset=pos.y_offset / _FIXED,
          x_advance=pos.x_advance / _FIXED,
          cluster=info.cluster,
      )
      for info, pos in zip(buf.glyph_infos, buf.glyph_positions)
  ]


def ascender_px(font_path: str, size_px: int) -> float:
  ft_face, _ = _load_faces(font_path, size_px)
  return ft_face.size.ascender / _FIXED


def line_height_px(font_path: str, size_px: int) -> float:
  ft_face, _ = _load_faces(font_path, size_px)
  return ft_face.size.height / _FIXED


def advance_width(text: str, font_path: str, size_px: int) -> float:
  return sum(g.x_advance for g in shape(text, font_path, size_px))


def ink_bbox(text: str, font_path: str, size_px: int) -> Tuple[int, int, int, int]:
  """Tight pixel bounds of the drawn glyphs, relative to the (x, y) top-left
  origin that draw_shaped_text uses. Mirrors ImageFont.getbbox()."""
  glyphs = shape(text, font_path, size_px)
  if not glyphs:
    return (0, 0, 0, 0)

  ft_face, _ = _load_faces(font_path, size_px)
  baseline = ascender_px(font_path, size_px)

  left = top = float("inf")
  right = bottom = float("-inf")
  pen_x = 0.0
  found = False

  for g in glyphs:
    ft_face.load_glyph(g.glyph_id, freetype.FT_LOAD_RENDER)
    bmp = ft_face.glyph.bitmap
    if bmp.width and bmp.rows:
      gx = pen_x + g.x_offset + ft_face.glyph.bitmap_left
      gy = baseline - g.y_offset - ft_face.glyph.bitmap_top
      left = min(left, gx)
      top = min(top, gy)
      right = max(right, gx + bmp.width)
      bottom = max(bottom, gy + bmp.rows)
      found = True
    pen_x += g.x_advance

  if not found:
    return (0, 0, 0, 0)
  return (int(np.floor(left)), int(np.floor(top)), int(np.ceil(right)), int(np.ceil(bottom)))


def _glyph_mask(ft_face, glyph_id: int) -> Optional[Tuple[np.ndarray, int, int]]:
  ft_face.load_glyph(glyph_id, freetype.FT_LOAD_RENDER)
  bmp = ft_face.glyph.bitmap
  if not bmp.width or not bmp.rows:
    return None
  # bmp.buffer is a flat list of rows padded to bmp.pitch bytes.
  arr = np.array(bmp.buffer, dtype=np.uint8).reshape(bmp.rows, bmp.pitch)[:, : bmp.width]
  return arr, ft_face.glyph.bitmap_left, ft_face.glyph.bitmap_top


def draw_shaped_text(
    layer: Image.Image,
    text: str,
    font_path: str,
    size_px: int,
    xy: Tuple[int, int],
    color: Tuple[int, int, int],
    language: Optional[str] = None,
) -> Image.Image:
  """Composite `text` onto an RGBA `layer` at `xy` (top-left, Pillow's "la").

  Glyphs are blitted as alpha masks so antialiasing is preserved and the
  result alpha-composites cleanly over the layers beneath it.
  """
  glyphs = shape(text, font_path, size_px, language)
  if not glyphs:
    return layer

  ft_face, _ = _load_faces(font_path, size_px)
  x0, y0 = xy
  baseline = y0 + ascender_px(font_path, size_px)

  canvas_w, canvas_h = layer.size
  alpha = np.zeros((canvas_h, canvas_w), dtype=np.uint8)

  pen_x = float(x0)
  for g in glyphs:
    mask = _glyph_mask(ft_face, g.glyph_id)
    if mask is not None:
      bitmap, bmp_left, bmp_top = mask
      gx = int(round(pen_x + g.x_offset + bmp_left))
      gy = int(round(baseline - g.y_offset - bmp_top))

      # Clip against the canvas; glyphs can legitimately fall partly outside.
      sx0, sy0 = max(0, -gx), max(0, -gy)
      dx0, dy0 = max(0, gx), max(0, gy)
      dx1 = min(canvas_w, gx + bitmap.shape[1])
      dy1 = min(canvas_h, gy + bitmap.shape[0])

      if dx1 > dx0 and dy1 > dy0:
        patch = bitmap[sy0 : sy0 + (dy1 - dy0), sx0 : sx0 + (dx1 - dx0)]
        target = alpha[dy0:dy1, dx0:dx1]
        # Overlapping marks (matras, nukta) must not darken each other.
        np.maximum(target, patch, out=target)

    pen_x += g.x_advance

  rgb = np.empty((canvas_h, canvas_w, 4), dtype=np.uint8)
  rgb[:, :, 0] = color[0]
  rgb[:, :, 1] = color[1]
  rgb[:, :, 2] = color[2]
  rgb[:, :, 3] = alpha

  glyph_layer = Image.fromarray(rgb)
  layer.alpha_composite(glyph_layer)
  return layer


def cluster_advances(text: str, font_path: str, size_px: int) -> Sequence[Tuple[int, float]]:
  """(cluster_index, advance) pairs — used to map shaped output back to the
  source string, which karaoke needs to colour individual words."""
  out = []
  for g in shape(text, font_path, size_px):
    out.append((g.cluster, g.x_advance))
  return out
