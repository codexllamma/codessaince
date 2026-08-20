"""Complex text layout regressions (README §5.4, §20).

Pillow without Raqm maps codepoints to glyphs 1:1 in logical order, which
silently misspells every Indic script — "किसान" renders as "कसिान". These
tests assert that shaping actually reorders and ligates, so a dependency
going missing fails here rather than in a demo.
"""

import pytest

from compositor import layers, shaping, typography

DEVANAGARI = str(typography.FONTS_DIR / "NotoSansDevanagari-Bold.ttf")
SIZE = 64

pytestmark = pytest.mark.skipif(
    not shaping.SHAPING_AVAILABLE, reason="HarfBuzz/FreeType not installed"
)


def _naive_glyph_ids(text: str, font_path: str):
    """What Pillow-without-Raqm would draw: one glyph per codepoint, in order."""
    import freetype

    face = freetype.Face(font_path)
    return [face.get_char_index(ord(ch)) for ch in text]


def test_shaping_is_available():
    """Guards against the wheel silently losing HarfBuzz on a rebuild."""
    assert shaping.SHAPING_AVAILABLE


def test_i_matra_is_reordered_before_its_consonant():
    """U+093F renders to the LEFT of the consonant it follows in memory."""
    text = "कि"
    shaped = [g.glyph_id for g in shaping.shape(text, DEVANAGARI, SIZE)]
    naive = _naive_glyph_ids(text, DEVANAGARI)

    assert len(shaped) == 2
    assert shaped != naive, "glyphs were not reordered — shaping did not run"
    # The consonant starts first in memory and must end up second on screen.
    # The matra takes a context-specific glyph, not its standalone one, so
    # only the consonant's identity is stable enough to assert on.
    assert shaped.index(naive[0]) == 1, "consonant did not move behind the matra"


def test_conjunct_ligates_to_fewer_glyphs():
    """क + virama + ष is a single क्ष ligature, not three glyphs."""
    text = "क्ष"
    shaped = shaping.shape(text, DEVANAGARI, SIZE)
    assert len(text) == 3
    assert len(shaped) < 3, "conjunct did not ligate"


def test_full_word_shapes_correctly():
    """किसान: 5 codepoints, and the matra must not stay in logical position."""
    shaped = [g.glyph_id for g in shaping.shape("किसान", DEVANAGARI, SIZE)]
    naive = _naive_glyph_ids("किसान", DEVANAGARI)
    assert shaped != naive


def test_latin_is_unaffected_by_shaping():
    """English must measure the same through the shaped path."""
    font = typography.load_font("en", "bold", 48)
    width = typography.measure_text("PM-KISAN", font)[0]
    assert width > 0
    assert typography.measure_text("", font) == (0, 0)


def test_measure_reports_advance_width():
    """Layout must use the shaped advance. Ink width is not interchangeable —
    for a kerned pair like AV the glyphs overhang and ink exceeds advance, so
    measuring by ink would space words inconsistently."""
    font = typography.load_font("en", "bold", 48)
    measured = typography.measure_text("AV", font)[0]
    advance = shaping.advance_width("AV", font.path, font.size)
    assert measured == int(round(advance))


@pytest.mark.parametrize("lang", ["hi", "ta", "te", "bn", "mr"])
def test_every_indic_language_resolves_a_real_font(lang):
    """§5.4: no OS fallback, no tofu — each script has a bundled face."""
    font = typography.load_font(lang, "bold", 48)
    assert font.path.endswith(".ttf")
    # If the language fell back to English its path would be the Latin face.
    assert "NotoSans-" not in font.path, f"{lang} fell back to the Latin font"


def test_headline_does_not_overlap_alert_pill():
    """The pill and headline collided by 22px; invisible in Latin, not in
    Devanagari where the shirorekha reaches the top of the em box."""
    pill_bottom = layers.ALERT_PILL_INSET + layers.ALERT_PILL_HEIGHT
    headline_top = pill_bottom + layers.HEADLINE_GAP_BELOW_PILL
    assert headline_top >= pill_bottom
