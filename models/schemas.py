"""Pydantic schemas — single source of truth for pipeline data contracts.

This is a minimal subset covering only what the Stage 6 compositor consumes
(README.md sections 7.2-7.4). ExtractedFact, PipelineTelemetry, and
NoticeVideoJob are not needed by the compositor and are added when the
upstream (OCR/LLM/TTS) stages are built.
"""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TemplateType(str, Enum):
    HERO_ANNOUNCEMENT = "HERO_ANNOUNCEMENT"
    METRIC_FOCUS = "METRIC_FOCUS"
    DEADLINE_ALERT = "DEADLINE_ALERT"
    OUTRO_CALL_TO_ACTION = "OUTRO_CALL_TO_ACTION"


class ScriptSegment(BaseModel):
    type: Literal["filler", "core_fact"]
    text: str
    emphasis_level: Literal["none", "moderate", "strong"] = "none"
    pause_after_ms: int = 0
    linked_fact_id: Optional[str] = None


class VisualTextHierarchy(BaseModel):
    badge_tag: str
    headline: str
    subtext: str
    highlight_metric: Optional[str] = None
    highlight_sublabel: Optional[str] = None


class VisualAssetSelection(BaseModel):
    asset_id: str
    asset_type: Literal["video_loop", "static_graphic", "mesh_gradient"]
    file_path: str
    # Not in the README's literal §7.3 listing, but present on every manifest
    # entry (§10.1) and needed here since the asset-matcher (§10, out of scope
    # for this slice) isn't around yet to carry accent_color forward separately.
    accent_color: str = "#38BDF8"
    dim_overlay_opacity: float = 0.65


class WordTimestamp(BaseModel):
    word: str
    start_sec: float
    end_sec: float
    is_core_fact: bool = False


class SceneDefinition(BaseModel):
    scene_id: int
    template_type: TemplateType
    script_segments: List[ScriptSegment]
    full_spoken_text: str
    visual_hierarchy: VisualTextHierarchy
    asset: VisualAssetSelection
    audio_path: Optional[str] = None
    scene_duration_sec: Optional[float] = None
    subtitles: Optional[List[WordTimestamp]] = None
