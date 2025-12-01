# Stream widgets

Widgets are rich UI components that can be displayed in chat. Design .widget files in <https://widgets.chatkit.studio>, load them as WidgetTemplates, inject dynamic data to build widgets, and stream the rendered widgets as `WidgetItem`s to clients from the `respond` or `action` ChatKitServer methods or from tool calls.

## Design widgets

Use <https://widgets.chatkit.studio> to visually design cards, lists, forms, charts, and other widget components. Populate the **Data** panel with sample values to preview how the widget renders with real inputs.

When the layout and bindings look correct, click **Export** to download the generated `.widget` file. Commit this file alongside the server code that builds and renders the widget.

For wiring user interactions and handling widget actions on the server, see [Handle widget actions](handle-widget-actions.md).

## Build widgets with `WidgetTemplate`

Load the `.widget` file with `WidgetTemplate.from_file` and hydrate it with runtime data. Placeholders inside the `.widget` template (Jinja-style `{{ }}` expressions) are rendered before the widget is streamed.

```python
from chatkit.widgets import WidgetTemplate

message_template = WidgetTemplate.from_file("widgets/channel_message.widget")

def build_message_widget(user_name: str, message: str):
    # Replace this helper with whatever your integration uses to build widgets.
    return message_template.build(
        {
            "user_name": user_name,
            "message": message,
        }
    )
```

`WidgetTemplate.build` accepts plain dicts or Pydantic models. Use `.build_basic` if you're working with a `BasicRoot` widget outside of streaming.

## Stream widgets from `respond`

Use `stream_widget` to emit a one-off widget or stream updates from an async generator.

```python
from chatkit.server import stream_widget

async def respond(...):
    user_name = "Harry Potter"
    message = "Yer a wizard, Harry"
    message_widget = build_message_widget(user_name=user_name, message=message)
    async for event in stream_widget(
        thread,
        message_widget,
        copy_text=f"Message to {user_name}: {message}",
        generate_id=lambda item_type: self.store.generate_item_id(item_type, thread, context),
    ):
        yield event
```

To stream gradual updates, yield successive widget states from an async generator; `stream_widget` diffs and emits `ThreadItemUpdatedEvent`s for you.

## Stream widgets from tools

Tools can enqueue widgets via `AgentContext.stream_widget`; `stream_agent_response` forwards them to the client.

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext

@function_tool(description_override="Display a sample widget to the user.")
async def sample_widget(ctx: RunContextWrapper[AgentContext]):
    message_widget = build_message_widget(...)
    await ctx.context.stream_widget(message_widget)
```

## Stream widget updates

The examples above return a fully completed static widget. You can also stream an updating widget by yielding new versions of the widget from a generator function. The ChatKit framework will send updates for the parts of the widget that have changed.

!!! note "Text streaming support"
    Currently, only `<Text>` and `<Markdown>` components marked with an `id` have their text updates streamed. Other diffs will forgo the streaming UI and replace and rerender parts of the widget client-side.

```python
from typing import AsyncGenerator

from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext, Runner
from chatkit.widgets import WidgetRoot

@function_tool
async def draft_message_to_harry(ctx: RunContextWrapper[AgentContext]):
    # message_generator is your model/tool function that streams text
    message_result = Runner.run_streamed(message_generator, "Draft a message to Harry.")

    async def widget_generator() -> AsyncGenerator[WidgetRoot, None]:
        message = ""
        async for event in message_result.stream_events():
            if event.type == "raw_response_event" and event.data.type == "response.output_text.delta":
                message += event.data.delta
                yield build_message_widget(
                    user_name="Harry Potter",
                    message=message,
                )

        # Final render after streaming completes.
        yield build_message_widget(
            user_name="Harry Potter",
            message=message,
        )

    await ctx.context.stream_widget(widget_generator())
```

The inner generator collects the streamed text events and rebuilds the widget with the latest message so the UI updates incrementally.
