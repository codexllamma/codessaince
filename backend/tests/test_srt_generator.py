from pathlib import Path
import pytest

from models.schemas import (
    FactCategory,
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
    WordTimestamp,
)
from services.srt_generator import _format_srt_time, generate_srt_content, export_srt_file


def test_format_srt_time():
    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(1.234) == "00:00:01,234"
    assert _format_srt_time(65.5) == "00:01:05,500"
    assert _format_srt_time(3661.125) == "01:01:01,125"


def test_generate_srt_content_with_subtitles(tmp_path: Path):
    scene1 = SceneDefinition(
        scene_id=1,
        template_type=TemplateType.HERO_ANNOUNCEMENT,
        script_segments=[ScriptSegment(type="filler", text="Official notice from Ministry of Agriculture.")],
        full_spoken_text="Official notice from Ministry of Agriculture.",
        visual_hierarchy=VisualTextHierarchy(badge_tag="NOTICE", headline="PM KISAN", subtext="Details"),
        asset=VisualAssetSelection(asset_id="default", asset_type="static_graphic", file_path=""),
        audio_path="static/audio/dummy1.mp3",
        scene_duration_sec=3.0,
        subtitles=[
            WordTimestamp(word="Official", start_sec=0.0, end_sec=0.5),
            WordTimestamp(word="notice", start_sec=0.5, end_sec=1.0),
            WordTimestamp(word="from", start_sec=1.0, end_sec=1.3),
            WordTimestamp(word="Ministry", start_sec=1.3, end_sec=1.8),
            WordTimestamp(word="of", start_sec=1.8, end_sec=2.0),
            WordTimestamp(word="Agriculture.", start_sec=2.0, end_sec=2.8),
        ],
    )

    scene2 = SceneDefinition(
        scene_id=2,
        template_type=TemplateType.METRIC_FOCUS,
        script_segments=[ScriptSegment(type="core_fact", text="Rs 2000 transferred.", linked_fact_id="f1")],
        full_spoken_text="Rs 2000 transferred.",
        visual_hierarchy=VisualTextHierarchy(badge_tag="PAYMENT", headline="₹2,000", subtext="Direct transfer"),
        asset=VisualAssetSelection(asset_id="default", asset_type="static_graphic", file_path=""),
        audio_path="static/audio/dummy2.mp3",
        scene_duration_sec=2.5,
        subtitles=[
            WordTimestamp(word="Rs", start_sec=0.0, end_sec=0.4),
            WordTimestamp(word="2000", start_sec=0.4, end_sec=1.2, is_core_fact=True),
            WordTimestamp(word="transferred.", start_sec=1.2, end_sec=2.2),
        ],
    )

    srt_content = generate_srt_content([scene1, scene2])
    assert "00:00:00,000 -->" in srt_content
    assert "Official notice from Ministry of Agriculture." in srt_content

    # Scene 2 cumulative offset is 3.0 seconds
    assert "00:00:03,000 --> 00:00:05,200" in srt_content
    assert "Rs 2000 transferred." in srt_content

    out_file = tmp_path / "test.srt"
    export_srt_file([scene1, scene2], out_file)
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == srt_content
