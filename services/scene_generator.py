from typing import Dict, List, Optional
from models.schemas import (
    ExtractedFact,
    FactCategory,
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
)


def build_scenes_from_facts(facts: List[ExtractedFact]) -> List[SceneDefinition]:
  fact_map: Dict[FactCategory, ExtractedFact] = {f.category: f for f in facts}

  scheme = fact_map.get(FactCategory.SCHEME_NAME)
  amount = fact_map.get(FactCategory.AMOUNT)
  deadline = fact_map.get(FactCategory.DEADLINE)
  authority = fact_map.get(FactCategory.AUTHORITY)
  action = fact_map.get(FactCategory.ACTION_REQUIRED)

  scenes: List[SceneDefinition] = []
  scene_idx = 1

  # Scene 1: Hero Announcement
  scheme_name = (
      scheme.effective_value if scheme else "New Government Initiative"
  )
  auth_name = (
      authority.effective_value if authority else "Government of India"
  )

  s1_segments = [
      ScriptSegment(
          type="filler",
          text=f"Official announcement issued by the {auth_name}.",
          emphasis_level="none",
          pause_after_ms=100,
      ),
      ScriptSegment(
          type="core_fact",
          text=f"Release of {scheme_name}",
          emphasis_level="strong",
          pause_after_ms=350,
          linked_fact_id=scheme.fact_id if scheme else None,
      ),
      ScriptSegment(
          type="filler",
          text="has been officially notified.",
          emphasis_level="none",
          pause_after_ms=200,
      ),
  ]

  scenes.append(
      SceneDefinition(
          scene_id=scene_idx,
          template_type=TemplateType.HERO_ANNOUNCEMENT,
          script_segments=s1_segments,
          full_spoken_text=" ".join(seg.text for seg in s1_segments),
          visual_hierarchy=VisualTextHierarchy(
              badge_tag="OFFICIAL NOTICE",
              headline=scheme_name,
              subtext=auth_name,
              highlight_metric=None,
              highlight_sublabel=None,
          ),
          asset=VisualAssetSelection(
              asset_id="broll_agri_01",
              asset_type="video_loop",
              file_path="assets/broll/agriculture_wheat_01.mp4",
              dim_overlay_opacity=0.65,
          ),
      )
  )
  scene_idx += 1

  # Scene 2: Core Benefit / Metric Focus
  if amount:
    amt_val = amount.effective_value
    s2_segments = [
        ScriptSegment(
            type="filler",
            text="Under this installment, eligible beneficiaries will receive",
            emphasis_level="none",
            pause_after_ms=100,
        ),
        ScriptSegment(
            type="core_fact",
            text=f"{amt_val}",
            emphasis_level="strong",
            pause_after_ms=400,
            linked_fact_id=amount.fact_id,
        ),
        ScriptSegment(
            type="filler",
            text="transferred directly via Direct Benefit Transfer.",
            emphasis_level="none",
            pause_after_ms=200,
        ),
    ]

    scenes.append(
        SceneDefinition(
            scene_id=scene_idx,
            template_type=TemplateType.METRIC_FOCUS,
            script_segments=s2_segments,
            full_spoken_text=" ".join(seg.text for seg in s2_segments),
            visual_hierarchy=VisualTextHierarchy(
                badge_tag="FINANCIAL BENEFIT",
                headline="Direct Benefit Transfer",
                subtext="Direct bank transfer to eligible accounts",
                highlight_metric=amt_val,
                highlight_sublabel="Per Beneficiary",
            ),
            asset=VisualAssetSelection(
                asset_id="broll_bank_01",
                asset_type="video_loop",
                file_path="assets/broll/banking_digital_rupee.mp4",
                dim_overlay_opacity=0.70,
            ),
        )
    )
    scene_idx += 1

  # Scene 3: Deadline & Action Alert
  if deadline or action:
    dl_val = (
        deadline.effective_value
        if deadline
        else "the prescribed cutoff date"
    )
    act_val = (
        action.effective_value
        if action
        else "Complete verification"
    )

    s3_segments = [
        ScriptSegment(
            type="filler",
            text="Please ensure you",
            emphasis_level="none",
            pause_after_ms=50,
        ),
        ScriptSegment(
            type="core_fact",
            text=f"{act_val}",
            emphasis_level="moderate",
            pause_after_ms=250,
            linked_fact_id=action.fact_id if action else None,
        ),
        ScriptSegment(
            type="filler",
            text="on or before the mandatory deadline of",
            emphasis_level="none",
            pause_after_ms=100,
        ),
        ScriptSegment(
            type="core_fact",
            text=f"{dl_val}.",
            emphasis_level="strong",
            pause_after_ms=400,
            linked_fact_id=deadline.fact_id if deadline else None,
        ),
    ]

    scenes.append(
        SceneDefinition(
            scene_id=scene_idx,
            template_type=TemplateType.DEADLINE_ALERT,
            script_segments=s3_segments,
            full_spoken_text=" ".join(seg.text for seg in s3_segments),
            visual_hierarchy=VisualTextHierarchy(
                badge_tag="DEADLINE ALERT",
                headline=act_val,
                subtext="Mandatory compliance requirement",
                highlight_metric=dl_val,
                highlight_sublabel="Cutoff Date",
            ),
            asset=VisualAssetSelection(
                asset_id="broll_alert_01",
                asset_type="video_loop",
                file_path="assets/broll/abstract_alert_loop.mp4",
                dim_overlay_opacity=0.75,
            ),
        )
    )
    scene_idx += 1

  # Scene 4: Outro / Official Source
  s4_segments = [
      ScriptSegment(
          type="filler",
          text="For official status tracking and grievances, visit the national portal or contact your local administrative office.",
          emphasis_level="none",
          pause_after_ms=300,
      )
  ]

  scenes.append(
      SceneDefinition(
          scene_id=scene_idx,
          template_type=TemplateType.OUTRO_CALL_TO_ACTION,
          script_segments=s4_segments,
          full_spoken_text=" ".join(seg.text for seg in s4_segments),
          visual_hierarchy=VisualTextHierarchy(
              badge_tag="OFFICIAL PORTAL",
              headline="Verify Online",
              subtext="pmkisan.gov.in",
              highlight_metric=None,
              highlight_sublabel="National Helpdesk: 155261",
          ),
          asset=VisualAssetSelection(
              asset_id="broll_agri_01",
              asset_type="video_loop",
              file_path="assets/broll/agriculture_wheat_01.mp4",
              dim_overlay_opacity=0.65,
          ),
      )
  )

  return scenes