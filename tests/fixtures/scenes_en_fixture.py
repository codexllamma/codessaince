"""Hand-written English fixture scenes for building/testing the compositor
standalone, since the upstream OCR/LLM/TTS stages don't exist yet.

Deliberately exercises two different layer combinations:
- Scene 1 (HERO_ANNOUNCEMENT): no metric card, proves layer 3 is absent.
- Scene 2 (METRIC_FOCUS): highlight_metric/highlight_sublabel populated,
  proves layer 3 presence + exercises the badge_tag 22-char budget overflow
  (the badge text below is 23 chars, taken verbatim from README Appendix A).
"""

from __future__ import annotations

from typing import List

from models.schemas import (
    ScriptSegment,
    SceneDefinition,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
    WordTimestamp,
)
from tests.fixtures.make_placeholder_audio import ensure_fixture_audio

SCENE_TAIL_PAD_SEC = 0.35  # README §6 default


def _duration(subtitles: List[WordTimestamp]) -> float:
    """README §8.6 dynamic timing rule."""
    return subtitles[-1].end_sec + SCENE_TAIL_PAD_SEC


def _scene_1_hero_announcement() -> SceneDefinition:
    words = [
        ("The", 0.00, 0.15, False),
        ("Ministry", 0.18, 0.55, False),
        ("of", 0.58, 0.66, False),
        ("Agriculture", 0.70, 1.25, False),
        ("announces", 1.30, 1.85, False),
        ("the", 1.88, 1.98, False),
        ("seventeenth", 2.02, 2.55, False),
        ("installment", 2.60, 3.10, False),
        ("of", 3.13, 3.22, False),
        ("PM-KISAN", 3.30, 4.10, True),
        ("starting", 4.45, 4.85, False),
        ("this", 4.88, 5.02, False),
        ("month.", 5.05, 5.45, False),
    ]
    subtitles = [WordTimestamp(word=w, start_sec=s, end_sec=e, is_core_fact=c) for w, s, e, c in words]

    return SceneDefinition(
        scene_id=1,
        template_type=TemplateType.HERO_ANNOUNCEMENT,
        script_segments=[
            ScriptSegment(type="filler", text="The Ministry of Agriculture announces the seventeenth installment of"),
            ScriptSegment(type="core_fact", text="PM-KISAN", emphasis_level="strong", pause_after_ms=300, linked_fact_id="f1"),
            ScriptSegment(type="filler", text="starting this month."),
        ],
        full_spoken_text="The Ministry of Agriculture announces the seventeenth installment of PM-KISAN starting this month.",
        visual_hierarchy=VisualTextHierarchy(
            badge_tag="GOVERNMENT NOTICE",
            headline="17th PM-KISAN Installment Announced",
            subtext="Ministry of Agriculture confirms release for eligible farmers nationwide",
        ),
        asset=VisualAssetSelection(
            asset_id="gradient_hero_01",
            asset_type="mesh_gradient",
            file_path="",
            accent_color="#22C55E",  # accent.agriculture, Appendix D
            dim_overlay_opacity=0.65,
        ),
        audio_path=ensure_fixture_audio(1, "en", _duration(subtitles), freq_hz=220.0),
        scene_duration_sec=_duration(subtitles),
        subtitles=subtitles,
    )


def _scene_2_metric_focus() -> SceneDefinition:
    words = [
        ("Eligible", 0.00, 0.48, False),
        ("farmers", 0.52, 0.95, False),
        ("will", 0.98, 1.10, False),
        ("receive", 1.14, 1.60, False),
        ("two", 1.62, 1.88, True),
        ("thousand", 1.90, 2.35, True),
        ("rupees", 2.38, 2.85, True),
        ("directly", 3.20, 3.70, False),
        ("in", 3.72, 3.80, False),
        ("their", 3.83, 4.05, False),
        ("bank", 4.08, 4.40, False),
        ("account.", 4.43, 4.95, False),
    ]
    subtitles = [WordTimestamp(word=w, start_sec=s, end_sec=e, is_core_fact=c) for w, s, e, c in words]

    return SceneDefinition(
        scene_id=2,
        template_type=TemplateType.METRIC_FOCUS,
        script_segments=[
            ScriptSegment(type="filler", text="Eligible farmers will receive"),
            ScriptSegment(type="core_fact", text="two thousand rupees", emphasis_level="strong", pause_after_ms=350, linked_fact_id="f2"),
            ScriptSegment(type="filler", text="directly in their bank account.", pause_after_ms=200),
        ],
        full_spoken_text="Eligible farmers will receive two thousand rupees directly in their bank account.",
        visual_hierarchy=VisualTextHierarchy(
            badge_tag="DIRECT BENEFIT TRANSFER",  # 23 chars, verbatim from README Appendix A — exercises the 22-char budget overflow path
            headline="₹2,000 per eligible farmer",
            subtext="Credited directly to the registered bank account",
            highlight_metric="₹2,000",
            highlight_sublabel="17th instalment",
        ),
        asset=VisualAssetSelection(
            asset_id="gradient_metric_01",
            asset_type="mesh_gradient",
            file_path="",
            accent_color="#38BDF8",  # accent.finance, Appendix D
            dim_overlay_opacity=0.70,
        ),
        audio_path=ensure_fixture_audio(2, "en", _duration(subtitles), freq_hz=330.0),
        scene_duration_sec=_duration(subtitles),
        subtitles=subtitles,
    )


def get_fixture_scenes() -> List[SceneDefinition]:
    return [_scene_1_hero_announcement(), _scene_2_metric_focus()]
