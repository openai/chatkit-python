"""
ChatKit RTL (Right-to-Left) Support Example.

This example demonstrates how to use ChatKit with RTL languages like Arabic,
including automatic direction detection, mixed-direction text, and proper
widget configuration.
"""

from chatkit.i18n import auto_detect_and_set_direction, detect_text_direction
from chatkit.widgets import (
    Button,
    Card,
    Caption,
    Col,
    Input,
    Label,
    Markdown,
    Row,
    Text,
    Textarea,
    Title,
)


def example_basic_rtl_text():
    """Example 1: Basic RTL text widget."""
    print("=" * 60)
    print("Example 1: Basic RTL Text")
    print("=" * 60)

    # Arabic text with explicit RTL direction
    arabic_text = Text(
        value="مرحباً بك في ChatKit!",
        dir="rtl",
        lang="ar",
        size="lg",
    )

    print(f"Text value: {arabic_text.value}")
    print(f"Direction: {arabic_text.dir}")
    print(f"Language: {arabic_text.lang}")
    print(f"JSON: {arabic_text.model_dump_json(exclude_none=True, indent=2)}")
    print()


def example_auto_detection():
    """Example 2: Automatic direction detection."""
    print("=" * 60)
    print("Example 2: Auto Direction Detection")
    print("=" * 60)

    texts = [
        "مرحباً بك في ChatKit",  # Arabic
        "Hello World",  # English
        "مرحبا Hello العالم World",  # Mixed
    ]

    for text in texts:
        direction = detect_text_direction(text)
        normalized, detected_dir, lang = auto_detect_and_set_direction(text)

        print(f"Text: {text}")
        print(f"Detected direction: {direction}")
        print(f"Detected language: {lang}")
        print(f"Normalized: {repr(normalized[:50])}...")
        print("-" * 40)

    print()


def example_rtl_card():
    """Example 3: Complete RTL card with multiple widgets."""
    print("=" * 60)
    print("Example 3: RTL Card with Multiple Widgets")
    print("=" * 60)

    card = Card(
        dir="rtl",
        lang="ar",
        size="md",
        children=[
            Title(
                value="نموذج تسجيل الدخول",
                dir="rtl",
                size="2xl",
            ),
            Caption(
                value="الرجاء إدخال بيانات الدخول الخاصة بك",
                dir="rtl",
                color="secondary",
            ),
            Col(
                gap=4,
                children=[
                    Label(
                        value="البريد الإلكتروني",
                        fieldName="email",
                        dir="rtl",
                    ),
                    Input(
                        name="email",
                        placeholder="أدخل بريدك الإلكتروني",
                        dir="rtl",
                        lang="ar",
                        inputType="email",
                        required=True,
                    ),
                    Label(
                        value="كلمة المرور",
                        fieldName="password",
                        dir="rtl",
                    ),
                    Input(
                        name="password",
                        placeholder="أدخل كلمة المرور",
                        dir="rtl",
                        lang="ar",
                        inputType="password",
                        required=True,
                    ),
                    Row(
                        gap=2,
                        justify="end",
                        children=[
                            Button(
                                label="إلغاء",
                                dir="rtl",
                                variant="outline",
                            ),
                            Button(
                                label="تسجيل الدخول",
                                dir="rtl",
                                variant="solid",
                                style="primary",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    print("RTL Login Card created successfully!")
    print(f"Card direction: {card.dir}")
    print(f"Card language: {card.lang}")
    print(f"Number of children: {len(card.children)}")
    print()


def example_mixed_content():
    """Example 4: Mixed Arabic and English content."""
    print("=" * 60)
    print("Example 4: Mixed Direction Content")
    print("=" * 60)

    # Card with mixed content
    card = Card(
        dir="auto",  # Auto-detect based on content
        children=[
            Title(
                value="ChatKit Features / مميزات ChatKit",
                dir="auto",
            ),
            Col(
                gap=3,
                children=[
                    Text(
                        value="✅ دعم كامل للغة العربية - Full Arabic Support",
                        dir="auto",
                    ),
                    Text(
                        value="✅ كشف تلقائي للاتجاه - Automatic Direction Detection",
                        dir="auto",
                    ),
                    Text(
                        value="✅ نصوص مختلطة - Mixed Text Support",
                        dir="auto",
                    ),
                ],
            ),
        ],
    )

    print("Mixed Content Card created successfully!")
    print(f"Card has {len(card.children)} children")
    print()


def example_markdown_rtl():
    """Example 5: RTL Markdown content."""
    print("=" * 60)
    print("Example 5: RTL Markdown")
    print("=" * 60)

    markdown_content = """
# مرحباً بك في ChatKit

## المميزات الرئيسية

- دعم كامل للغة العربية
- واجهة سهلة الاستخدام
- أداء عالي وسريع

### مثال على الكود

```python
text = Text(value="مرحبا", dir="rtl", lang="ar")
```

### الأرقام والتواريخ

اليوم هو 2025/10/7 والساعة 12:30
    """

    markdown = Markdown(
        value=markdown_content,
        dir="rtl",
        lang="ar",
    )

    print("Markdown widget created!")
    print(f"Direction: {markdown.dir}")
    print(f"Language: {markdown.lang}")
    print(f"Content length: {len(markdown.value)} characters")
    print()


def example_form_rtl():
    """Example 6: Complete RTL form."""
    print("=" * 60)
    print("Example 6: Complete RTL Form")
    print("=" * 60)

    form_card = Card(
        dir="rtl",
        lang="ar",
        children=[
            Title(value="نموذج التواصل", dir="rtl"),
            Caption(value="نسعد بتواصلكم معنا", dir="rtl"),
            Col(
                gap=4,
                children=[
                    # Name field
                    Label(value="الاسم الكامل", fieldName="name", dir="rtl"),
                    Input(
                        name="name",
                        placeholder="أدخل اسمك الكامل",
                        dir="rtl",
                        required=True,
                    ),
                    # Email field
                    Label(value="البريد الإلكتروني", fieldName="email", dir="rtl"),
                    Input(
                        name="email",
                        placeholder="example@email.com",
                        dir="ltr",  # Email is LTR even in RTL form
                        inputType="email",
                        required=True,
                    ),
                    # Message field
                    Label(value="الرسالة", fieldName="message", dir="rtl"),
                    Textarea(
                        name="message",
                        placeholder="اكتب رسالتك هنا...",
                        dir="rtl",
                        lang="ar",
                        rows=5,
                        required=True,
                    ),
                    # Submit button
                    Button(
                        label="إرسال",
                        dir="rtl",
                        style="primary",
                        block=True,
                    ),
                ],
            ),
        ],
    )

    print("Complete RTL Form created successfully!")
    print("Form includes: name, email, message, and submit button")
    print()


def example_rtl_best_practices():
    """Example 7: Best practices for RTL."""
    print("=" * 60)
    print("Example 7: RTL Best Practices")
    print("=" * 60)

    practices = [
        {
            "title": "1. استخدم dir='auto' للنصوص المختلطة",
            "desc": "Use dir='auto' for mixed-direction text",
            "widget": Text(value="مرحبا ChatKit مرحبا", dir="auto"),
        },
        {
            "title": "2. حدد اللغة بوضوح",
            "desc": "Always specify language code",
            "widget": Text(value="مرحبا", dir="rtl", lang="ar"),
        },
        {
            "title": "3. البريد الإلكتروني يبقى LTR",
            "desc": "Keep emails and URLs LTR",
            "widget": Input(name="email", placeholder="user@example.com", dir="ltr"),
        },
        {
            "title": "4. استخدم الكشف التلقائي عند عدم التأكد",
            "desc": "Use auto-detection when unsure",
            "widget": Text(value="", dir="auto"),
        },
    ]

    for i, practice in enumerate(practices, 1):
        print(f"{practice['title']}")
        print(f"   {practice['desc']}")
        print(f"   Widget: {practice['widget'].type}, dir={practice['widget'].dir}")
        if i < len(practices):
            print()

    print()


def example_performance_tips():
    """Example 8: Performance tips for RTL."""
    print("=" * 60)
    print("Example 8: Performance Tips")
    print("=" * 60)

    tips = """
    نصائح الأداء / Performance Tips:
    
    1. استخدم dir='rtl' بشكل صريح عندما تعرف الاتجاه
       Use explicit dir='rtl' when you know the direction
       
    2. تجنب الكشف التلقائي المتكرر للنصوص الكبيرة
       Avoid repeated auto-detection for large texts
       
    3. قم بتخزين النتائج المكتشفة مؤقتاً
       Cache detected results when possible
       
    4. استخدم lang= للحصول على دعم أفضل من المتصفح
       Use lang= for better browser support
    """

    print(tips)
    print()


def main():
    """Run all RTL examples."""
    print("\n")
    print("=" * 60)
    print("ChatKit RTL Support - Examples")
    print("=" * 60)
    print("\n")

    # Run all examples
    example_basic_rtl_text()
    example_auto_detection()
    example_rtl_card()
    example_mixed_content()
    example_markdown_rtl()
    example_form_rtl()
    example_rtl_best_practices()
    example_performance_tips()

    print("=" * 60)
    print("All examples completed successfully! ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
