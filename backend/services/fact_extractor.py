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


import json
import requests

def try_ollama_extraction(raw_text: str, source_lang: str = "en") -> List[ExtractedFact]:
    """Attempts to extract facts using local Ollama model."""
    OLLAMA_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "llama3.2:3b"
    
    prompt = f"""
    You are an expert data extractor. Extract ALL relevant information and key details from the following government notice text.
    Be EXTENSIVE and thorough. Do not limit the number of facts; extract every single entity you can find.
    The provided text is in the {source_lang} language. You must read it, extract the requested facts, and TRANSLATE all 'raw_value' and 'normalized_value' outputs into ENGLISH. The final JSON output MUST be entirely in English.
    Return ONLY a valid JSON array of objects. Do not include markdown formatting or explanations.
    Each object must have exactly these keys:
    "category": string (must be exactly one of: AUTHORITY, SCHEME_NAME, AMOUNT, DEADLINE, ACTION_REQUIRED, ELIGIBILITY, BENEFICIARY)
    "raw_value": string (translated to English)
    "normalized_value": string (a clean, readable version of the fact in English)
    
    Notice Text:
    {raw_text}
    """
    
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }, timeout=300)
        
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        response_text = data.get("response", "[]")
        parsed_facts = json.loads(response_text)
        
        facts = []
        fact_id_counter = 1
        
        for item in parsed_facts:
            if not isinstance(item, dict):
                continue
            cat_str = item.get("category", "")
            if cat_str not in FactCategory.__members__:
                continue
                
            raw_val = item.get("raw_value", "")
            norm_val = item.get("normalized_value", raw_val)
            
            # Find the substring in the text to get offsets (grounding)
            start_idx = raw_text.find(raw_val)
            if start_idx == -1:
                # If exact match fails, try case-insensitive
                start_idx_lower = raw_text.lower().find(raw_val.lower())
                if start_idx_lower != -1:
                    start_idx = start_idx_lower
                else:
                    start_idx = 0
            
            end_idx = start_idx + len(raw_val) if start_idx != -1 else 0
            
            facts.append(
                ExtractedFact(
                    fact_id=f"ollama_f{fact_id_counter}",
                    category=FactCategory[cat_str],
                    raw_value=raw_val if start_idx != -1 else raw_val,
                    normalized_value=norm_val,
                    source_page=1,
                    source_char_start=start_idx if start_idx != -1 else 0,
                    source_char_end=end_idx if start_idx != -1 else len(raw_val),
                    confidence_score=0.95,
                    is_verified=True,
                )
            )
            fact_id_counter += 1
            
        return facts
    except Exception as e:
        print(f"Ollama extraction failed: {e}")
        return []

class FactExtractor:
    """Grounded entity extraction and fact normalization interface."""

    def extract_facts(self, raw_text: str, source_lang: str = "en") -> List[ExtractedFact]:
        """Extracts facts from raw extracted notice text using local LLM or fallback."""
        if not raw_text or not raw_text.strip():
            return []
            
        print("Attempting fact extraction with local Ollama LLM (llama3.2:3b)...")
        llm_facts = try_ollama_extraction(raw_text, source_lang)
        
        if llm_facts and len(llm_facts) > 0:
            print(f"Successfully extracted {len(llm_facts)} facts using local LLM.")
            return llm_facts
            
        print("Local LLM extraction failed or returned zero facts. Falling back to Regex parser.")
        return extract_facts_from_text(raw_text)

