import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.fact_extractor import extract_facts_from_text

sample_notices = [
    "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000. Complete verification before 31-10-2026.",
    "Ministry of Education: National Means-cum-Merit Scholarship disbursement of Rs 12000 per annum. Apply on NSP portal before 30-11-2026.",
    "Ministry of Agriculture: Distribution of Soil Health Cards with testing subsidy of Rs 500 per sample before 15-12-2026.",
]

for i, notice in enumerate(sample_notices, 1):
    print(f"\n--- Notice #{i} ---")
    print(f"Text: {notice}")
    facts = extract_facts_from_text(notice)
    print(f"Extracted ({len(facts)} facts):")
    for f in facts:
        print(f"  • [{f.category.value}]: raw=\"{f.raw_value}\" -> norm=\"{f.normalized_value}\" (chars {f.source_char_start}..{f.source_char_end})")
