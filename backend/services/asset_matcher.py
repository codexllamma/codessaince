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
    selection = VisualAssetSelection(
        asset_id=best_match["asset_id"],
        asset_type=best_match["asset_type"],
        file_path=best_match["file_path"],
        accent_color=best_match.get("accent_color", "#38BDF8"),
        dim_overlay_opacity=0.65,
    )
    return _prefer_library_image(selection, template_type, scene_text, categories)

  return _prefer_library_image(DEFAULT_ASSET, template_type, scene_text, categories)


def _prefer_library_image(
    selection: VisualAssetSelection,
    template_type: TemplateType,
    scene_text: str,
    categories: Optional[List[FactCategory]] = None,
) -> VisualAssetSelection:
  """Swap in a still from the local image library when the catalogue clip
  is not on disk.

  A curated clip in assets/broll/ always wins: it was chosen deliberately and
  vetted, whereas a library pick is whatever scripts/build_image_library.py
  seeded from Wikimedia Commons. But the catalogue currently points at four
  clips that do not exist, so without this every scene falls back to the
  gradient. A library still is a better floor than a gradient and a worse
  ceiling than real B-roll, which is exactly where it belongs in the order.

  This is a pure local lookup — no network, no key, no quota — replacing an
  earlier live-search design (services/image_fetcher.py) that needed a Google
  Cloud project with the Custom Search API enabled. That module is left in
  place and fully tested in case it is worth revisiting later, but nothing
  here calls it.

  Returns `selection` unchanged whenever the relevant category has no images
  yet — expected for categories build_image_library.py has not populated or
  a human hasn't finished reviewing — so an empty library behaves exactly
  like no library at all.
  """
  from services import image_library

  if selection.asset_type != "mesh_gradient":
    if (Path(__file__).resolve().parent.parent / selection.file_path).is_file():
      return selection  # the curated clip really is there; use it

  # `categories` is an ordered preference — scene_generator passes it as
  # priority-ordered by how central that fact is to the scene, real facts
  # only (a fallback display string like "Ministry of Agriculture" for a
  # scene with no AUTHORITY fact does not get to steer image selection).
  # The template default is appended last so a scene with no categories at
  # all — or one whose facts have empty pools — still gets a reasonable try
  # before giving up to the gradient.
  ordered = [c.value for c in categories] if categories else []
  template_default = _CATEGORY_FOR_TEMPLATE.get(template_type, "")
  if template_default and template_default not in ordered:
    ordered.append(template_default)

  try:
    for category in ordered:
      image = image_library.select_image(category, scene_text=scene_text, seed=scene_text)
      if image is not None:
        return VisualAssetSelection(
            asset_id=f"library_{image.path.stem}",
            asset_type="static_graphic",
            file_path=str(image.path.relative_to(Path(__file__).resolve().parent.parent)).replace("\\", "/"),
            accent_color=selection.accent_color,
            dim_overlay_opacity=0.65,
        )
  except Exception:  # never let asset selection break scene generation
    return selection

  return selection


# Used when a scene carries no facts of its own to key off.
_CATEGORY_FOR_TEMPLATE = {
    TemplateType.HERO_ANNOUNCEMENT: "SCHEME_NAME",
    TemplateType.METRIC_FOCUS: "AMOUNT",
    TemplateType.DEADLINE_ALERT: "DEADLINE",
    TemplateType.OUTRO_CALL_TO_ACTION: "ACTION_REQUIRED",
}