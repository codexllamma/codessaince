from typing import Dict, List, Optional
from models.schemas import (
    ExtractedFact,
    FactCategory,
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualTextHierarchy,
)
from services.asset_matcher import match_visual_asset


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
  scheme_name = scheme.effective_value if scheme else "Government Notice"
  auth_name = (
      authority.effective_value if authority else "Ministry of Agriculture"
  )

  s1_segments = [
      ScriptSegment(
          type="filler",
          text=f"Official announcement from the {auth_name}.",
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
  ]
  s1_spoken = " ".join(seg.text for seg in s1_segments)

  scenes.append(
      SceneDefinition(
          scene_id=scene_idx,
          template_type=TemplateType.HERO_ANNOUNCEMENT,
          script_segments=s1_segments,
          full_spoken_text=s1_spoken,
          visual_hierarchy=VisualTextHierarchy(
              badge_tag="OFFICIAL NOTICE",
              headline=scheme_name,
              subtext=auth_name,
          ),
          asset=match_visual_asset(TemplateType.HERO_ANNOUNCEMENT, s1_spoken),
      )
  )
  scene_idx += 1

  # Scene 2: Metric Focus
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
            text="directly transferred to bank accounts.",
            emphasis_level="none",
            pause_after_ms=200,
        ),
    ]
    s2_spoken = " ".join(seg.text for seg in s2_segments)

    scenes.append(
        SceneDefinition(
            scene_id=scene_idx,
            template_type=TemplateType.METRIC_FOCUS,
            script_segments=s2_segments,
            full_spoken_text=s2_spoken,
            visual_hierarchy=VisualTextHierarchy(
                badge_tag="DISBURSEMENT",
                headline="Direct Benefit Transfer",
                subtext="Direct bank transfer to eligible accounts",
                highlight_metric=amt_val,
                highlight_sublabel="Per Beneficiary",
            ),
            asset=match_visual_asset(TemplateType.METRIC_FOCUS, s2_spoken),
        )
    )
    scene_idx += 1

  # Scene 3: Deadline Alert
  if deadline or action:
    dl_val = (
        deadline.effective_value
        if deadline
        else "the specified cutoff date"
    )
    act_val = (
        action.effective_value
        if action
        else "Complete verification"
    )

    s3_segments = [
        ScriptSegment(
            type="filler",
            text="Beneficiaries must complete",
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
            text="on or before",
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
    s3_spoken = " ".join(seg.text for seg in s3_segments)

    scenes.append(
        SceneDefinition(
            scene_id=scene_idx,
            template_type=TemplateType.DEADLINE_ALERT,
            script_segments=s3_segments,
            full_spoken_text=s3_spoken,
            visual_hierarchy=VisualTextHierarchy(
                badge_tag="DEADLINE ALERT",
                headline=act_val,
                subtext="Mandatory compliance requirement",
                highlight_metric=dl_val,
                highlight_sublabel="Cutoff Date",
            ),
            asset=match_visual_asset(TemplateType.DEADLINE_ALERT, s3_spoken),
        )
    )
    scene_idx += 1

  # Scene 4: Outro CTA
  s4_segments = [
      ScriptSegment(
          type="filler",
          text="For official status and updates, visit pmkisan.gov.in.",
          emphasis_level="none",
          pause_after_ms=300,
      )
  ]
  s4_spoken = " ".join(seg.text for seg in s4_segments)

  scenes.append(
      SceneDefinition(
          scene_id=scene_idx,
          template_type=TemplateType.OUTRO_CALL_TO_ACTION,
          script_segments=s4_segments,
          full_spoken_text=s4_spoken,
          visual_hierarchy=VisualTextHierarchy(
              badge_tag="OFFICIAL PORTAL",
              headline="Verify Online",
              subtext="pmkisan.gov.in",
              highlight_sublabel="National Helpdesk: 155261",
          ),
          asset=match_visual_asset(TemplateType.OUTRO_CALL_TO_ACTION, s4_spoken),
      )
  )

  return scenes