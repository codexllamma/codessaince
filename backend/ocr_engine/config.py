"""
Configuration for PaddleOCR engine and PDF rasterization.
"""

# Supported language codes mapped to PaddleOCR model identifiers
SUPPORTED_LANGUAGES = {
    "en": "en",       # English
    "hi": "hi",       # Hindi
    "ta": "ta",       # Tamil
    "te": "te",       # Telugu
    "mr": "mr",       # Marathi
    "bn": "bn",       # Bengali
    "gu": "gu",       # Gujarati
    "kn": "kn",       # Kannada
    "ml": "ml",       # Malayalam
}

DEFAULT_CONFIG = {
    "default_lang": "en",
    "use_gpu": True,
    "use_angle_cls": True,       # Correct inverted or rotated text
    "dpi": 300,                  # Optimal balance between quality and inference speed
    "min_confidence": 0.50,      # Filter out low-confidence hallucinations
    "sort_reading_order": True,  # Sort blocks top-to-bottom, left-to-right
}