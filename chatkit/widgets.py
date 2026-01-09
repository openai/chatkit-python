from __future__ import annotations

import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from jinja2 import Environment, StrictUndefined, Template
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
)
from typing_extensions import NotRequired, TypedDict, deprecated

from .actions import ActionConfig
from .icons import IconName

_jinja_env = Environment(undefined=StrictUndefined)

_direct_usage_of_named_widget_types_deprecated = deprecated(
    "Direct usage of named widget classes is deprecated. "
    "Use WidgetTemplate to build widgets from .widget files instead. "
    "Visit https://widgets.chatkit.studio/ to author widget files."
)


@_direct_usage_of_named_widget_types_deprecated
class ThemeColor(TypedDict):
    """Color values for light and dark themes."""

    dark: str
    """Color to use when the theme is dark."""
    light: str
    """Color to use when the theme is light."""


@_direct_usage_of_named_widget_types_deprecated
class Spacing(TypedDict):
    """Shorthand spacing values applied to a widget."""

    top: NotRequired[float | str]
    """Top spacing; accepts a spacing unit or CSS string."""
    right: NotRequired[float | str]
    """Right spacing; accepts a spacing unit or CSS string."""
    bottom: NotRequired[float | str]
    """Bottom spacing; accepts a spacing unit or CSS string."""
    left: NotRequired[float | str]
    """Left spacing; accepts a spacing unit or CSS string."""
    x: NotRequired[float | str]
    """Horizontal spacing; accepts a spacing unit or CSS string."""
    y: NotRequired[float | str]
    """Vertical spacing; accepts a spacing unit or CSS string."""


@_direct_usage_of_named_widget_types_deprecated
class Border(TypedDict):
    """Border style definition for an edge."""

    size: int
    """Thickness of the border in px."""
    color: NotRequired[str | ThemeColor]
    """Border color; accepts border color token, a primitive color token, a CSS string, or theme-aware `{ light, dark }`.

    Valid tokens: `default` `subtle` `strong`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    style: NotRequired[
        Literal[
            "solid", "dashed", "dotted", "double", "groove", "ridge", "inset", "outset"
        ]
    ]
    """Border line style."""


@_direct_usage_of_named_widget_types_deprecated
class Borders(TypedDict):
    """Composite border configuration applied across edges."""

    top: NotRequired[int | Border]
    """Top border or thickness in px."""
    right: NotRequired[int | Border]
    """Right border or thickness in px."""
    bottom: NotRequired[int | Border]
    """Bottom border or thickness in px."""
    left: NotRequired[int | Border]
    """Left border or thickness in px."""
    x: NotRequired[int | Border]
    """Horizontal borders or thickness in px."""
    y: NotRequired[int | Border]
    """Vertical borders or thickness in px."""


@_direct_usage_of_named_widget_types_deprecated
class MinMax(TypedDict):
    """Integer minimum/maximum bounds."""

    min: NotRequired[int]
    """Minimum value (inclusive)."""
    max: NotRequired[int]
    """Maximum value (inclusive)."""


@_direct_usage_of_named_widget_types_deprecated
class EditableProps(TypedDict):
    """Editable field options for text widgets."""

    name: str
    """The name of the form control field used when submitting forms."""
    autoFocus: NotRequired[bool]
    """Autofocus the editable input when it appears."""
    autoSelect: NotRequired[bool]
    """Select all text on focus."""
    autoComplete: NotRequired[str]
    """Native autocomplete hint for the input."""
    allowAutofillExtensions: NotRequired[bool]
    """Allow browser password/autofill extensions."""
    pattern: NotRequired[str]
    """Regex pattern for input validation."""
    placeholder: NotRequired[str]
    """Placeholder text for the editable input."""
    required: NotRequired[bool]
    """Mark the editable input as required."""


RadiusValue = Literal[
    "2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "full", "100%", "none"
]
"""Allowed corner radius tokens."""

TextAlign = Literal["start", "center", "end"]
"""Horizontal text alignment options."""

TextSize = Literal["xs", "sm", "md", "lg", "xl"]
"""Body text size tokens."""

IconSize = Literal["xs", "sm", "md", "lg", "xl", "2xl", "3xl"]
"""Icon size tokens."""

TitleSize = Literal["sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
"""Title text size tokens."""

CaptionSize = Literal["sm", "md", "lg"]
"""Caption text size tokens."""

Alignment = Literal["start", "center", "end", "baseline", "stretch"]
"""Flexbox alignment options."""
Justification = Literal[
    "start", "center", "end", "between", "around", "evenly", "stretch"
]
"""Flexbox justification options."""

ControlVariant = Literal["solid", "soft", "outline", "ghost"]
"""Button and input style variants."""
ControlSize = Literal["3xs", "2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl"]
"""Button and input size variants."""


def _drop_none(x):
    """Recursively remove ``None`` values when serializing widgets."""
    if isinstance(x, dict):
        return {
            k: _drop_none(v) for k, v in x.items() if k == "children" or v is not None
        }
    if isinstance(x, list):
        return [_drop_none(v) for v in x if v is not None]
    return x


class WidgetComponentBase(BaseModel):
    """Base Pydantic model for all ChatKit widget components."""

    model_config = ConfigDict(serialize_by_alias=True)

    key: str | None = None
    id: str | None = None
    type: str = Field(...)

    # For nested model dumps (e.g. if Widget is not the top-level model)
    @model_serializer(mode="wrap")
    def serialize(self, next_):
        dumped = next_(self)
        # Recursively filter out None values when serialized.
        # Do this explicitly instead of overriding model_dump_json and model_dump;
        # the overrides will not be invoked unless the widget is the top-level model.
        dumped = _drop_none(dumped)
        # include type even when exlude_defaults is True
        if isinstance(dumped, dict):
            dumped["type"] = self.type

        return dumped


@_direct_usage_of_named_widget_types_deprecated
class WidgetStatusWithFavicon(TypedDict):
    """Widget status representation using a favicon."""

    text: str
    """Status text to display."""
    favicon: NotRequired[str]
    """URL of a favicon to render at the start of the status."""
    frame: NotRequired[bool]
    """Show a frame around the favicon for contrast."""


@_direct_usage_of_named_widget_types_deprecated
class WidgetStatusWithIcon(TypedDict):
    """Widget status representation using an icon."""

    text: str
    """Status text to display."""
    icon: NotRequired[WidgetIcon]
    """Icon to render at the start of the status."""


WidgetStatus = WidgetStatusWithFavicon | WidgetStatusWithIcon
"""Union for representing widget status messaging."""


@_direct_usage_of_named_widget_types_deprecated
class ListViewItem(WidgetComponentBase):
    """Single row inside a ``ListView`` component."""

    type: Literal["ListViewItem"] = Field(default="ListViewItem", frozen=True)  # pyright: ignore
    children: list["WidgetComponent"]
    """Content for the list item."""
    onClickAction: ActionConfig | None = None
    """Optional action triggered when the list item is clicked."""
    gap: int | str | None = None
    """Gap between children within the list item; spacing unit or CSS string."""
    align: Alignment | None = None
    """Y-axis alignment for content within the list item."""


@_direct_usage_of_named_widget_types_deprecated
class ListView(WidgetComponentBase):
    """Container component for rendering collections of list items."""

    type: Literal["ListView"] = Field(default="ListView", frozen=True)  # pyright: ignore
    children: list[ListViewItem]
    """Items to render in the list."""
    limit: int | Literal["auto"] | None = None
    """Max number of items to show before a "Show more" control."""
    status: WidgetStatus | None = None
    """Optional status header displayed above the list."""
    theme: Literal["light", "dark"] | None = None
    """Force light or dark theme for this subtree."""


@_direct_usage_of_named_widget_types_deprecated
class CardAction(TypedDict):
    """Configuration for confirm/cancel actions within a card."""

    label: str
    """Button label shown in the card footer."""
    action: ActionConfig
    """Declarative action dispatched to the host application."""


@_direct_usage_of_named_widget_types_deprecated
class Card(WidgetComponentBase):
    """Versatile container used for structuring widget content."""

    type: Literal["Card"] = Field(default="Card", frozen=True)  # pyright: ignore
    asForm: bool | None = None
    """Treat the card as an HTML form so confirm/cancel capture form data."""
    children: list["WidgetComponent"]
    """Child components rendered inside the card."""
    background: str | ThemeColor | None = None
    """Background color; accepts background color token, a primitive color token, a CSS string, or theme-aware `{ light, dark }`.

    Valid tokens: `surface` `surface-secondary` `surface-tertiary` `surface-elevated` `surface-elevated-secondary`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    size: Literal["sm", "md", "lg", "full"] | None = None
    """Visual size of the card; accepts a size token. No preset default is documented."""
    padding: float | str | Spacing | None = None
    """Inner spacing of the card; spacing unit, CSS string, or padding object."""
    status: WidgetStatus | None = None
    """Optional status header displayed above the card."""
    collapsed: bool | None = None
    """Collapse card body after the main action has completed."""
    confirm: CardAction | None = None
    """Confirmation action button shown in the card footer."""
    cancel: CardAction | None = None
    """Cancel action button shown in the card footer."""
    theme: Literal["light", "dark"] | None = None
    """Force light or dark theme for this subtree."""


@_direct_usage_of_named_widget_types_deprecated
class Markdown(WidgetComponentBase):
    """Widget rendering Markdown content, optionally streamed."""

    type: Literal["Markdown"] = Field(default="Markdown", frozen=True)  # pyright: ignore
    value: str
    """Markdown source string to render."""
    streaming: bool | None = None
    """Applies streaming-friendly transitions for incremental updates."""


@_direct_usage_of_named_widget_types_deprecated
class Text(WidgetComponentBase):
    """Widget rendering plain text with typography controls."""

    type: Literal["Text"] = Field(default="Text", frozen=True)  # pyright: ignore
    value: str
    """Text content to display."""
    streaming: bool | None = None
    """Enables streaming-friendly transitions for incremental updates."""
    italic: bool | None = None
    """Render text in italic style."""
    lineThrough: bool | None = None
    """Render text with a line-through decoration."""
    color: str | ThemeColor | None = None
    """
    Text color; accepts a text color token, a primitive color token, a CSS color string, or a theme-aware `{ light, dark }`.

    Text color tokens: `prose` `primary` `emphasis` `secondary` `tertiary` `success` `warning` `danger`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    weight: Literal["normal", "medium", "semibold", "bold"] | None = None
    """Font weight; accepts a font weight token."""
    width: float | str | None = None
    """Constrain the text container width; px or CSS string."""
    size: TextSize | None = None
    """Size of the text; accepts a text size token."""
    textAlign: TextAlign | None = None
    """Horizontal text alignment."""
    truncate: bool | None = None
    """Truncate overflow with ellipsis."""
    minLines: int | None = None
    """Reserve space for a minimum number of lines."""
    maxLines: int | None = None
    """Limit text to a maximum number of lines (line clamp)."""
    editable: Literal[False] | EditableProps | None = None
    """Enable inline editing for this text node."""


@_direct_usage_of_named_widget_types_deprecated
class Title(WidgetComponentBase):
    """Widget rendering prominent headline text."""

    type: Literal["Title"] = Field(default="Title", frozen=True)  # pyright: ignore
    value: str
    """Text content to display."""
    color: str | ThemeColor | None = None
    """
    Text color; accepts a text color token, a primitive color token, a CSS color string, or a theme-aware `{ light, dark }`.

    Text color tokens: `prose` `primary` `emphasis` `secondary` `tertiary` `success` `warning` `danger`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    weight: Literal["normal", "medium", "semibold", "bold"] | None = None
    """Font weight; accepts a font weight token."""
    size: TitleSize | None = None
    """Size of the title text; accepts a title size token."""
    textAlign: TextAlign | None = None
    """Horizontal text alignment."""
    truncate: bool | None = None
    """Truncate overflow with ellipsis."""
    maxLines: int | None = None
    """Limit text to a maximum number of lines (line clamp)."""


@_direct_usage_of_named_widget_types_deprecated
class Caption(WidgetComponentBase):
    """Widget rendering supporting caption text."""

    type: Literal["Caption"] = Field(default="Caption", frozen=True)  # pyright: ignore
    value: str
    """Text content to display."""
    color: str | ThemeColor | None = None
    """
    Text color; accepts a text color token, a primitive color token, a CSS color string, or a theme-aware `{ light, dark }`.

    Text color tokens: `prose` `primary` `emphasis` `secondary` `tertiary` `success` `warning` `danger`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    weight: Literal["normal", "medium", "semibold", "bold"] | None = None
    """Font weight; accepts a font weight token."""
    size: CaptionSize | None = None
    """Size of the caption text; accepts a caption size token."""
    textAlign: TextAlign | None = None
    """Horizontal text alignment."""
    truncate: bool | None = None
    """Truncate overflow with ellipsis."""
    maxLines: int | None = None
    """Limit text to a maximum number of lines (line clamp)."""


@_direct_usage_of_named_widget_types_deprecated
class Badge(WidgetComponentBase):
    """Small badge indicating status or categorization."""

    type: Literal["Badge"] = Field(default="Badge", frozen=True)  # pyright: ignore
    label: str
    """Text to display inside the badge."""
    color: (
        Literal["secondary", "success", "danger", "warning", "info", "discovery"] | None
    ) = None
    """Color of the badge; accepts a badge color token."""
    variant: Literal["solid", "soft", "outline"] | None = None
    """Visual style of the badge."""
    size: Literal["sm", "md", "lg"] | None = None
    """Size of the badge."""
    pill: bool | None = None
    """Determines if the badge should be fully rounded (pill)."""


@_direct_usage_of_named_widget_types_deprecated
class BoxBase(BaseModel):
    """Shared layout props for flexible container widgets."""

    children: list["WidgetComponent"] | None = None
    """Child components to render inside the container."""
    align: Alignment | None = None
    """Cross-axis alignment of children."""
    justify: Justification | None = None
    """Main-axis distribution of children."""
    wrap: Literal["nowrap", "wrap", "wrap-reverse"] | None = None
    """Wrap behavior for flex items."""
    flex: int | str | None = None
    """Flex growth/shrink factor."""
    gap: int | str | None = None
    """Gap between direct children; spacing unit or CSS string."""
    height: float | str | None = None
    """Explicit height; px or CSS string."""
    width: float | str | None = None
    """Explicit width; px or CSS string."""
    size: float | str | None = None
    """Shorthand to set both width and height; px or CSS string."""
    minHeight: int | str | None = None
    """Minimum height; px or CSS string."""
    minWidth: int | str | None = None
    """Minimum width; px or CSS string."""
    minSize: int | str | None = None
    """Shorthand to set both minWidth and minHeight; px or CSS string."""
    maxHeight: int | str | None = None
    """Maximum height; px or CSS string."""
    maxWidth: int | str | None = None
    """Maximum width; px or CSS string."""
    maxSize: int | str | None = None
    """Shorthand to set both maxWidth and maxHeight; px or CSS string."""
    padding: float | str | Spacing | None = None
    """Inner padding; spacing unit, CSS string, or padding object."""
    margin: float | str | Spacing | None = None
    """Outer margin; spacing unit, CSS string, or margin object."""
    border: int | Border | Borders | None = None
    """Border applied to the container; px or border object/shorthand."""
    radius: RadiusValue | None = None
    """Border radius; accepts a radius token."""
    background: str | ThemeColor | None = None
    """Background color; accepts background color token, a primitive color token, a CSS string, or theme-aware `{ light, dark }`.

    Valid tokens: `surface` `surface-secondary` `surface-tertiary` `surface-elevated` `surface-elevated-secondary`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    aspectRatio: float | str | None = None
    """Aspect ratio of the box (e.g., 16/9); number or CSS string."""


@_direct_usage_of_named_widget_types_deprecated
class Box(WidgetComponentBase, BoxBase):
    """Generic flex container with direction control."""

    type: Literal["Box"] = Field(default="Box", frozen=True)  # pyright: ignore
    direction: Literal["row", "col"] | None = None
    """Flex direction for content within this container."""


@_direct_usage_of_named_widget_types_deprecated
class Row(WidgetComponentBase, BoxBase):
    """Horizontal flex container."""

    type: Literal["Row"] = Field(default="Row", frozen=True)  # pyright: ignore


@_direct_usage_of_named_widget_types_deprecated
class Col(WidgetComponentBase, BoxBase):
    """Vertical flex container."""

    type: Literal["Col"] = Field(default="Col", frozen=True)  # pyright: ignore


@_direct_usage_of_named_widget_types_deprecated
class Form(WidgetComponentBase, BoxBase):
    """Form wrapper capable of submitting ``onSubmitAction``."""

    type: Literal["Form"] = Field(default="Form", frozen=True)  # pyright: ignore
    onSubmitAction: ActionConfig | None = None
    """Action dispatched when the form is submitted."""
    direction: Literal["row", "col"] | None = None
    """Flex direction for laying out form children."""


@_direct_usage_of_named_widget_types_deprecated
class Divider(WidgetComponentBase):
    """Visual divider separating content sections."""

    type: Literal["Divider"] = Field(default="Divider", frozen=True)  # pyright: ignore
    color: str | ThemeColor | None = None
    """Divider color; accepts border color token, a primitive color token, a CSS string, or theme-aware `{ light, dark }`.

    Valid tokens: `default` `subtle` `strong`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    size: int | str | None = None
    """Thickness of the divider line; px or CSS string."""
    spacing: int | str | None = None
    """Outer spacing above and below the divider; spacing unit or CSS string."""
    flush: bool | None = None
    """Flush the divider to the container edge, removing surrounding padding."""


@_direct_usage_of_named_widget_types_deprecated
class Icon(WidgetComponentBase):
    """Icon component referencing a built-in icon name."""

    type: Literal["Icon"] = Field(default="Icon", frozen=True)  # pyright: ignore
    name: WidgetIcon
    """Name of the icon to display."""
    color: str | ThemeColor | None = None
    """
    Icon color; accepts a text color token, a primitive color token, a CSS color string, or a theme-aware `{ light, dark }`.

    Text color tokens: `prose` `primary` `emphasis` `secondary` `tertiary` `success` `warning` `danger`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    size: IconSize | None = None
    """Size of the icon; accepts an icon size token."""


@_direct_usage_of_named_widget_types_deprecated
class Image(WidgetComponentBase):
    """Image component with sizing and fitting controls."""

    type: Literal["Image"] = Field(default="Image", frozen=True)  # pyright: ignore
    src: str
    """Image URL source."""
    alt: str | None = None
    """Alternate text for accessibility."""
    fit: Literal["cover", "contain", "fill", "scale-down", "none"] | None = None
    """How the image should fit within the container."""
    position: (
        Literal[
            "top left",
            "top",
            "top right",
            "left",
            "center",
            "right",
            "bottom left",
            "bottom",
            "bottom right",
        ]
        | None
    ) = None
    """Focal position of the image within the container."""
    radius: RadiusValue | None = None
    """Border radius; accepts a radius token."""
    frame: bool | None = None
    """Draw a subtle frame around the image."""
    flush: bool | None = None
    """Flush the image to the container edge, removing surrounding padding."""
    height: int | str | None = None
    """Explicit height; px or CSS string."""
    width: int | str | None = None
    """Explicit width; px or CSS string."""
    size: int | str | None = None
    """Shorthand to set both width and height; px or CSS string."""
    minHeight: int | str | None = None
    """Minimum height; px or CSS string."""
    minWidth: int | str | None = None
    """Minimum width; px or CSS string."""
    minSize: int | str | None = None
    """Shorthand to set both minWidth and minHeight; px or CSS string."""
    maxHeight: int | str | None = None
    """Maximum height; px or CSS string."""
    maxWidth: int | str | None = None
    """Maximum width; px or CSS string."""
    maxSize: int | str | None = None
    """Shorthand to set both maxWidth and maxHeight; px or CSS string."""
    margin: int | str | Spacing | None = None
    """Outer margin; spacing unit, CSS string, or margin object."""
    background: str | ThemeColor | None = None
    """Background color; accepts background color token, a primitive color token, a CSS string, or theme-aware `{ light, dark }`.

    Valid tokens: `surface` `surface-secondary` `surface-tertiary` `surface-elevated` `surface-elevated-secondary`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """
    aspectRatio: float | str | None = None
    """Aspect ratio of the box (e.g., 16/9); number or CSS string."""
    flex: int | str | None = None
    """Flex growth/shrink factor."""


@_direct_usage_of_named_widget_types_deprecated
class Button(WidgetComponentBase):
    """Button component optionally wired to an action."""

    type: Literal["Button"] = Field(default="Button", frozen=True)  # pyright: ignore
    submit: bool | None = None
    """Configure the button as a submit button for the nearest form."""
    label: str | None = None
    """Text to display inside the button."""
    onClickAction: ActionConfig | None = None
    """Action dispatched on click."""
    iconStart: WidgetIcon | None = None
    """Icon shown before the label; can be used for icon-only buttons."""
    iconEnd: WidgetIcon | None = None
    """Optional icon shown after the label."""
    style: Literal["primary", "secondary"] | None = None
    """Convenience preset for button style."""
    iconSize: Literal["sm", "md", "lg", "xl", "2xl"] | None = None
    """Controls the size of icons within the button; accepts an icon size token."""
    color: (
        Literal[
            "primary",
            "secondary",
            "info",
            "discovery",
            "success",
            "caution",
            "warning",
            "danger",
        ]
        | None
    ) = None
    """Color of the button; accepts a button color token."""
    variant: ControlVariant | None = None
    """Visual variant of the button; accepts a control variant token."""
    size: ControlSize | None = None
    """Controls the overall size of the button."""
    pill: bool | None = None
    """Determines if the button should be fully rounded (pill)."""
    uniform: bool | None = None
    """Determines if the button should have matching width and height."""
    block: bool | None = None
    """Extend the button to 100% of the available width."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""


@_direct_usage_of_named_widget_types_deprecated
class Spacer(WidgetComponentBase):
    """Flexible spacer used to push content apart."""

    type: Literal["Spacer"] = Field(default="Spacer", frozen=True)  # pyright: ignore
    minSize: int | str | None = None
    """Minimum size the spacer should occupy along the flex direction."""


@_direct_usage_of_named_widget_types_deprecated
class SelectOption(TypedDict):
    """Selectable option used by the ``Select`` widget."""

    value: str
    """Option value submitted with the form."""
    label: str
    """Human-readable label for the option."""
    disabled: NotRequired[bool]
    """Disable the option."""
    description: NotRequired[str]
    """Displayed as secondary text below the option `label`."""


@_direct_usage_of_named_widget_types_deprecated
class Select(WidgetComponentBase):
    """Select dropdown component."""

    type: Literal["Select"] = Field(default="Select", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    options: list[SelectOption]
    """List of selectable options."""
    onChangeAction: ActionConfig | None = None
    """Action dispatched when the value changes."""
    placeholder: str | None = None
    """Placeholder text shown when no value is selected."""
    defaultValue: str | None = None
    """Initial value of the select."""
    variant: ControlVariant | None = None
    """Visual style of the select; accepts a control variant token."""
    size: ControlSize | None = None
    """Controls the size of the select control."""
    pill: bool | None = None
    """Determines if the select should be fully rounded (pill)."""
    block: bool | None = None
    """Extend the select to 100% of the available width."""
    clearable: bool | None = None
    """Show a clear control to unset the value."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""
    searchable: bool | None = None
    """Enables the search input. Defaults to enabling search when there are more than 15 options."""


@_direct_usage_of_named_widget_types_deprecated
class DatePicker(WidgetComponentBase):
    """Date picker input component."""

    type: Literal["DatePicker"] = Field(default="DatePicker", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    onChangeAction: ActionConfig | None = None
    """Action dispatched when the date value changes."""
    placeholder: str | None = None
    """Placeholder text shown when no date is selected."""
    defaultValue: datetime | None = None
    """Initial value of the date picker."""
    min: datetime | None = None
    """Earliest selectable date (inclusive)."""
    max: datetime | None = None
    """Latest selectable date (inclusive)."""
    variant: ControlVariant | None = None
    """Visual variant of the datepicker control."""
    size: ControlSize | None = None
    """Controls the size of the datepicker control."""
    side: Literal["top", "bottom", "left", "right"] | None = None
    """Preferred side to render the calendar."""
    align: Literal["start", "center", "end"] | None = None
    """Preferred alignment of the calendar relative to the control."""
    pill: bool | None = None
    """Determines if the datepicker should be fully rounded (pill)."""
    block: bool | None = None
    """Extend the datepicker to 100% of the available width."""
    clearable: bool | None = None
    """Show a clear control to unset the value."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""


@_direct_usage_of_named_widget_types_deprecated
class Checkbox(WidgetComponentBase):
    """Checkbox input component."""

    type: Literal["Checkbox"] = Field(default="Checkbox", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    label: str | None = None
    """Optional label text rendered next to the checkbox."""
    defaultChecked: bool | None = None
    """The initial checked state of the checkbox."""
    onChangeAction: ActionConfig | None = None
    """Action dispatched when the checked state changes."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""
    required: bool | None = None
    """Mark the checkbox as required for form submission."""


@_direct_usage_of_named_widget_types_deprecated
class Input(WidgetComponentBase):
    """Single-line text input component."""

    type: Literal["Input"] = Field(default="Input", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    inputType: Literal["number", "email", "text", "password", "tel", "url"] | None = (
        None
    )
    """Native input type."""
    defaultValue: str | None = None
    """Initial value of the input."""
    required: bool | None = None
    """Mark the input as required for form submission."""
    pattern: str | None = None
    """Regex pattern for input validation."""
    placeholder: str | None = None
    """Placeholder text shown when empty."""
    allowAutofillExtensions: bool | None = None
    """Allow password managers / autofill extensions to appear."""
    autoSelect: bool | None = None
    """Select all contents of the input when it mounts."""
    autoFocus: bool | None = None
    """Autofocus the input when it mounts."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""
    variant: Literal["soft", "outline"] | None = None
    """Visual style of the input."""
    size: ControlSize | None = None
    """Controls the size of the input control."""
    gutterSize: Literal["2xs", "xs", "sm", "md", "lg", "xl"] | None = None
    """Controls gutter on the edges of the input; overrides value from `size`."""
    pill: bool | None = None
    """Determines if the input should be fully rounded (pill)."""


@_direct_usage_of_named_widget_types_deprecated
class Label(WidgetComponentBase):
    """Form label associated with a field."""

    type: Literal["Label"] = Field(default="Label", frozen=True)  # pyright: ignore
    value: str
    """Text content of the label."""
    fieldName: str
    """Name of the field this label describes."""
    size: TextSize | None = None
    """Size of the label text; accepts a text size token."""
    weight: Literal["normal", "medium", "semibold", "bold"] | None = None
    """Font weight; accepts a font weight token."""
    textAlign: TextAlign | None = None
    """Horizontal text alignment."""
    color: str | ThemeColor | None = None
    """
    Text color; accepts a text color token, a primitive color token, a CSS color string, or a theme-aware `{ light, dark }`.

    Text color tokens: `prose` `primary` `emphasis` `secondary` `tertiary` `success` `warning` `danger`

    Primitive color token: e.g. `red-100`, `blue-900`, `gray-500`
    """


@_direct_usage_of_named_widget_types_deprecated
class RadioOption(TypedDict):
    """Option inside a ``RadioGroup`` widget."""

    label: str
    """Label displayed next to the radio option."""
    value: str
    """Value submitted when the radio option is selected."""
    disabled: NotRequired[bool]
    """Disables a specific radio option."""


@_direct_usage_of_named_widget_types_deprecated
class RadioGroup(WidgetComponentBase):
    """Grouped radio input control."""

    type: Literal["RadioGroup"] = Field(default="RadioGroup", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    options: list[RadioOption] | None = None
    """Array of options to render as radio items."""
    ariaLabel: str | None = None
    """Accessible label for the radio group; falls back to `name`."""
    onChangeAction: ActionConfig | None = None
    """Action dispatched when the selected value changes."""
    defaultValue: str | None = None
    """Initial selected value of the radio group."""
    direction: Literal["row", "col"] | None = None
    """Layout direction of the radio items."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles for the entire group."""
    required: bool | None = None
    """Mark the group as required for form submission."""


@_direct_usage_of_named_widget_types_deprecated
class Textarea(WidgetComponentBase):
    """Multiline text input component."""

    type: Literal["Textarea"] = Field(default="Textarea", frozen=True)  # pyright: ignore
    name: str
    """The name of the form control field used when submitting forms."""
    defaultValue: str | None = None
    """Initial value of the textarea."""
    required: bool | None = None
    """Mark the textarea as required for form submission."""
    pattern: str | None = None
    """Regex pattern for input validation."""
    placeholder: str | None = None
    """Placeholder text shown when empty."""
    autoSelect: bool | None = None
    """Select all contents of the textarea when it mounts."""
    autoFocus: bool | None = None
    """Autofocus the textarea when it mounts."""
    disabled: bool | None = None
    """Disable interactions and apply disabled styles."""
    variant: Literal["soft", "outline"] | None = None
    """Visual style of the textarea."""
    size: ControlSize | None = None
    """Controls the size of the textarea control."""
    gutterSize: Literal["2xs", "xs", "sm", "md", "lg", "xl"] | None = None
    """Controls gutter on the edges of the textarea; overrides value from `size`."""
    rows: int | None = None
    """Initial number of visible rows."""
    autoResize: bool | None = None
    """Automatically grow/shrink to fit content."""
    maxRows: int | None = None
    """Maximum number of rows when auto-resizing."""
    allowAutofillExtensions: bool | None = None
    """Allow password managers / autofill extensions to appear."""


@_direct_usage_of_named_widget_types_deprecated
class Transition(WidgetComponentBase):
    """Wrapper enabling transitions for a child component."""

    type: Literal["Transition"] = Field(default="Transition", frozen=True)  # pyright: ignore
    children: WidgetComponent | None
    """The child component to animate layout changes for."""


@_direct_usage_of_named_widget_types_deprecated
class Chart(WidgetComponentBase):
    """Data visualization component for simple bar/line/area charts."""

    type: Literal["Chart"] = Field(default="Chart", frozen=True)  # pyright: ignore
    data: list[dict[str, str | int | float]]
    """Tabular data for the chart, where each row maps field names to values."""
    series: list[Series]
    """One or more series definitions that describe how to visualize data fields."""
    xAxis: str | XAxisConfig
    """X-axis configuration; either a `dataKey` string or a config object."""
    showYAxis: bool | None = None
    """Controls whether the Y axis is rendered."""
    showLegend: bool | None = None
    """Controls whether a legend is rendered."""
    showTooltip: bool | None = None
    """Controls whether a tooltip is rendered when hovering over a datapoint."""
    barGap: int | None = None
    """Gap between bars within the same category (in px)."""
    barCategoryGap: int | None = None
    """Gap between bar categories/groups (in px)."""
    flex: int | str | None = None
    """Flex growth/shrink factor for layout."""
    height: int | str | None = None
    """Explicit height; px or CSS string."""
    width: int | str | None = None
    """Explicit width; px or CSS string."""
    size: int | str | None = None
    """Shorthand to set both width and height; px or CSS string."""
    minHeight: int | str | None = None
    """Minimum height; px or CSS string."""
    minWidth: int | str | None = None
    """Minimum width; px or CSS string."""
    minSize: int | str | None = None
    """Shorthand to set both minWidth and minHeight; px or CSS string."""
    maxHeight: int | str | None = None
    """Maximum height; px or CSS string."""
    maxWidth: int | str | None = None
    """Maximum width; px or CSS string."""
    maxSize: int | str | None = None
    """Shorthand to set both maxWidth and maxHeight; px or CSS string."""
    aspectRatio: float | str | None = None
    """Aspect ratio of the chart area (e.g., 16/9); number or CSS string."""


@_direct_usage_of_named_widget_types_deprecated
class XAxisConfig(TypedDict):
    """Configuration object for the X axis."""

    dataKey: str
    """Field name from each data row to use for X-axis categories."""
    hide: NotRequired[bool]
    """Hide the X axis line, ticks, and labels when true."""
    labels: NotRequired[dict[str, str]]
    """Custom mapping of tick values to display labels."""


CurveType = Literal[
    "basis",
    "basisClosed",
    "basisOpen",
    "bumpX",
    "bumpY",
    "bump",
    "linear",
    "linearClosed",
    "natural",
    "monotoneX",
    "monotoneY",
    "monotone",
    "step",
    "stepBefore",
    "stepAfter",
]
"""Interpolation curve types for `area` and `line` series."""


@_direct_usage_of_named_widget_types_deprecated
class BarSeries(BaseModel):
    """A bar series plotted from a numeric `dataKey`. Supports stacking."""

    type: Literal["bar"] = Field(default="bar", frozen=True)
    label: str | None
    """Legend label for the series."""
    dataKey: str
    """Field name from each data row that contains the numeric value."""
    stack: str | None = None
    """Optional stack group ID. Series with the same ID stack together."""
    color: str | ThemeColor | None = None
    """
    Color for the series; accepts chart color token, a primitive color token, a CSS string, or theme-aware { light, dark }.

    Chart color tokens: `blue` `purple` `orange` `green` `red` `yellow` `pink`

    Primitive color token, e.g., `red-100`, `blue-900`, `gray-500`

    Note: By default, a color will be sequentially assigned from the chart series colors.
    """


@_direct_usage_of_named_widget_types_deprecated
class AreaSeries(BaseModel):
    """An area series plotted from a numeric `dataKey`. Supports stacking and curves."""

    type: Literal["area"] = Field(default="area", frozen=True)
    label: str | None
    """Legend label for the series."""
    dataKey: str
    """Field name from each data row that contains the numeric value."""
    stack: str | None = None
    """Optional stack group ID. Series with the same ID stack together."""
    color: str | ThemeColor | None = None
    """
    Color for the series; accepts chart color token, a primitive color token, a CSS string, or theme-aware { light, dark }.

    Chart color tokens: `blue` `purple` `orange` `green` `red` `yellow` `pink`

    Primitive color token, e.g., `red-100`, `blue-900`, `gray-500`

    Note: By default, a color will be sequentially assigned from the chart series colors.
    """
    curveType: None | Literal[CurveType] = None
    """Interpolation curve type used to connect points."""


@_direct_usage_of_named_widget_types_deprecated
class LineSeries(BaseModel):
    """A line series plotted from a numeric `dataKey`. Supports curves."""

    type: Literal["line"] = Field(default="line", frozen=True)
    label: str | None
    """Legend label for the series."""
    dataKey: str
    """Field name from each data row that contains the numeric value."""
    color: str | ThemeColor | None = None
    """
    Color for the series; accepts chart color token, a primitive color token, a CSS string, or theme-aware { light, dark }.

    Chart color tokens: `blue` `purple` `orange` `green` `red` `yellow` `pink`

    Primitive color token, e.g., `red-100`, `blue-900`, `gray-500`

    Note: By default, a color will be sequentially assigned from the chart series colors.
    """
    curveType: None | Literal[CurveType] = None
    """Interpolation curve type used to connect points."""


Series = Annotated[
    BarSeries | AreaSeries | LineSeries,
    Field(discriminator="type"),
]
"""Union of all supported chart series types."""


class DynamicWidgetComponent(WidgetComponentBase):
    """
    A widget component with a statically defined base shape but dynamically
    defined additional fields loaded from a widget template or JSON schema.
    """

    model_config = ConfigDict(extra="allow")
    children: DynamicWidgetComponent | list[DynamicWidgetComponent] | None = None


StrictWidgetComponent = Annotated[
    Text
    | Title
    | Caption
    | Chart
    | Badge
    | Markdown
    | Box
    | Row
    | Col
    | Divider
    | Icon
    | Image
    | ListViewItem
    | Button
    | Checkbox
    | Spacer
    | Select
    | DatePicker
    | Form
    | Input
    | Label
    | RadioGroup
    | Textarea
    | Transition,
    Field(discriminator="type"),
]


StrictWidgetRoot = Annotated[
    Card | ListView,
    Field(discriminator="type"),
]


class DynamicWidgetRoot(DynamicWidgetComponent):
    """Dynamic root widget restricted to root types."""

    type: Literal["Card", "ListView"]  # pyright: ignore


class BasicRoot(DynamicWidgetComponent):
    """Layout root capable of nesting components or other roots."""

    type: Literal["Basic"] = Field(default="Basic", frozen=True)  # pyright: ignore


WidgetComponent = StrictWidgetComponent | DynamicWidgetComponent
"""Union of all renderable widget components."""

WidgetRoot = StrictWidgetRoot | DynamicWidgetRoot
"""Union of all renderable top-level widgets."""


WidgetIcon = IconName
"""Icon names accepted by widgets that render icons."""


class WidgetTemplate:
    """
    Utility for loading and building widgets from a .widget file.

    Example using .widget file on disc:
    ```python
    template = WidgetTemplate.from_file("path/to/my_widget.widget")
    widget = template.build({"name": "Harry Potter"})
    ```

    Example using already parsed widget definition:
    ```python
    template = WidgetTemplate(definition={"version": "1.0", "name": "...", "template": Template(...), "jsonSchema": {...}})
    widget = template.build({"name": "Harry Potter"})
    ```
    """

    def __init__(self, definition: dict[str, Any]):
        self.version = definition["version"]
        if self.version != "1.0":
            raise ValueError(f"Unsupported widget spec version: {self.version}")

        self.name = definition["name"]
        template = definition["template"]
        if isinstance(template, Template):
            self.template = template
        else:
            self.template = _jinja_env.from_string(template)
        self.data_schema = definition.get("jsonSchema", {})

    @classmethod
    def from_file(cls, file_path: str) -> WidgetTemplate:
        path = Path(file_path)
        if not path.is_absolute():
            caller_frame = inspect.stack()[1]
            caller_path = Path(caller_frame.filename).resolve()
            path = caller_path.parent / path

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        return cls(payload)

    def build(
        self, data: dict[str, Any] | BaseModel | None = None
    ) -> DynamicWidgetRoot:
        """Render the widget template with the given data and return a DynamicWidgetRoot instance."""
        rendered = self.template.render(**self._normalize_data(data))
        widget_dict = json.loads(rendered)
        return DynamicWidgetRoot.model_validate(widget_dict)

    def build_basic(self, data: dict[str, Any] | BaseModel | None = None) -> BasicRoot:
        """Separate method for building basic root widgets until BasicRoot is supported for streamed widgets."""
        rendered = self.template.render(**self._normalize_data(data))
        widget_dict = json.loads(rendered)
        return BasicRoot.model_validate(widget_dict)

    def _normalize_data(
        self, data: dict[str, Any] | BaseModel | None
    ) -> dict[str, Any]:
        if data is None:
            return {}
        return data.model_dump() if isinstance(data, BaseModel) else data
