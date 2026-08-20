"""models/schemas.py

Single source of truth for IndicGov-Sentinel data contracts.
Changes here must be coordinated across all team members.
"""

from enum import Enum
import re
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# =====================================================================
# 7.1 Fact Extraction Schemas
# =====================================================================


class FactCategory(str, Enum):
  SCHEME_NAME = "SCHEME_NAME"
  AMOUNT = "AMOUNT"
  DEADLINE = "DEADLINE"
  ELIGIBILITY = "ELIGIBILITY"
  BENEFICIARY = "BENEFICIARY"
  AUTHORITY = "AUTHORITY"
  ACTION_REQUIRED = "ACTION_REQUIRED"


class ExtractedFact(BaseModel):
  fact_id: str = Field(
      ...,
      pattern=r"^f\d+$",
      description="Stable handle in format f<n>, unique within a job",
  )
  category: FactCategory
  raw_value: str
  normalized_value: str
  source_page: int = Field(default=1, ge=1)
  source_char_start: int = Field(..., ge=0)
  source_char_end: int = Field(..., ge=0)
  confidence_score: float = Field(..., ge=0.0, le=1.0)
  is_verified: bool = True
  officer_override: Optional[str] = None

  @model_validator(mode="after")
  def validate_character_offsets(self) -> "ExtractedFact":
    if self.source_char_end <= self.source_char_start:
      raise ValueError(
          f"source_char_end ({self.source_char_end}) must be strictly greater "
          f"than source_char_start ({self.source_char_start})"
      )
    return self

  @property
  def effective_value(self) -> str:
    """Resolution order for display: officer_override > normalized_value > raw_value."""
    if self.officer_override is not None and self.officer_override.strip():
      return self.officer_override
    if self.normalized_value is not None and self.normalized_value.strip():
      return self.normalized_value
    return self.raw_value


# =====================================================================
# 7.2 Prosody and Scripting Schemas
# =====================================================================


class ScriptSegment(BaseModel):
  type: Literal["filler", "core_fact"]
  text: str
  emphasis_level: Literal["none", "moderate", "strong"] = "none"
  pause_after_ms: int = Field(default=0, ge=0)
  linked_fact_id: Optional[str] = None

  @model_validator(mode="after")
  def validate_core_fact_link(self) -> "ScriptSegment":
    if self.type == "core_fact" and not self.linked_fact_id:
      raise ValueError("A segment of type 'core_fact' must carry a linked_fact_id")
    return self


# =====================================================================
# 7.3 Visual Directive Schemas
# =====================================================================


class TemplateType(str, Enum):
  HERO_ANNOUNCEMENT = "HERO_ANNOUNCEMENT"
  METRIC_FOCUS = "METRIC_FOCUS"
  DEADLINE_ALERT = "DEADLINE_ALERT"
  OUTRO_CALL_TO_ACTION = "OUTRO_CALL_TO_ACTION"


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
  # Carried on every manifest entry (section 10.1) and consumed by the
  # compositor for the metric-card glow, alert pill, and the tint of the
  # procedural mesh_gradient fallback. Default is accent.finance.
  accent_color: str = Field(default="#38BDF8", pattern=r"^#[0-9A-Fa-f]{6}$")
  dim_overlay_opacity: float = Field(default=0.65, ge=0.0, le=1.0)


class WordTimestamp(BaseModel):
  word: str
  start_sec: float = Field(..., ge=0.0)
  end_sec: float = Field(..., ge=0.0)
  is_core_fact: bool = False

  @model_validator(mode="after")
  def validate_duration_order(self) -> "WordTimestamp":
    if self.end_sec < self.start_sec:
      raise ValueError(
          f"end_sec ({self.end_sec}) cannot be less than start_sec ({self.start_sec})"
      )
    return self


# =====================================================================
# 7.4 Scene and Master Job Payload
# =====================================================================


class SceneDefinition(BaseModel):
  scene_id: int = Field(..., ge=1)
  template_type: TemplateType
  script_segments: List[ScriptSegment]
  full_spoken_text: str
  visual_hierarchy: VisualTextHierarchy
  asset: VisualAssetSelection
  audio_path: Optional[str] = None
  scene_duration_sec: Optional[float] = None
  subtitles: Optional[List[WordTimestamp]] = None

  @model_validator(mode="after")
  def validate_media_synthesis_invariants(self) -> "SceneDefinition":
    media_fields = [self.audio_path, self.scene_duration_sec, self.subtitles]
    all_none = all(field is None for field in media_fields)
    all_set = all(field is not None for field in media_fields)

    if not (all_none or all_set):
      raise ValueError(
          "Invariant violated: audio_path, scene_duration_sec, and subtitles "
          "must all be None (pre-synthesis) or all non-None (post-synthesis)."
      )
    return self


class PipelineTelemetry(BaseModel):
  ocr_latency_sec: float = 0.0
  extraction_confidence_avg: float = 0.0
  nli_entailment_score: float = 0.0
  entity_preservation_rate: float = 1.0
  speech_visual_drift_ms: float = 0.0


class NoticeVideoJob(BaseModel):
  job_id: str
  source_file_name: str
  raw_extracted_text: str
  target_languages: List[Literal["en", "hi", "ta", "te", "bn", "mr"]]
  selected_voice_id: str
  voice_speed_modifier: str = "+0%"
  extracted_facts: List[ExtractedFact]
  master_scenes_en: List[SceneDefinition]
  localized_scenes: Dict[str, List[SceneDefinition]] = Field(
      default_factory=dict
  )
  telemetry: Optional[PipelineTelemetry] = None
  officer_approved: bool = False
  final_video_paths: Dict[str, str] = Field(default_factory=dict)

  @model_validator(mode="after")
  def validate_job_invariants(self) -> "NoticeVideoJob":
    # 1. localized_scenes validation
    expected_scene_ids = [scene.scene_id for scene in self.master_scenes_en]
    master_len = len(self.master_scenes_en)

    for lang, scenes in self.localized_scenes.items():
      if len(scenes) != master_len:
        raise ValueError(
            f"localized_scenes['{lang}'] length ({len(scenes)}) does not match "
            f"master_scenes_en length ({master_len})"
        )
      localized_ids = [scene.scene_id for scene in scenes]
      if localized_ids != expected_scene_ids:
        raise ValueError(
            f"localized_scenes['{lang}'] scene_id ordering ({localized_ids}) does "
            f"not match master_scenes_en ordering ({expected_scene_ids})"
        )

    # 2. final_video_paths keys must be a subset of target_languages
    for lang in self.final_video_paths.keys():
      if lang not in self.target_languages:
        raise ValueError(
            f"final_video_paths contains '{lang}' which is not in target_languages "
            f"({self.target_languages})"
        )

    return self