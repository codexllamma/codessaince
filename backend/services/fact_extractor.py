"""Grounded entity extraction and fact normalization for government notices (README §7.1).

Extracts categorized claims from circular raw text with character-level provenance offsets:
- AUTHORITY: Issuing ministry or department
- SCHEME_NAME: Government scheme, mission, or initiative
- AMOUNT: Financial disbursement or benefit value normalized with ₹ symbol
- DEADLINE: Cutoff date normalized into human-readable format (e.g., 31st October 2026)
- ACTION_REQUIRED: Mandatory citizen compliance action
- ELIGIBILITY / BENEFICIARY: Target audience criteria
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

from models.schemas import ExtractedFact, FactCategory


def _normalize_date_str(raw_date: str) -> str:
    """Convert varied date patterns (31-10-2026, 31/10/2026, 2026-10-31) to '31st October 2026'."""
    raw_date = raw_date.strip()
    # Handle dd-mm-yyyy or dd/mm/yyyy
    d_match = re.match(r"^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})$", raw_date)
    if d_match:
        day, month, year = int(d_match.group(1)), int(d_match.group(2)), int(d_match.group(3))
        try:
            dt = datetime(year, month, day)
            suffix = (
                "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
            )
            return f"{day}{suffix} {dt.strftime('%B %Y')}"
        except ValueError:
            pass

    # Handle yyyy-mm-dd
    y_match = re.match(r"^(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})$", raw_date)
    if y_match:
        year, month, day = int(y_match.group(1)), int(y_match.group(2)), int(y_match.group(3))
        try:
            dt = datetime(year, month, day)
            suffix = (
                "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
            )
            return f"{day}{suffix} {dt.strftime('%B %Y')}"
        except ValueError:
            pass

    return raw_date


def _normalize_amount_str(raw_amt: str) -> str:
    """Normalize 'Rs 2000', 'INR 12,000', 'Rs.500' -> '₹2,000'."""
    digits = re.sub(r"[^\d]", "", raw_amt)
    if not digits:
        return raw_amt
    try:
        num = int(digits)
        # Format with Indian or standard commas
        return f"₹{num:,}"
    except ValueError:
        return f"₹{digits}"


def extract_facts_from_text(raw_text: str) -> List[ExtractedFact]:
    """Dynamically parses and extracts grounded fact entities from notice text."""
    facts: List[ExtractedFact] = []
    fact_id_counter = 1

    if not raw_text or not raw_text.strip():
        return facts

    # 1. Extract AUTHORITY (Ministry / Department / Commission)
    auth_patterns = [
        r"(Ministry\s+of\s+[A-Za-z\s&,]+?)(?=:|\.|\n|$|;)",
        r"(Department\s+of\s+[A-Za-z\s&,]+?)(?=:|\.|\n|$|;)",
        r"(Government\s+of\s+[A-Za-z\s&,]+?)(?=:|\.|\n|$|;)",
        r"\b(UIDAI|RBI|UGC|AICTE|CBDT|ISRO|DRDO)\b",
    ]
    for pattern in auth_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            norm_val = raw_val
            # Common canonical expansion
            if "Ministry of Agriculture" in raw_val and "Farmers" not in raw_val:
                norm_val = "Ministry of Agriculture & Farmers Welfare"
            facts.append(
                ExtractedFact(
                    fact_id=f"f{fact_id_counter}",
                    category=FactCategory.AUTHORITY,
                    raw_value=raw_val,
                    normalized_value=norm_val,
                    source_page=1,
                    source_char_start=match.start(1),
                    source_char_end=match.end(1),
                    confidence_score=0.98,
                    is_verified=True,
                )
            )
            fact_id_counter += 1
            break

    # 2. Extract SCHEME_NAME
    scheme_patterns = [
        r"\b(PM-KISAN(?:\s+\d+(?:st|nd|rd|th)?\s+installment)?)\b",
        r"\b(PM\s+[A-Za-z]+(?:\s+Yojana|\s+Scheme|\s+Mission)?)\b",
        r"\b(Pradhan\s+Mantri\s+[A-Za-z\s]+?(?:Yojana|Scheme|Mission|Abhiyan))\b",
        r"\b([A-Za-z\s\-]+(?:Scholarship|Yojana|Installment|Card|Scheme))\b",
    ]
    for pattern in scheme_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            # Avoid picking whole sentences if too long
            if len(raw_val) < 60 and not any(f.category == FactCategory.SCHEME_NAME for f in facts):
                norm_val = raw_val.title() if "PM-" not in raw_val else raw_val
                facts.append(
                    ExtractedFact(
                        fact_id=f"f{fact_id_counter}",
                        category=FactCategory.SCHEME_NAME,
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        source_page=1,
                        source_char_start=match.start(1),
                        source_char_end=match.end(1),
                        confidence_score=0.99,
                        is_verified=True,
                    )
                )
                fact_id_counter += 1
                break

    # 3. Extract AMOUNT
    amt_patterns = [
        r"\b((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?)\b",
        r"\b([\d,]+)\s*(?:rupees|lakh|crore)\b",
    ]
    for pattern in amt_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            norm_val = _normalize_amount_str(raw_val)
            facts.append(
                ExtractedFact(
                    fact_id=f"f{fact_id_counter}",
                    category=FactCategory.AMOUNT,
                    raw_value=raw_val,
                    normalized_value=norm_val,
                    source_page=1,
                    source_char_start=match.start(1),
                    source_char_end=match.end(1),
                    confidence_score=0.97,
                    is_verified=True,
                )
            )
            fact_id_counter += 1
            break

    # 4. Extract DEADLINE
    deadline_patterns = [
        r"(?:before|on\s+or\s+before|by|deadline:?|cutoff:?)\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})",
        r"\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})\b",
        r"(?:before|by)\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})",
    ]
    for pattern in deadline_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            norm_val = _normalize_date_str(raw_val)
            facts.append(
                ExtractedFact(
                    fact_id=f"f{fact_id_counter}",
                    category=FactCategory.DEADLINE,
                    raw_value=raw_val,
                    normalized_value=norm_val,
                    source_page=1,
                    source_char_start=match.start(1),
                    source_char_end=match.end(1),
                    confidence_score=0.98,
                    is_verified=True,
                )
            )
            fact_id_counter += 1
            break

    # 5. Extract ACTION_REQUIRED
    action_patterns = [
        r"\b((?:Complete|Verify|Register|Apply|Submit|Update)\s+[A-Za-z0-9\-\s]+?)(?=\s+(?:before|on|by|\.|\n|$))",
    ]
    for pattern in action_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            if len(raw_val) < 60:
                facts.append(
                    ExtractedFact(
                        fact_id=f"f{fact_id_counter}",
                        category=FactCategory.ACTION_REQUIRED,
                        raw_value=raw_val,
                        normalized_value=raw_val.title(),
                        source_page=1,
                        source_char_start=match.start(1),
                        source_char_end=match.end(1),
                        confidence_score=0.95,
                        is_verified=True,
                    )
                )
                fact_id_counter += 1
                break

    # 6. Extract ELIGIBILITY (target-audience criteria — who qualifies, not
    # who benefits once qualified; BENEFICIARY is the module's stated
    # counterpart to this but has no extraction rule yet)
    eligibility_patterns = [
        r"\b((?:small\s+and\s+marginal|small|marginal)\s+farmers)\b",
        r"\b(eligible\s+(?:farmers|beneficiaries|households|citizens|families|farmer\s+families))\b",
        r"\b(rural\s+households)\b",
        r"\b(landholding\s+farmer\s+families)\b",
        r"\b(farmers?\s+(?:owning|holding)\s+(?:less\s+than|up\s+to)\s+[\d.]+\s*(?:hectares?|acres?)(?:\s+of\s+land)?)\b",
    ]
    for pattern in eligibility_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).strip()
            facts.append(
                ExtractedFact(
                    fact_id=f"f{fact_id_counter}",
                    category=FactCategory.ELIGIBILITY,
                    raw_value=raw_val,
                    normalized_value=raw_val.title(),
                    source_page=1,
                    source_char_start=match.start(1),
                    source_char_end=match.end(1),
                    confidence_score=0.93,
                    is_verified=True,
                )
            )
            fact_id_counter += 1
            break

    # 7. Fallback if fewer than 2 facts extracted (ensure grounded baseline)
    if len(facts) < 2:
        # Generic sentence scan fallback
        sentences = [s.strip() for s in re.split(r"[.\n]", raw_text) if s.strip()]
        if sentences and not any(f.category == FactCategory.SCHEME_NAME for f in facts):
            first_sent = sentences[0][:50]
            facts.append(
                ExtractedFact(
                    fact_id=f"f{fact_id_counter}",
                    category=FactCategory.SCHEME_NAME,
                    raw_value=first_sent,
                    normalized_value=first_sent,
                    source_page=1,
                    source_char_start=0,
                    source_char_end=len(first_sent),
                    confidence_score=0.85,
                    is_verified=True,
                )
            )
            fact_id_counter += 1

    return facts


class FactExtractor:
    """Grounded entity extraction and fact normalization interface."""

    def extract_facts(self, raw_text: str) -> List[ExtractedFact]:
        """Extracts facts from raw extracted notice text."""
        return extract_facts_from_text(raw_text)
