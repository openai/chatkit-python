# ChatKit Widgets

This reference is generated from the `chatkit.widgets` module. Every component inherits the common props `id`, `key`, and `type`. Optional props default to `None` unless noted.

## Badge

Small badge indicating status or categorization.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Badge` | 'Badge' |
| `label` | `str` |  |
| `color` | `secondary | success | danger | warning | info | discovery | None` | None |
| `variant` | `solid | soft | outline | None` | None |
| `size` | `sm | md | lg | None` | None |
| `pill` | `bool | None` | None |

## Box

Generic flex container with direction control.

| Field | Type | Default |
| --- | --- | --- |
| `children` | `list['WidgetComponent'] | None` | None |
| `align` | `start | center | end | baseline | stretch | None` | None |
| `justify` | `start | center | end | between | around | evenly | stretch | None` | None |
| `wrap` | `nowrap | wrap | wrap-reverse | None` | None |
| `flex` | `int | str | None` | None |
| `gap` | `int | str | None` | None |
| `height` | `float | str | None` | None |
| `width` | `float | str | None` | None |
| `size` | `float | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `padding` | `float | str | Spacing | None` | None |
| `margin` | `float | str | Spacing | None` | None |
| `border` | `int | Border | Borders | None` | None |
| `radius` | `2xs | xs | sm | md | lg | xl | 2xl | 3xl | 4xl | full | 100% | none | None` | None |
| `background` | `str | ThemeColor | None` | None |
| `aspectRatio` | `float | str | None` | None |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Box` | 'Box' |
| `direction` | `row | col | None` | None |

## Button

Button component optionally wired to an action.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Button` | 'Button' |
| `submit` | `bool | None` | None |
| `label` | `str | None` | None |
| `onClickAction` | `ActionConfig | None` | None |
| `iconStart` | `WidgetIcon | None` | None |
| `iconEnd` | `WidgetIcon | None` | None |
| `style` | `primary | secondary | None` | None |
| `iconSize` | `sm | md | lg | xl | 2xl | None` | None |
| `color` | `primary | secondary | info | discovery | success | caution | warning | danger | None` | None |
| `variant` | `solid | soft | outline | ghost | None` | None |
| `size` | `3xs | 2xs | xs | sm | md | lg | xl | 2xl | 3xl | None` | None |
| `pill` | `bool | None` | None |
| `uniform` | `bool | None` | None |
| `block` | `bool | None` | None |
| `disabled` | `bool | None` | None |

## Caption

Widget rendering supporting caption text.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Caption` | 'Caption' |
| `value` | `str` |  |
| `color` | `str | ThemeColor | None` | None |
| `weight` | `normal | medium | semibold | bold | None` | None |
| `size` | `sm | md | lg | None` | None |
| `textAlign` | `start | center | end | None` | None |
| `truncate` | `bool | None` | None |
| `maxLines` | `int | None` | None |

## Card

Versatile container used for structuring widget content.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Card` | 'Card' |
| `asForm` | `bool | None` | None |
| `children` | `list['WidgetComponent']` |  |
| `background` | `str | ThemeColor | None` | None |
| `size` | `sm | md | lg | full | None` | None |
| `padding` | `float | str | Spacing | None` | None |
| `status` | `WidgetStatusWithFavicon | WidgetStatusWithIcon | None` | None |
| `collapsed` | `bool | None` | None |
| `confirm` | `CardAction | None` | None |
| `cancel` | `CardAction | None` | None |
| `theme` | `light | dark | None` | None |

## Chart

Data visualization component for simple bar/line/area charts.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Chart` | 'Chart' |
| `data` | `list[dict[str, str | int | float]]` |  |
| `series` | `list[Series]` |  |
| `xAxis` | `str | XAxisConfig` |  |
| `showYAxis` | `bool | None` | None |
| `showLegend` | `bool | None` | None |
| `showTooltip` | `bool | None` | None |
| `barGap` | `int | None` | None |
| `barCategoryGap` | `int | None` | None |
| `flex` | `int | str | None` | None |
| `height` | `int | str | None` | None |
| `width` | `int | str | None` | None |
| `size` | `int | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `aspectRatio` | `float | str | None` | None |

## Checkbox

Checkbox input component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Checkbox` | 'Checkbox' |
| `name` | `str` |  |
| `label` | `str | None` | None |
| `defaultChecked` | `bool | None` | None |
| `onChangeAction` | `ActionConfig | None` | None |
| `disabled` | `bool | None` | None |
| `required` | `bool | None` | None |

## Col

Vertical flex container.

| Field | Type | Default |
| --- | --- | --- |
| `children` | `list['WidgetComponent'] | None` | None |
| `align` | `start | center | end | baseline | stretch | None` | None |
| `justify` | `start | center | end | between | around | evenly | stretch | None` | None |
| `wrap` | `nowrap | wrap | wrap-reverse | None` | None |
| `flex` | `int | str | None` | None |
| `gap` | `int | str | None` | None |
| `height` | `float | str | None` | None |
| `width` | `float | str | None` | None |
| `size` | `float | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `padding` | `float | str | Spacing | None` | None |
| `margin` | `float | str | Spacing | None` | None |
| `border` | `int | Border | Borders | None` | None |
| `radius` | `2xs | xs | sm | md | lg | xl | 2xl | 3xl | 4xl | full | 100% | none | None` | None |
| `background` | `str | ThemeColor | None` | None |
| `aspectRatio` | `float | str | None` | None |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Col` | 'Col' |

## DatePicker

Date picker input component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `DatePicker` | 'DatePicker' |
| `name` | `str` | |
| `onChangeAction` | `ActionConfig | None` | None |
| `placeholder` | `str | None` | None |
| `defaultValue` | `datetime | None` | None |
| `min` | `datetime | None` | None |
| `max` | `datetime | None` | None |
| `variant` | `solid | soft | outline | ghost | None` | None |
| `size` | `3xs | 2xs | xs | sm | md | lg | xl | 2xl | 3xl | None` | None |
| `side` | `top | bottom | left | right | None` | None |
| `align` | `start | center | end | None` | None |
| `pill` | `bool | None` | None |
| `block` | `bool | None` | None |
| `clearable` | `bool | None` | None |
| `disabled` | `bool | None` | None |

## Divider

Visual divider separating content sections.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Divider` | 'Divider' |
| `color` | `str | ThemeColor | None` | None |
| `size` | `int | str | None` | None |
| `spacing` | `int | str | None` | None |
| `flush` | `bool | None` | None |

## Form

Form wrapper capable of submitting ``onSubmitAction``.

| Field | Type | Default |
| --- | --- | --- |
| `children` | `list['WidgetComponent'] | None` | None |
| `align` | `start | center | end | baseline | stretch | None` | None |
| `justify` | `start | center | end | between | around | evenly | stretch | None` | None |
| `wrap` | `nowrap | wrap | wrap-reverse | None` | None |
| `flex` | `int | str | None` | None |
| `gap` | `int | str | None` | None |
| `height` | `float | str | None` | None |
| `width` | `float | str | None` | None |
| `size` | `float | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `padding` | `float | str | Spacing | None` | None |
| `margin` | `float | str | Spacing | None` | None |
| `border` | `int | Border | Borders | None` | None |
| `radius` | `2xs | xs | sm | md | lg | xl | 2xl | 3xl | 4xl | full | 100% | none | None` | None |
| `background` | `str | ThemeColor | None` | None |
| `aspectRatio` | `float | str | None` | None |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Form` | 'Form' |
| `onSubmitAction` | `ActionConfig | None` | None |
| `direction` | `row | col | None` | None |

## Icon

Icon component referencing a built-in icon name.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Icon` | 'Icon' |
| `name` | `WidgetIcon` | |
| `color` | `str | ThemeColor | None` | None |
| `size` | `xs | sm | md | lg | xl | 2xl | 3xl | None` | None |

## Image

Image component with sizing and fitting controls.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Image` | 'Image' |
| `src` | `str` | |
| `alt` | `str | None` | None |
| `fit` | `cover | contain | fill | scale-down | none | None` | None |
| `position` | `top left | top | top right | left | center | right | bottom left | bottom | bottom right | None` | None |
| `radius` | `2xs | xs | sm | md | lg | xl | 2xl | 3xl | 4xl | full | 100% | none | None` | None |
| `frame` | `bool | None` | None |
| `flush` | `bool | None` | None |
| `height` | `int | str | None` | None |
| `width` | `int | str | None` | None |
| `size` | `int | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `margin` | `int | str | Spacing | None` | None |
| `background` | `str | ThemeColor | None` | None |
| `aspectRatio` | `float | str | None` | None |
| `flex` | `int | str | None` | None |

## Input

Single-line text input component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Input` | 'Input' |
| `name` | `str` | |
| `inputType` | `number | email | text | password | tel | url | None` | None |
| `defaultValue` | `str | None` | None |
| `required` | `bool | None` | None |
| `pattern` | `str | None` | None |
| `placeholder` | `str | None` | None |
| `allowAutofillExtensions` | `bool | None` | None |
| `autoSelect` | `bool | None` | None |
| `autoFocus` | `bool | None` | None |
| `disabled` | `bool | None` | None |
| `variant` | `soft | outline | None` | None |
| `size` | `3xs | 2xs | xs | sm | md | lg | xl | 2xl | 3xl | None` | None |
| `gutterSize` | `2xs | xs | sm | md | lg | xl | None` | None |
| `pill` | `bool | None` | None |

## Label

Form label associated with a field.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Label` | 'Label' |
| `value` | `str` | |
| `fieldName` | `str` | |
| `size` | `xs | sm | md | lg | xl | None` | None |
| `weight` | `normal | medium | semibold | bold | None` | None |
| `textAlign` | `start | center | end | None` | None |
| `color` | `str | ThemeColor | None` | None |

## ListView

Container component for rendering collections of list items.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `ListView` | 'ListView' |
| `children` | `list[ListViewItem]` | |
| `limit` | `int | auto | None` | None |
| `status` | `WidgetStatusWithFavicon | WidgetStatusWithIcon | None` | None |
| `theme` | `light | dark | None` | None |

## ListViewItem

Single row inside a ``ListView`` component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `ListViewItem` | 'ListViewItem' |
| `children` | `list['WidgetComponent']` | |
| `onClickAction` | `ActionConfig | None` | None |
| `gap` | `int | str | None` | None |
| `align` | `start | center | end | baseline | stretch | None` | None |

## Markdown

Widget rendering Markdown content, optionally streamed.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Markdown` | 'Markdown' |
| `value` | `str` | |
| `streaming` | `bool | None` | None |

## RadioGroup

Grouped radio input control.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `RadioGroup` | 'RadioGroup' |
| `name` | `str` | |
| `options` | `list[RadioOption] | None` | None |
| `ariaLabel` | `str | None` | None |
| `onChangeAction` | `ActionConfig | None` | None |
| `defaultValue` | `str | None` | None |
| `direction` | `row | col | None` | None |
| `disabled` | `bool | None` | None |
| `required` | `bool | None` | None |

## Row

Horizontal flex container.

| Field | Type | Default |
| --- | --- | --- |
| `children` | `list['WidgetComponent'] | None` | None |
| `align` | `start | center | end | baseline | stretch | None` | None |
| `justify` | `start | center | end | between | around | evenly | stretch | None` | None |
| `wrap` | `nowrap | wrap | wrap-reverse | None` | None |
| `flex` | `int | str | None` | None |
| `gap` | `int | str | None` | None |
| `height` | `float | str | None` | None |
| `width` | `float | str | None` | None |
| `size` | `float | str | None` | None |
| `minHeight` | `int | str | None` | None |
| `minWidth` | `int | str | None` | None |
| `minSize` | `int | str | None` | None |
| `maxHeight` | `int | str | None` | None |
| `maxWidth` | `int | str | None` | None |
| `maxSize` | `int | str | None` | None |
| `padding` | `float | str | Spacing | None` | None |
| `margin` | `float | str | Spacing | None` | None |
| `border` | `int | Border | Borders | None` | None |
| `radius` | `2xs | xs | sm | md | lg | xl | 2xl | 3xl | 4xl | full | 100% | none | None` | None |
| `background` | `str | ThemeColor | None` | None |
| `aspectRatio` | `float | str | None` | None |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Row` | 'Row' |

## Select

Select dropdown component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Select` | 'Select' |
| `name` | `str` | |
| `options` | `list[SelectOption]` |  |
| `onChangeAction` | `ActionConfig | None` | None |
| `placeholder` | `str | None` | None |
| `defaultValue` | `str | None` | None |
| `variant` | `solid | soft | outline | ghost | None` | None |
| `size` | `3xs | 2xs | xs | sm | md | lg | xl | 2xl | 3xl | None` | None |
| `pill` | `bool | None` | None |
| `block` | `bool | None` | None |
| `clearable` | `bool | None` | None |
| `disabled` | `bool | None` | None |

## Spacer

Flexible spacer used to push content apart.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Spacer` | 'Spacer' |
| `minSize` | `int | str | None` | None |

## Text

Widget rendering plain text with typography controls.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Text` | 'Text' |
| `value` | `str` | |
| `streaming` | `bool | None` | None |
| `italic` | `bool | None` | None |
| `lineThrough` | `bool | None` | None |
| `color` | `str | ThemeColor | None` | None |
| `weight` | `normal | medium | semibold | bold | None` | None |
| `width` | `float | str | None` | None |
| `size` | `xs | sm | md | lg | xl | None` | None |
| `textAlign` | `start | center | end | None` | None |
| `truncate` | `bool | None` | None |
| `minLines` | `int | None` | None |
| `maxLines` | `int | None` | None |
| `editable` | `False | EditableProps | None` | None |

## Textarea

Multiline text input component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Textarea` | 'Textarea' |
| `name` | `str` |  |
| `defaultValue` | `str | None` | None |
| `required` | `bool | None` | None |
| `pattern` | `str | None` | None |
| `placeholder` | `str | None` | None |
| `autoSelect` | `bool | None` | None |
| `autoFocus` | `bool | None` | None |
| `disabled` | `bool | None` | None |
| `variant` | `soft | outline | None` | None |
| `size` | `3xs | 2xs | xs | sm | md | lg | xl | 2xl | 3xl | None` | None |
| `gutterSize` | `2xs | xs | sm | md | lg | xl | None` | None |
| `rows` | `int | None` | None |
| `autoResize` | `bool | None` | None |
| `maxRows` | `int | None` | None |
| `allowAutofillExtensions` | `bool | None` | None |

## Title

Widget rendering prominent headline text.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Title` | 'Title' |
| `value` | `str` |  |
| `color` | `str | ThemeColor | None` | None |
| `weight` | `normal | medium | semibold | bold | None` | None |
| `size` | `sm | md | lg | xl | 2xl | 3xl | 4xl | 5xl | None` | None |
| `textAlign` | `start | center | end | None` | None |
| `truncate` | `bool | None` | None |
| `maxLines` | `int | None` | None |

## Transition

Wrapper enabling transitions for a child component.

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str | None` | None |
| `id` | `str | None` | None |
| `type` | `Transition` | 'Transition' |
| `children` | `WidgetComponent | None` |  |

