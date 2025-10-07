"""
Bidirectional text (bidi) utilities for ChatKit.

This module provides utilities for handling Unicode Bidirectional Algorithm
and mixed-direction text, which is essential for proper RTL support.
"""

from __future__ import annotations

import re
from typing import Literal, cast

# Unicode Bidirectional Formatting Characters
RLM = "\u200F"  # Right-to-Left Mark
LRM = "\u200E"  # Left-to-Right Mark
RLE = "\u202B"  # Right-to-Left Embedding
LRE = "\u202A"  # Left-to-Right Embedding
PDF = "\u202C"  # Pop Directional Formatting
RLO = "\u202E"  # Right-to-Left Override
LRO = "\u202D"  # Left-to-Right Override

# Unicode line separator
ALM = "\u061C"  # Arabic Letter Mark


class TextSegment:
    """
    Represents a segment of text with a specific direction.

    Attributes:
        text: The text content
        direction: The text direction ('ltr' or 'rtl')
        start_index: Starting position in the original text
        end_index: Ending position in the original text
    """

    def __init__(
        self,
        text: str,
        direction: Literal["ltr", "rtl"],
        start_index: int = 0,
        end_index: int | None = None,
    ):
        self.text = text
        self.direction = direction
        self.start_index = start_index
        self.end_index = end_index or len(text)

    def __repr__(self) -> str:
        return f"TextSegment(text={self.text!r}, direction={self.direction!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TextSegment):
            return False
        return (
            self.text == other.text
            and self.direction == other.direction
            and self.start_index == other.start_index
            and self.end_index == other.end_index
        )


def wrap_with_direction_markers(
    text: str, direction: Literal["ltr", "rtl"]
) -> str:
    """
    Wrap text with Unicode directional markers.

    This ensures the text is rendered in the correct direction
    regardless of the surrounding context.

    Args:
        text: Text to wrap
        direction: Desired direction ('ltr' or 'rtl')

    Returns:
        Text wrapped with appropriate Unicode markers

    Examples:
        >>> wrap_with_direction_markers('Hello', 'ltr')
        '\\u202aHello\\u202c'
        >>> wrap_with_direction_markers('مرحبا', 'rtl')
        '\\u202bمرحبا\\u202c'
    """
    if not text:
        return text

    if direction == "rtl":
        return f"{RLE}{text}{PDF}"
    else:
        return f"{LRE}{text}{PDF}"


def add_direction_mark(text: str, direction: Literal["ltr", "rtl"]) -> str:
    """
    Add a directional mark to the end of text.

    This is useful for inline text that needs directional hints.

    Args:
        text: Text to mark
        direction: Desired direction

    Returns:
        Text with directional mark appended
    """
    if not text:
        return text

    mark = RLM if direction == "rtl" else LRM
    return f"{text}{mark}"


def isolate_rtl_text(text: str) -> str:
    """
    Isolate RTL text to prevent it from affecting surrounding LTR text.

    This is particularly useful when RTL text is embedded in LTR context.

    Args:
        text: RTL text to isolate

    Returns:
        Isolated text with appropriate markers
    """
    if not text:
        return text

    return f"{RLM}{text}{RLM}"


def fix_arabic_numbers_in_text(text: str) -> str:
    """
    Fix the display of numbers in Arabic text.

    Numbers in RTL text should be displayed LTR, but they need
    proper markers to render correctly.

    Args:
        text: Text containing numbers

    Returns:
        Text with properly marked numbers

    Examples:
        >>> fix_arabic_numbers_in_text('عدد 123 شيء')
        'عدد \\u202a123\\u202c شيء'
    """
    if not text:
        return text

    # Find all numbers in the text
    def replace_number(match):
        number = match.group(0)
        # Wrap number with LTR embedding
        return f"{LRE}{number}{PDF}"

    # Pattern to match numbers (including decimals and separators)
    number_pattern = r"\d+(?:[.,]\d+)*"
    return re.sub(number_pattern, replace_number, text)


def split_mixed_direction_text(text: str) -> list[TextSegment]:
    """
    Split text into segments based on direction changes.

    This is useful for processing mixed-direction text segment by segment.

    Args:
        text: Text to split

    Returns:
        List of TextSegment objects

    Examples:
        >>> segments = split_mixed_direction_text('Hello مرحبا World')
        >>> len(segments)
        3
        >>> segments[1].direction
        'rtl'
    """
    if not text:
        return []

    from .i18n import RTL_PATTERN

    segments = []
    current_pos = 0
    current_direction = None
    segment_start = 0

    for i, char in enumerate(text):
        if char.isspace():
            continue

        # Determine character direction
        is_rtl = bool(RTL_PATTERN.match(char))
        char_direction = "rtl" if is_rtl else "ltr"

        # If direction changes, create a new segment
        if current_direction is None:
            current_direction = char_direction
            segment_start = i
        elif current_direction != char_direction:
            # Save the previous segment
            segment_text = text[segment_start:i].strip()
            if segment_text:
                segments.append(
                    TextSegment(
                        segment_text, current_direction, segment_start, i
                    )
                )
            # Start new segment
            current_direction = char_direction
            segment_start = i

    # Add the last segment
    if current_direction is not None:
        segment_text = text[segment_start:].strip()
        if segment_text:
            segments.append(
                TextSegment(segment_text, current_direction, segment_start, len(text))
            )

    return segments


def normalize_mixed_text(text: str) -> str:
    """
    Normalize mixed-direction text for proper display.

    This function splits the text into directional segments
    and wraps each with appropriate markers.

    Args:
        text: Mixed-direction text

    Returns:
        Normalized text with proper directional markers

    Examples:
        >>> normalize_mixed_text('Hello مرحبا World')
        '\\u202aHello\\u202c \\u202bمرحبا\\u202c \\u202aWorld\\u202c'
    """
    if not text:
        return text

    segments = split_mixed_direction_text(text)

    if not segments:
        return text

    # If only one segment, wrap it
    if len(segments) == 1:
        seg_dir = cast(Literal["ltr", "rtl"], segments[0].direction)
        return wrap_with_direction_markers(text, seg_dir)

    # Multiple segments - normalize each
    result_parts = []
    last_end = 0

    for segment in segments:
        # Add any whitespace between segments
        if segment.start_index > last_end:
            result_parts.append(text[last_end : segment.start_index])

        # Add wrapped segment
        seg_direction = cast(Literal["ltr", "rtl"], segment.direction)
        result_parts.append(
            wrap_with_direction_markers(segment.text, seg_direction)
        )
        last_end = segment.end_index

    # Add any trailing whitespace
    if last_end < len(text):
        result_parts.append(text[last_end:])

    return "".join(result_parts)


def prepare_rtl_text_for_streaming(text: str) -> str:
    """
    Prepare RTL text for streaming display.

    When streaming RTL text character by character, it's important
    to maintain proper directionality throughout.

    Args:
        text: RTL text to prepare

    Returns:
        Text prepared for streaming
    """
    if not text:
        return text

    # Add RLM at the start to establish RTL context
    return f"{RLM}{text}"


def clean_bidi_markers(text: str) -> str:
    """
    Remove all Unicode bidirectional markers from text.

    This is useful for getting the plain text content
    without formatting characters.

    Args:
        text: Text with bidi markers

    Returns:
        Clean text without markers

    Examples:
        >>> clean_bidi_markers('\\u202aHello\\u202c')
        'Hello'
    """
    if not text:
        return text

    # Remove all bidi control characters
    bidi_chars = [RLM, LRM, RLE, LRE, PDF, RLO, LRO, ALM]
    result = text
    for char in bidi_chars:
        result = result.replace(char, "")

    return result


def ensure_rtl_punctuation(text: str) -> str:
    """
    Ensure punctuation in RTL text is properly positioned.

    In RTL text, punctuation marks should be mirrored or positioned
    correctly according to the RTL context.

    Args:
        text: RTL text

    Returns:
        Text with properly positioned punctuation
    """
    if not text:
        return text

    # Map of LTR punctuation to RTL equivalents where applicable
    punctuation_map = {
        "(": ")",
        ")": "(",
        "[": "]",
        "]": "[",
        "{": "}",
        "}": "{",
        "<": ">",
        ">": "<",
    }

    result = []
    for char in text:
        if char in punctuation_map:
            result.append(punctuation_map[char])
        else:
            result.append(char)

    return "".join(result)


def get_visual_length(text: str) -> int:
    """
    Get the visual length of text (excluding bidi markers).

    Args:
        text: Text to measure

    Returns:
        Visual length (number of visible characters)
    """
    return len(clean_bidi_markers(text))


def is_weak_character(char: str) -> bool:
    """
    Check if a character is weak in bidirectional context.

    Weak characters include numbers, punctuation, and whitespace.

    Args:
        char: Character to check

    Returns:
        True if character is weak
    """
    return not char.isalpha() or char.isspace()


def wrap_rtl_text_safely(text: str) -> str:
    """
    Safely wrap RTL text with directional markers.

    This function handles edge cases like numbers and mixed content.

    Args:
        text: RTL text to wrap

    Returns:
        Safely wrapped text
    """
    if not text:
        return text

    # First fix numbers
    text_with_fixed_numbers = fix_arabic_numbers_in_text(text)

    # Then wrap the whole text
    return wrap_with_direction_markers(text_with_fixed_numbers, "rtl")
