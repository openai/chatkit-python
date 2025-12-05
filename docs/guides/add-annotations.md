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

Inline annotations are not yet supported for entity sources, but you can still attach `EntitySource` items as annotations so they appear in the Sources list below the message.

```python
from datetime import datetime
from chatkit.types import (
    Annotation,
    AssistantMessageContent,
    AssistantMessageItem,
    EntitySource,
    ThreadItemDoneEvent,
)

annotations = [
    Annotation(
        source=EntitySource(
            id="customer_123",
            title="ACME Corp",
            description="Enterprise plan · 500 seats",
            icon="suitcase",
            data={"href": "https://crm.example.com/customers/123"},
        )
    )
]

yield ThreadItemDoneEvent(
    item=AssistantMessageItem(
        id=self.store.generate_item_id("message", thread, context),
        thread_id=thread.id,
        created_at=datetime.now(),
        content=[
            AssistantMessageContent(
                text="Here are the ACME account details for reference.",
                annotations=annotations,
            )
        ],
    )
)
```

Provide richer previews and navigation by handling [`entities.onRequestPreview`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onrequestpreview) and [`entities.onClick`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onclick) in ChatKit.js, using the `data` payload to pass entity information and deep link into your app.
