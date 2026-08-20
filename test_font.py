from pathlib import Path
import numpy as np
from PIL import Image

from models.schemas import (
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
)
from services.video_renderer import render_scene_card_image

out_dir = Path("static/font_tests")
out_dir.mkdir(parents=True, exist_ok=True)

test_cases = {
    "en": {
        "badge": "OFFICIAL NOTICE",
        "headline": "PM-KISAN 17th Installment",
        "subtext": "Ministry of Agriculture & Farmers Welfare",
        "metric": "₹2,000",
        "metric_sub": "Direct Benefit Transfer",
        "spoken": (
            "Official announcement: PM-KISAN installment will be credited"
            " directly."
        ),
    },
    "hi": {
        "badge": "आधिकारिक सूचना",
        "headline": "पीएम-किसान 17वीं किस्त जारी",
        "subtext": "कृषि एवं किसान कल्याण मंत्रालय",
        "metric": "₹2,000",
        "metric_sub": "प्रत्यक्ष लाभ अंतरण",
        "spoken": (
            "कृषि मंत्रालय की आधिकारिक अधिसूचना: पात्र किसानों को ₹2,000 भेजे"
            " जाएंगे।"
        ),
    },
    "ta": {
        "badge": "அதிகாரப்பூர்வ அறிவிப்பு",
        "headline": "பிஎம்-கிசான் 17வது தவணை",
        "subtext": "வேளாண்மை மற்றும் விவசாயிகள் நல அமைச்சகம்",
        "metric": "₹2,000",
        "metric_sub": "நேரடி வங்கி பரிமாற்றம்",
        "spoken": (
            "வேளாண்மை அமைச்சகத்தின் அதிகாரப்பூர்வ அறிவிப்பு: ₹2,000 நேரடியாக"
            " கணக்கில் வரவு வைக்கப்படும்."
        ),
    },
    "te": {
        "badge": "అధికారిక ప్రకటన",
        "headline": "పీఎం-కిసాన్ 17వ విడత",
        "subtext": "వ్యవసాయ మరియు రైతు సంక్షేమ మంత్రిత్వ శాఖ",
        "metric": "₹2,000",
        "metric_sub": "ప్రత్యక్ష ప్రయోజన బదిలీ",
        "spoken": (
            "అధికారిక ప్రకటన: అర్హులైన రైతులకు ₹2,000 వారి ఖాతాల్లో జమ"
            " చేయబడతాయి."
        ),
    },
}

for lang, data in test_cases.items():
  scene = SceneDefinition(
      scene_id=1,
      template_type=TemplateType.METRIC_FOCUS,
      script_segments=[ScriptSegment(type="filler", text=data["spoken"])],
      full_spoken_text=data["spoken"],
      visual_hierarchy=VisualTextHierarchy(
          badge_tag=data["badge"],
          headline=data["headline"],
          subtext=data["subtext"],
          highlight_metric=data["metric"],
          highlight_sublabel=data["metric_sub"],
      ),
      asset=VisualAssetSelection(
          asset_id="test", asset_type="static_graphic", file_path=""
      ),
  )

  img_array = render_scene_card_image(scene, lang=lang)
  save_path = out_dir / f"test_card_{lang}.png"
  Image.fromarray(img_array).save(save_path)
  print(f"[OK] Generated: {save_path}")

print("\n[SUCCESS] Open 'static/font_tests/' to inspect the rendered text.")