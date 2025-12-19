# Add annotations in assistant messages

ChatKit renders clickable inline citations when assistant text includes `annotations` and rolls every reference into a collapsed **Sources** list beneath each message. You can let the model emit annotations directly or attach sources yourself before streaming the message.

## Use model-emitted citations

When you stream a Responses run through `stream_agent_response`, ChatKit automatically converts any `file_citation`, `container_file_citation`, and `url_citation` annotations returned by the OpenAI API into ChatKit `Annotation` objects and attaches them to streamed message content.

Provide the model with citable evidence via tools to receive citation annotations, most commonly:

- `FileSearchTool` for uploaded documents (emits `file_citation` / `container_file_citation`)
- `WebSearchTool` for live URLs (emits `url_citation`)

No additional server-side wiring is required beyond calling `stream_agent_response`. If the model emits citation annotations from tool usage, ChatKit will forward them automatically as `Annotation` objects on the corresponding content parts.


## Attach sources manually

If you build assistant messages yourself, include annotations on each `AssistantMessageContent` item.

```python
from datetime import datetime
from chatkit.types import (
    Annotation,
    AssistantMessageContent,
    AssistantMessageItem,
    FileSource,
    ThreadItemDoneEvent,
    URLSource,
)

text = "Quarterly revenue grew 12% year over year."
annotations = [
    Annotation(
        source=FileSource(filename="q1_report.pdf", title="Q1 Report"),
        index=len(text) - 1,  # attach near the end of the sentence
    ),
    Annotation(
        source=URLSource(
            url="https://example.com/press-release",
            title="Press release",
        ),
        index=len(text) - 1,
    ),
]

yield ThreadItemDoneEvent(
    item=AssistantMessageItem(
        id=self.store.generate_item_id("message", thread, context),
        thread_id=thread.id,
        created_at=datetime.now(),
        content=[AssistantMessageContent(text=text, annotations=annotations)],
    )
)
```

`index` is the character position to place the footnote marker; re-use the same index when multiple citations support the same claim so the footnote numbers stay grouped.

## Annotating with custom entities

You can attach `EntitySource` items as annotations to show entity references inline in assistant text and in the **Sources** list below the message.

Entity annotations support a few UI-focused fields:

- `icon`: Controls the icon shown for the entity in the default inline/hover UI.
- `label`: Customizes what's shown in the default entity hover header (when you are not rendering a custom preview).
- `inline_label`: Shows a label inline instead of an icon.
- `interactive=True`: Wires the annotation to client-side callbacks (`ChatKitOptions.entities.onClick` and `ChatKitOptions.entities.onRequestPreview`).

```python
from datetime import datetime
from chatkit.types import (
    Annotation,
    AssistantMessageContent,
    AssistantMessageItem,
    EntitySource,
    ThreadItemDoneEvent,
)

text = "Here are the ACME account details for reference."

annotations = [
    Annotation(
        source=EntitySource(
            id="customer_123",
            title="ACME Corp",
            description="Enterprise plan · 500 seats",
            icon="suitcase",
            label="Customer",
            interactive=True,
            # Free-form data object passed to your client-side entity callbacks
            data={"href": "https://crm.example.com/customers/123"},
        ),
        # `index` controls where the inline marker is placed in the text.
        index=text.index("ACME") + len("ACME"),
    )
]

yield ThreadItemDoneEvent(
    item=AssistantMessageItem(
        id=self.store.generate_item_id("message", thread, context),
        thread_id=thread.id,
        created_at=datetime.now(),
        content=[
            AssistantMessageContent(
                text=text,
                annotations=annotations,
            )
        ],
    )
)
```

Provide richer previews and navigation by handling [`entities.onRequestPreview`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onrequestpreview) and [`entities.onClick`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onclick) in ChatKit.js. These callbacks are only invoked for entity annotations with `interactive=True`; use the `data` payload to pass entity information and deep link into your app.
