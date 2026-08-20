"""Visual font check: render one card per language and eyeball it for tofu.

Renders through the real compositor layer stack (compositor/layers.py), which
is what actually produces frames, so what you inspect here is what ships.
Fonts resolve via compositor/typography.py FONT_FILES against assets/fonts/.

Usage:  python test_font.py    ->  static/font_tests/test_card_<lang>.png
"""

from pathlib import Path

from compositor import layers
from models.schemas import (
    SceneDefinition,
    ScriptSegment,
    TemplateType,
    VisualAssetSelection,
    VisualTextHierarchy,
)

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
    "mr": {
        "badge": "अधिकृत सूचना",
        "headline": "पीएम-किसान १७वा हप्ता जाहीर",
        "subtext": "कृषी व शेतकरी कल्याण मंत्रालय",
        "metric": "₹2,000",
        "metric_sub": "थेट लाभ हस्तांतरण",
        "spoken": "कृषी मंत्रालयाची अधिकृत अधिसूचना: पात्र शेतकऱ्यांना ₹2,000 मिळतील.",
    },
    "bn": {
        "badge": "সরকারি বিজ্ঞপ্তি",
        "headline": "পিএম-কিসান ১৭তম কিস্তি",
        "subtext": "কৃষি ও কৃষক কল্যাণ মন্ত্রক",
        "metric": "₹2,000",
        "metric_sub": "সরাসরি সুবিধা স্থানান্তর",
        "spoken": "কৃষি মন্ত্রকের সরকারি বিজ্ঞপ্তি: যোগ্য কৃষকরা ₹2,000 পাবেন।",
    },
}


def build_card(lang: str, data: dict):
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
          asset_id=f"fonttest_{lang}",
          asset_type="mesh_gradient",
          file_path="",
          accent_color="#38BDF8",
      ),
  )

  canvas = (layers.VIDEO_WIDTH, layers.VIDEO_HEIGHT)
  frame = layers.build_background_source(scene.asset, *canvas)
  frame = frame.crop((0, 0, *canvas)).convert("RGBA")
  static_layers = layers.build_static_layers(scene, lang, canvas)
  for key in ("metric_card", "headline_subtext", "alert_pill"):
    if key in static_layers:
      frame.alpha_composite(static_layers[key])
  return frame.convert("RGB")


if __name__ == "__main__":
  for lang, data in test_cases.items():
    save_path = out_dir / f"test_card_{lang}.png"
    build_card(lang, data).save(save_path)
    print(f"[OK] Generated: {save_path}")

  print("\n[SUCCESS] Open 'static/font_tests/' to inspect the rendered text.")
