import pytest
from models.schemas import FactCategory
from services.fact_extractor import extract_facts_from_text, _normalize_date_str, _normalize_amount_str


def test_normalize_date_formats():
    assert _normalize_date_str("31-10-2026") == "31st October 2026"
    assert _normalize_date_str("01/11/2026") == "1st November 2026"
    assert _normalize_date_str("2026-12-15") == "15th December 2026"
    assert _normalize_date_str("30-11-2026") == "30th November 2026"


def test_normalize_amount_formats():
    assert _normalize_amount_str("Rs 2000") == "₹2,000"
    assert _normalize_amount_str("Rs. 12000") == "₹12,000"
    assert _normalize_amount_str("INR 500") == "₹500"
    assert _normalize_amount_str("₹25000") == "₹25,000"


def test_extract_pmkisan_notice():
    text = (
        "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000. "
        "Complete verification before 31-10-2026."
    )
    facts = extract_facts_from_text(text)
    assert len(facts) >= 4

    categories = {f.category: f for f in facts}
    assert FactCategory.AUTHORITY in categories
    assert "Agriculture" in categories[FactCategory.AUTHORITY].normalized_value

    assert FactCategory.SCHEME_NAME in categories
    assert "PM-KISAN" in categories[FactCategory.SCHEME_NAME].raw_value

    assert FactCategory.AMOUNT in categories
    assert categories[FactCategory.AMOUNT].normalized_value == "₹2,000"

    assert FactCategory.DEADLINE in categories
    assert categories[FactCategory.DEADLINE].normalized_value == "31st October 2026"


def test_extract_scholarship_notice():
    text = (
        "Ministry of Education: National Means-cum-Merit Scholarship disbursement of "
        "Rs 12000 per annum. Apply on NSP portal before 30-11-2026."
    )
    facts = extract_facts_from_text(text)
    categories = {f.category: f for f in facts}

    assert FactCategory.AUTHORITY in categories
    assert categories[FactCategory.AUTHORITY].raw_value == "Ministry of Education"

    assert FactCategory.AMOUNT in categories
    assert categories[FactCategory.AMOUNT].normalized_value == "₹12,000"

    assert FactCategory.DEADLINE in categories
    assert categories[FactCategory.DEADLINE].normalized_value == "30th November 2026"


def test_extract_char_provenance_offsets():
    text = "Ministry of Agriculture: PM-KISAN 17th installment of Rs 2000."
    facts = extract_facts_from_text(text)
    for fact in facts:
        assert fact.source_char_start >= 0
        assert fact.source_char_end > fact.source_char_start
        assert text[fact.source_char_start:fact.source_char_end] == fact.raw_value
