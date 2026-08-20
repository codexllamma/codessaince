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
  scenes: List[SceneDefinition] = []
  scene_idx = 1
  
  # Group facts by category
  fact_map: Dict[FactCategory, List[ExtractedFact]] = {cat: [] for cat in FactCategory}
  for f in facts:
      fact_map[f.category].append(f)

  # 1. Hero Announcement (using first scheme and authority if available)
  schemes = fact_map.get(FactCategory.SCHEME_NAME, [])
  authorities = fact_map.get(FactCategory.AUTHORITY, [])
  
  scheme_name = schemes[0].effective_value if len(schemes) > 0 else "Government Notice"
  auth_name = authorities[0].effective_value if len(authorities) > 0 else "Official Department"

  s1_segments = [
      ScriptSegment(
          type="filler",
          text=f"Official announcement from the {auth_name}.",
          emphasis_level="none",
          pause_after_ms=100,
      ),
      ScriptSegment(
          type="core_fact" if schemes else "filler",
          text=f"Release of {scheme_name}",
          emphasis_level="strong",
          pause_after_ms=350,
          linked_fact_id=schemes[0].fact_id if schemes else None,
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
          asset=match_visual_asset(
              TemplateType.HERO_ANNOUNCEMENT, s1_spoken, [FactCategory.SCHEME_NAME, FactCategory.AUTHORITY]
          ),
      )
  )
  scene_idx += 1

  # 2. Iterate through all AMOUNT and ELIGIBILITY facts (METRIC_FOCUS scenes)
  for amount_fact in fact_map[FactCategory.AMOUNT]:
      amt_val = amount_fact.effective_value
      s2_segments = [
          ScriptSegment(type="filler", text="Under this initiative, eligible beneficiaries will receive", emphasis_level="none", pause_after_ms=100),
          ScriptSegment(type="core_fact", text=f"{amt_val}", emphasis_level="strong", pause_after_ms=400, linked_fact_id=amount_fact.fact_id),
          ScriptSegment(type="filler", text="directly transferred to bank accounts.", emphasis_level="none", pause_after_ms=200),
      ]
      s2_spoken = " ".join(seg.text for seg in s2_segments)
      scenes.append(
          SceneDefinition(
              scene_id=scene_idx, template_type=TemplateType.METRIC_FOCUS,
              script_segments=s2_segments, full_spoken_text=s2_spoken,
              visual_hierarchy=VisualTextHierarchy(
                  badge_tag="DISBURSEMENT", headline="Direct Benefit Transfer", subtext="Financial support allocation", highlight_metric=amt_val, highlight_sublabel="Allocated Amount"
              ),
              asset=match_visual_asset(TemplateType.METRIC_FOCUS, s2_spoken, [FactCategory.AMOUNT])
          )
      )
      scene_idx += 1

  for elig_fact in fact_map[FactCategory.ELIGIBILITY] + fact_map[FactCategory.BENEFICIARY]:
      elig_val = elig_fact.effective_value
      s_segments = [
          ScriptSegment(type="filler", text="This program is specifically designed for", emphasis_level="none", pause_after_ms=100),
          ScriptSegment(type="core_fact", text=f"{elig_val}.", emphasis_level="strong", pause_after_ms=300, linked_fact_id=elig_fact.fact_id),
      ]
      s_spoken = " ".join(seg.text for seg in s_segments)
      scenes.append(
          SceneDefinition(
              scene_id=scene_idx, template_type=TemplateType.METRIC_FOCUS,
              script_segments=s_segments, full_spoken_text=s_spoken,
              visual_hierarchy=VisualTextHierarchy(
                  badge_tag="ELIGIBILITY", headline="Target Beneficiaries", subtext="Program qualifications", highlight_metric="Eligible", highlight_sublabel=elig_val[:30]
              ),
              asset=match_visual_asset(TemplateType.METRIC_FOCUS, s_spoken, [FactCategory.ELIGIBILITY])
          )
      )
      scene_idx += 1

  # 3. Iterate through all DEADLINE and ACTION facts (DEADLINE_ALERT scenes)
  for act_fact in fact_map[FactCategory.ACTION_REQUIRED]:
      act_val = act_fact.effective_value
      s_segments = [
          ScriptSegment(type="filler", text="Citizens are strongly advised to", emphasis_level="none", pause_after_ms=100),
          ScriptSegment(type="core_fact", text=f"{act_val}.", emphasis_level="strong", pause_after_ms=400, linked_fact_id=act_fact.fact_id),
      ]
      s_spoken = " ".join(seg.text for seg in s_segments)
      scenes.append(
          SceneDefinition(
              scene_id=scene_idx, template_type=TemplateType.DEADLINE_ALERT,
              script_segments=s_segments, full_spoken_text=s_spoken,
              visual_hierarchy=VisualTextHierarchy(
                  badge_tag="ACTION REQUIRED", headline="Mandatory Action", subtext="Compliance requirement", highlight_metric="Action", highlight_sublabel=act_val[:30]
              ),
              asset=match_visual_asset(TemplateType.DEADLINE_ALERT, s_spoken, [FactCategory.ACTION_REQUIRED])
          )
      )
      scene_idx += 1

  for dl_fact in fact_map[FactCategory.DEADLINE]:
      dl_val = dl_fact.effective_value
      s_segments = [
          ScriptSegment(type="filler", text="Please ensure all requirements are met on or before", emphasis_level="none", pause_after_ms=100),
          ScriptSegment(type="core_fact", text=f"{dl_val}.", emphasis_level="strong", pause_after_ms=400, linked_fact_id=dl_fact.fact_id),
      ]
      s_spoken = " ".join(seg.text for seg in s_segments)
      scenes.append(
          SceneDefinition(
              scene_id=scene_idx, template_type=TemplateType.DEADLINE_ALERT,
              script_segments=s_segments, full_spoken_text=s_spoken,
              visual_hierarchy=VisualTextHierarchy(
                  badge_tag="DEADLINE ALERT", headline="Cutoff Date", subtext="Final date for compliance", highlight_metric=dl_val, highlight_sublabel="Deadline"
              ),
              asset=match_visual_asset(TemplateType.DEADLINE_ALERT, s_spoken, [FactCategory.DEADLINE])
          )
      )
      scene_idx += 1

  # 4. Outro CTA
  s_outro = [ScriptSegment(type="filler", text="For official status and updates, visit the government portal.", emphasis_level="none", pause_after_ms=300)]
  scenes.append(
      SceneDefinition(
          scene_id=scene_idx, template_type=TemplateType.OUTRO_CALL_TO_ACTION,
          script_segments=s_outro, full_spoken_text=s_outro[0].text,
          visual_hierarchy=VisualTextHierarchy(
              badge_tag="OFFICIAL PORTAL", headline="Verify Online", subtext="Stay updated with official sources", highlight_sublabel="National Helpdesk: 155261"
          ),
          asset=match_visual_asset(TemplateType.OUTRO_CALL_TO_ACTION, s_outro[0].text, [])
      )
  )

  return scenes