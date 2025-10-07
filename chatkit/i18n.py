from __future__ import annotations

import re
from typing import Literal

# RTL language codes (ISO 639-1)
RTL_LANGUAGES = {
    "ar",  # Arabic
    "he",  # Hebrew
    "fa",  # Persian (Farsi)
    "ur",  # Urdu
    "yi",  # Yiddish
    "arc",  # Aramaic
    "ckb",  # Sorani Kurdish
    "dv",  # Dhivehi
    "iw",  # Hebrew (old code)
    "ji",  # Yiddish (old code)
    "ps",  # Pashto
    "sd",  # Sindhi
}

# Unicode ranges for RTL scripts
ARABIC_RANGE = r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
HEBREW_RANGE = r"[\u0590-\u05FF]"
RTL_RANGE = (
    r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# Compiled regex patterns for performance
ARABIC_PATTERN = re.compile(ARABIC_RANGE)
HEBREW_PATTERN = re.compile(HEBREW_RANGE)
RTL_PATTERN = re.compile(RTL_RANGE)


def is_rtl_language(lang_code: str) -> bool:
    """
    Check if a language code represents an RTL language.

    Args:
        lang_code: ISO 639-1 language code (e.g., 'ar', 'he', 'en')

    Returns:
        True if the language is RTL, False otherwise

    """
    if not lang_code:
        return False
    # Extract base language code (e.g., 'ar' from 'ar-SA')
    base_code = lang_code.lower().split("-")[0].split("_")[0]
    return base_code in RTL_LANGUAGES


def get_language_direction(lang_code: str) -> Literal["ltr", "rtl"]:
    """
    Get the text direction for a given language code.

    Args:
        lang_code: ISO 639-1 language code

    Returns:
        'rtl' for RTL languages, 'ltr' for LTR languages

    """
    return "rtl" if is_rtl_language(lang_code) else "ltr"


def contains_rtl_characters(text: str) -> bool:
    """
    Check if the text contains any RTL characters.

    Args:
        text: Text to analyze

    Returns:
        True if text contains RTL characters, False otherwise

    """
    if not text:
        return False
    return bool(RTL_PATTERN.search(text))


def contains_arabic_characters(text: str) -> bool:
    """
    Check if the text contains Arabic characters.

    Args:
        text: Text to analyze

    Returns:
        True if text contains Arabic characters, False otherwise
    """
    if not text:
        return False
    return bool(ARABIC_PATTERN.search(text))


def contains_hebrew_characters(text: str) -> bool:
    """
    Check if the text contains Hebrew characters.

    """
    if not text:
        return False
    return bool(HEBREW_PATTERN.search(text))


def calculate_rtl_ratio(text: str, sample_size: int = 100) -> float:
    """
    Calculate the ratio of RTL characters in the text.
    
    """
    if not text:
        return 0.0

    # Sample the beginning of the text for performance
    sample = text[:sample_size]

    # Remove whitespace and punctuation for accurate counting
    chars = [c for c in sample if c.strip() and c.isalnum()]

    if not chars:
        return 0.0

    rtl_count = sum(1 for c in chars if RTL_PATTERN.match(c))
    return rtl_count / len(chars)


def detect_text_direction(
    text: str, threshold_rtl: float = 0.3, threshold_ltr: float = 0.1
) -> Literal["ltr", "rtl", "auto"]:
    """
    Automatically detect the text direction based on content.

    The function analyzes the text and determines if it's primarily RTL, LTR,
    or mixed (auto). The detection is based on the ratio of RTL characters.

    Args:
        text: Text to analyze
        threshold_rtl: Minimum ratio of RTL chars to classify as RTL (default: 0.3)
        threshold_ltr: Maximum ratio of RTL chars to classify as LTR (default: 0.1)

    Returns:
        'rtl' if text is primarily RTL
        'ltr' if text is primarily LTR
        'auto' if text is mixed or uncertain

    """
    if not text or not text.strip():
        return "auto"

    rtl_ratio = calculate_rtl_ratio(text)

    if rtl_ratio >= threshold_rtl:
        return "rtl"
    elif rtl_ratio <= threshold_ltr:
        return "ltr"
    else:
        return "auto"


def guess_language_from_text(text: str) -> str | None:
    """
    Attempt to guess the language from text content.

    This is a simple heuristic based on script detection.
    For more accurate detection, consider using external libraries.

    Args:
        text: Text to analyze

    Returns:
        Language code if detected, None otherwise

    """
    if not text:
        return None

    if contains_arabic_characters(text):
        return "ar"
    elif contains_hebrew_characters(text):
        return "he"

    # For other RTL languages or LTR languages, we cannot determine accurately
    # without more sophisticated language detection
    return None


def is_mixed_direction_text(text: str) -> bool:
    """
    Check if text contains both RTL and LTR characters.

    Args:
        text: Text to analyze

    Returns:
        True if text contains both RTL and LTR characters

    """
    if not text:
        return False

    has_rtl = contains_rtl_characters(text)
    # Check for basic Latin characters as LTR indicator
    has_ltr = bool(re.search(r"[a-zA-Z]", text))

    return has_rtl and has_ltr


def normalize_text_direction(text: str, force_direction: str | None = None) -> str:
   
    if not text:
        return text

    # Import bidi utilities
    from .bidi import wrap_with_direction_markers

    if force_direction:
        return wrap_with_direction_markers(text, force_direction)

    # Auto-detect and normalize
    direction = detect_text_direction(text)
    if direction != "auto":
        return wrap_with_direction_markers(text, direction)

    return text


# Convenience functions for common use cases
def auto_detect_and_set_direction(
    text: str,
) -> tuple[str, Literal["ltr", "rtl", "auto"], str | None]:
    """
    Automatically detect text direction and guess language.

    This is a convenience function that combines direction detection
    and language guessing.

    Args:
        text: Text to analyze

    Returns:
        Tuple of (normalized_text, direction, language_code)

    Examples:
        >>> auto_detect_and_set_direction('مرحبا')
        ('مرحبا', 'rtl', 'ar')
        >>> auto_detect_and_set_direction('Hello')
        ('Hello', 'ltr', None)
    """
    direction = detect_text_direction(text)
    language = guess_language_from_text(text)
    normalized = normalize_text_direction(text, direction if direction != "auto" else None)

    return normalized, direction, language
