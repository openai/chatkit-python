"""
Tests for internationalization (i18n) and RTL support in ChatKit.
"""

import pytest

from chatkit.bidi import (
    RLE,
    RLM,
    TextSegment,
    clean_bidi_markers,
    fix_arabic_numbers_in_text,
    get_visual_length,
    normalize_mixed_text,
    split_mixed_direction_text,
    wrap_with_direction_markers,
)
from chatkit.i18n import (
    calculate_rtl_ratio,
    contains_arabic_characters,
    contains_hebrew_characters,
    contains_rtl_characters,
    detect_text_direction,
    get_language_direction,
    guess_language_from_text,
    is_mixed_direction_text,
    is_rtl_language,
)


class TestLanguageDetection:
    """Tests for language and direction detection."""

    def test_is_rtl_language_arabic(self):
        assert is_rtl_language("ar") is True
        assert is_rtl_language("ar-SA") is True
        assert is_rtl_language("ar_EG") is True

    def test_is_rtl_language_hebrew(self):
        assert is_rtl_language("he") is True
        assert is_rtl_language("iw") is True  # Old Hebrew code

    def test_is_rtl_language_persian(self):
        assert is_rtl_language("fa") is True

    def test_is_rtl_language_ltr(self):
        assert is_rtl_language("en") is False
        assert is_rtl_language("fr") is False
        assert is_rtl_language("de") is False

    def test_is_rtl_language_empty(self):
        assert is_rtl_language("") is False
        assert is_rtl_language(None) is False  # type: ignore

    def test_get_language_direction_rtl(self):
        assert get_language_direction("ar") == "rtl"
        assert get_language_direction("he") == "rtl"
        assert get_language_direction("fa") == "rtl"

    def test_get_language_direction_ltr(self):
        assert get_language_direction("en") == "ltr"
        assert get_language_direction("fr") == "ltr"


class TestCharacterDetection:
    """Tests for character-level RTL detection."""

    def test_contains_arabic_characters(self):
        assert contains_arabic_characters("مرحبا") is True
        assert contains_arabic_characters("Hello مرحبا") is True
        assert contains_arabic_characters("Hello") is False
        assert contains_arabic_characters("") is False

    def test_contains_hebrew_characters(self):
        assert contains_hebrew_characters("שלום") is True
        assert contains_hebrew_characters("Hello שלום") is True
        assert contains_hebrew_characters("Hello") is False

    def test_contains_rtl_characters(self):
        assert contains_rtl_characters("مرحبا") is True
        assert contains_rtl_characters("שלום") is True
        assert contains_rtl_characters("Hello") is False
        assert contains_rtl_characters("مرحبا Hello") is True

    def test_is_mixed_direction_text(self):
        assert is_mixed_direction_text("مرحبا Hello") is True
        assert is_mixed_direction_text("Hello مرحبا World") is True
        assert is_mixed_direction_text("مرحبا") is False
        assert is_mixed_direction_text("Hello") is False


class TestRTLRatioCalculation:
    """Tests for RTL character ratio calculation."""

    def test_calculate_rtl_ratio_pure_rtl(self):
        ratio = calculate_rtl_ratio("مرحبا بك")
        assert ratio == pytest.approx(1.0)

    def test_calculate_rtl_ratio_pure_ltr(self):
        ratio = calculate_rtl_ratio("Hello World")
        assert ratio == pytest.approx(0.0)

    def test_calculate_rtl_ratio_mixed(self):
        ratio = calculate_rtl_ratio("مرحبا Hello")
        assert 0.0 < ratio < 1.0

    def test_calculate_rtl_ratio_empty(self):
        assert calculate_rtl_ratio("") == 0.0

    def test_calculate_rtl_ratio_with_numbers(self):
        # Numbers should not affect RTL ratio
        ratio = calculate_rtl_ratio("مرحبا 123")
        assert ratio > 0.5  # Still predominantly RTL


class TestTextDirectionDetection:
    """Tests for automatic text direction detection."""

    def test_detect_text_direction_pure_arabic(self):
        assert detect_text_direction("مرحبا بك في ChatKit") == "rtl"

    def test_detect_text_direction_pure_hebrew(self):
        assert detect_text_direction("שלום עולם") == "rtl"

    def test_detect_text_direction_pure_english(self):
        assert detect_text_direction("Hello World") == "ltr"

    def test_detect_text_direction_mixed(self):
        result = detect_text_direction("مرحبا Hello العالم World")
        # Mixed text with more Arabic should return 'rtl' or 'auto'
        assert result in ["rtl", "auto"]

    def test_detect_text_direction_empty(self):
        assert detect_text_direction("") == "auto"

    def test_detect_text_direction_with_numbers(self):
        # Arabic with numbers
        assert detect_text_direction("عدد 123 شيء") == "rtl"


class TestLanguageGuessing:
    """Tests for language guessing from text."""

    def test_guess_language_arabic(self):
        assert guess_language_from_text("مرحبا") == "ar"

    def test_guess_language_hebrew(self):
        assert guess_language_from_text("שלום") == "he"

    def test_guess_language_english(self):
        # Cannot determine specific LTR language
        assert guess_language_from_text("Hello") is None

    def test_guess_language_empty(self):
        assert guess_language_from_text("") is None


class TestBidiMarkers:
    """Tests for Unicode bidirectional markers."""

    def test_wrap_with_direction_markers_rtl(self):
        result = wrap_with_direction_markers("مرحبا", "rtl")
        assert result.startswith(RLE)
        assert "مرحبا" in result

    def test_wrap_with_direction_markers_ltr(self):
        result = wrap_with_direction_markers("Hello", "ltr")
        assert "Hello" in result

    def test_wrap_with_direction_markers_empty(self):
        assert wrap_with_direction_markers("", "rtl") == ""

    def test_clean_bidi_markers(self):
        marked_text = wrap_with_direction_markers("Hello", "ltr")
        clean_text = clean_bidi_markers(marked_text)
        assert clean_text == "Hello"

    def test_get_visual_length(self):
        marked_text = wrap_with_direction_markers("مرحبا", "rtl")
        assert get_visual_length(marked_text) == len("مرحبا")


class TestArabicNumberHandling:
    """Tests for number handling in Arabic text."""

    def test_fix_arabic_numbers_simple(self):
        result = fix_arabic_numbers_in_text("عدد 123 شيء")
        # Numbers should be wrapped with LTR markers
        assert "123" in result
        assert result != "عدد 123 شيء"  # Should be different

    def test_fix_arabic_numbers_multiple(self):
        result = fix_arabic_numbers_in_text("من 10 إلى 20")
        assert "10" in result
        assert "20" in result

    def test_fix_arabic_numbers_decimals(self):
        result = fix_arabic_numbers_in_text("السعر 99.99 دولار")
        assert "99.99" in result

    def test_fix_arabic_numbers_no_numbers(self):
        text = "مرحبا بك"
        result = fix_arabic_numbers_in_text(text)
        # Text without numbers should remain unchanged
        assert clean_bidi_markers(result) == text


class TestMixedDirectionText:
    """Tests for mixed-direction text handling."""

    def test_split_mixed_direction_simple(self):
        segments = split_mixed_direction_text("Hello مرحبا World")
        assert len(segments) >= 2
        assert any(seg.direction == "rtl" for seg in segments)
        assert any(seg.direction == "ltr" for seg in segments)

    def test_split_mixed_direction_pure_rtl(self):
        segments = split_mixed_direction_text("مرحبا بك")
        assert len(segments) >= 1
        assert all(seg.direction == "rtl" for seg in segments)

    def test_split_mixed_direction_pure_ltr(self):
        segments = split_mixed_direction_text("Hello World")
        assert len(segments) >= 1
        assert all(seg.direction == "ltr" for seg in segments)

    def test_split_mixed_direction_empty(self):
        segments = split_mixed_direction_text("")
        assert segments == []

    def test_normalize_mixed_text(self):
        result = normalize_mixed_text("Hello مرحبا World")
        # Result should contain directional markers
        assert result != "Hello مرحبا World"
        # Visual content should be preserved
        clean = clean_bidi_markers(result)
        assert "Hello" in clean
        assert "مرحبا" in clean
        assert "World" in clean


class TestTextSegment:
    """Tests for TextSegment class."""

    def test_text_segment_creation(self):
        seg = TextSegment("مرحبا", "rtl", 0, 5)
        assert seg.text == "مرحبا"
        assert seg.direction == "rtl"
        assert seg.start_index == 0
        assert seg.end_index == 5

    def test_text_segment_equality(self):
        seg1 = TextSegment("مرحبا", "rtl", 0, 5)
        seg2 = TextSegment("مرحبا", "rtl", 0, 5)
        seg3 = TextSegment("Hello", "ltr", 0, 5)

        assert seg1 == seg2
        assert seg1 != seg3

    def test_text_segment_repr(self):
        seg = TextSegment("مرحبا", "rtl")
        repr_str = repr(seg)
        assert "مرحبا" in repr_str
        assert "rtl" in repr_str


class TestWidgetRTLSupport:
    """Tests for RTL support in widgets."""

    def test_text_widget_with_rtl(self):
        from chatkit.widgets import Text

        widget = Text(value="مرحبا", dir="rtl", lang="ar")
        assert widget.value == "مرحبا"
        assert widget.dir == "rtl"
        assert widget.lang == "ar"

    def test_text_widget_with_auto(self):
        from chatkit.widgets import Text

        widget = Text(value="مرحبا Hello", dir="auto")
        assert widget.dir == "auto"

    def test_markdown_widget_with_rtl(self):
        from chatkit.widgets import Markdown

        widget = Markdown(value="# مرحبا", dir="rtl", lang="ar")
        assert widget.dir == "rtl"
        assert widget.lang == "ar"

    def test_title_widget_with_rtl(self):
        from chatkit.widgets import Title

        widget = Title(value="عنوان", dir="rtl", lang="ar")
        assert widget.value == "عنوان"
        assert widget.dir == "rtl"

    def test_button_widget_with_rtl(self):
        from chatkit.widgets import Button

        widget = Button(label="إرسال", dir="rtl", lang="ar")
        assert widget.label == "إرسال"
        assert widget.dir == "rtl"

    def test_input_widget_with_rtl(self):
        from chatkit.widgets import Input

        widget = Input(name="name", placeholder="الاسم", dir="rtl", lang="ar")
        assert widget.dir == "rtl"
        assert widget.lang == "ar"

    def test_card_widget_with_rtl(self):
        from chatkit.widgets import Card, Text

        widget = Card(
            dir="rtl",
            lang="ar",
            children=[Text(value="محتوى", dir="rtl")],
        )
        assert widget.dir == "rtl"
        assert widget.lang == "ar"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_text_handling(self):
        assert detect_text_direction("") == "auto"
        assert calculate_rtl_ratio("") == 0.0
        assert split_mixed_direction_text("") == []

    def test_whitespace_only_text(self):
        assert detect_text_direction("   ") == "auto"

    def test_numbers_only_text(self):
        # Numbers are weak characters
        result = detect_text_direction("123 456")
        assert result == "ltr"

    def test_punctuation_only_text(self):
        result = detect_text_direction("!@#$%")
        assert result in ["ltr", "auto"]

    def test_very_long_text(self):
        long_arabic = "مرحبا " * 1000
        result = detect_text_direction(long_arabic)
        assert result == "rtl"

    def test_mixed_with_emojis(self):
        text = "مرحبا 😊 Hello"
        result = detect_text_direction(text)
        # Should still detect correctly despite emojis
        assert result in ["rtl", "auto"]


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_auto_detect_workflow_arabic(self):
        from chatkit.i18n import auto_detect_and_set_direction

        text = "مرحبا بك في ChatKit"
        normalized, direction, language = auto_detect_and_set_direction(text)

        assert direction == "rtl"
        assert language == "ar"
        assert "مرحبا" in normalized

    def test_auto_detect_workflow_mixed(self):
        from chatkit.i18n import auto_detect_and_set_direction

        text = "مرحبا Hello"
        normalized, direction, language = auto_detect_and_set_direction(text)

        # Mixed text can be detected as 'rtl' or 'auto' depending on ratio
        assert direction in ["rtl", "auto"]
        assert language == "ar"  # Arabic detected

    def test_widget_serialization_with_rtl(self):
        from chatkit.widgets import Text

        widget = Text(value="مرحبا", dir="rtl", lang="ar")
        data = widget.model_dump(exclude_none=True)

        assert "dir" in data
        assert data["dir"] == "rtl"
        assert data["lang"] == "ar"

    def test_widget_serialization_without_rtl(self):
        from chatkit.widgets import Text

        widget = Text(value="Hello")
        data = widget.model_dump(exclude_none=True)

        # dir and lang should not be in output if None
        assert "dir" not in data
        assert "lang" not in data
