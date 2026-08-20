from pathlib import Path
from typing import Dict, List, Optional
from models.schemas import FactCategory, TemplateType, VisualAssetSelection

ASSET_CATALOG = [
    {
        "asset_id": "broll_agri_wheat_01",
        "asset_type": "video_loop",
        "file_path": "assets/broll/agriculture_wheat_01.mp4",
        "accent_color": "#10B981",  # Vibrant Emerald
        "tags": ["agriculture", "farmer", "crop", "kisan", "wheat", "rural"],
        "template_affinity": [TemplateType.HERO_ANNOUNCEMENT],
    },
    {
        "asset_id": "broll_finance_rupee_01",
        "asset_type": "video_loop",
        "file_path": "assets/broll/banking_digital_rupee.mp4",
        "accent_color": "#06B6D4",  # Electric Cyan
        "tags": ["amount", "disbursement", "bank", "rupee", "payment", "dbt", "thousand", "crore"],
        "template_affinity": [TemplateType.METRIC_FOCUS],
    },
    {
        "asset_id": "broll_alert_calendar_01",
        "asset_type": "video_loop",
        "file_path": "assets/broll/deadline_calendar_loop.mp4",
        "accent_color": "#F43F5E",  # Coral Rose Alert
        "tags": ["deadline", "cutoff", "last date", "urgent", "ekyc", "october", "verification", "before"],
        "template_affinity": [TemplateType.DEADLINE_ALERT],
    },
    {
        "asset_id": "broll_gov_emblem_01",
        "asset_type": "video_loop",
        "file_path": "assets/broll/government_portal_loop.mp4",
        "accent_color": "#FF9933",  # National Saffron
        "tags": ["portal", "helpdesk", "official", "grievance", "verification", "pmkisan.gov.in"],
        "template_affinity": [TemplateType.OUTRO_CALL_TO_ACTION],
    },
]

DEFAULT_ASSET = VisualAssetSelection(
    asset_id="mesh_gradient_navy",
    asset_type="mesh_gradient",
    file_path="assets/broll/mesh_dark_blue.png",
    accent_color="#38BDF8",
    dim_overlay_opacity=0.65,
)


def match_visual_asset(
    template_type: TemplateType,
    scene_text: str,
    categories: Optional[List[FactCategory]] = None,
) -> VisualAssetSelection:
  search_corpus = scene_text.lower()
  best_match = None
  highest_score = -1

  for entry in ASSET_CATALOG:
    score = 0
    if template_type in entry["template_affinity"]:
      score += 3

    for tag in entry["tags"]:
      if tag in search_corpus:
        score += 2

    if score > highest_score:
      highest_score = score
      best_match = entry

  if best_match and highest_score > 0:
    return VisualAssetSelection(
        asset_id=best_match["asset_id"],
        asset_type=best_match["asset_type"],
        file_path=best_match["file_path"],
        accent_color=best_match.get("accent_color", "#38BDF8"),
        dim_overlay_opacity=0.65,
    )

  return DEFAULT_ASSET