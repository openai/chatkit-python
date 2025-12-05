# Build interactive responses with widgets

Use widgets to turn assistant responses into rich, interactive UIs. Design widgets visually, hydrate them with data on the server, stream them into the conversation, and wire actions and forms so users can click, edit, and submit without writing long free-text prompts.

This guide covers:

- Designing and loading widget templates
- Streaming widgets from `respond` and from tools
- Handling widget actions on the server and client
- Building editable forms with widgets

## Design widgets in ChatKit Studio

Use <https://widgets.chatkit.studio> to visually design cards, lists, forms, charts, and other widget components. Populate the **Data** panel with sample values to preview how the widget renders with real inputs.

When the layout and bindings look correct, click **Export** to download the generated `.widget` file. Commit this file alongside the server code that builds and renders the widget.

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
        generate_id=lambda item_type: self.store.generate_item_id(
            item_type, thread, context
        ),
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

## Stream widget updates while text streams

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
    message_result = Runner.run_streamed(
        message_generator, "Draft a message to Harry."
    )

    async def widget_generator() -> AsyncGenerator[WidgetRoot, None]:
        message = ""
        async for event in message_result.stream_events():
            if (
                event.type == "raw_response_event"
                and event.data.type == "response.output_text.delta"
            ):
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

## Handle widget actions

Actions let widget interactions trigger server or client logic without posting a chat message.

### Define actions in your widget

Configure actions as part of the widget definition while you design it in <https://widgets.chatkit.studio>. Add an action to any action-capable component such as `Button.onClickAction`; explore supported components on the components page.

```jsx
<Button
  label="Send message"
  onClickAction={{
    type: "send_message",
    payload: { text: "Ping support" },
  }}
/>
```

### Choose client vs server handling

Actions are handled on the server by default and flow into `ChatKitServer.action`. Set `handler: "client"` in the action to route it to your frontend’s `widgets.onAction` instead. Use the server when you need to update thread state or stream widgets; use the client for immediate UI work or to chain into a follow-up `sendCustomAction` after local logic completes.

Example widget definition with a client action handler:

```jsx
<Button
  label="Send message"
  onClickAction={{
    type: "send_message",
    handler: "client",
    payload: { text: "Ping support" },
  }}
/>
```

### Handle actions on the server

Implement `ChatKitServer.action` to process incoming actions. The `sender` argument is the widget item that triggered the action (if available).

```python
from datetime import datetime

from chatkit.server import ChatKitServer, stream_widget
from chatkit.types import HiddenContextItem, WidgetItem


class MyChatKitServer(ChatKitServer[RequestContext]):
    async def action(self, thread, action, sender, context):
        if action.type == "send_message":
            await send_to_chat(action.payload["text"])

            # Record the user action so the model can see it on the next turn.
            hidden = HiddenContextItem(
                id="generated-item-id",
                thread_id=thread.id,
                created_at=datetime.now(),
                content=f"User sent message: {action.payload['text']}",
            )
            # HiddenContextItems need to be manually saved because ChatKitServer
            # only auto-saves streamed items, and HiddenContextItem should never be streamed to the client.
            await self.store.add_thread_item(thread.id, hidden, context)

            # Stream an updated widget back to the client.
            updated_widget = build_message_widget(text=action.payload["text"])
            async for event in stream_widget(
                thread,
                updated_widget,
                generate_id=lambda item_type: self.store.generate_item_id(
                    item_type, thread, context
                ),
            ):
                yield event
```

Treat action payloads as untrusted input from the client.

### Handle actions on the client

Provide [`widgets.onAction`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/widgetsoption) when creating ChatKit on the client; you can still forward follow-up actions to the server from your `onAction` callback with the `sendCustomAction()` command if needed.

```ts
const chatkit = useChatKit({
  // ...
  widgets: {
    onAction: async (action, widgetItem) => {
      if (action.type === "save_profile") {
        const result = await saveProfile(action.payload);

        // Optionally invoke a server action after client-side work completes.
        await chatkit.sendCustomAction(
          {
            type: "save_profile_complete",
            payload: {...result, user_id: action.payload.user_id},
          },
          widgetItem.id,
        );
      }
    },
  },
});
```

On the server, handle the follow-up action (`save_profile_complete`) in the `action` method to stream refreshed widgets or messages.

### Control loading behavior

Use `loadingBehavior` to control how actions trigger different loading states in a widget.

```jsx
<Button
  label="Send message"
  onClickAction={{
    type: "send_message",
    loadingBehavior: "container",
  }}
/>
```

| Value       | Behavior                                                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `auto`      | The action will adapt to how it’s being used. (_default_)                                                                      |
| `self`      | The action triggers loading state on the widget node that the action was bound to.                                             |
| `container` | The action triggers loading state on the entire widget container. This causes the widget to fade out slightly and become inert. |
| `none`      | No loading state                                                                                                               |

Generally, we recommend using `auto`, which is the default. `auto` triggers loading states based on where the action is bound, for example:

- `Button.onClickAction` → `self`
- `Select.onChangeAction` → `none`
- `Card.confirm.action` → `container`

## Create custom forms with widgets

Wrap widgets that collect user input in a `Form` to have their values automatically injected into every action triggered inside that form. The form values arrive in the action payload, keyed by each field’s `name`.

- `<Select name="title" />` → `action.payload["title"]`
- `<Select name="todo.title" />` → `action.payload["todo"]["title"]`

```jsx
<Form
  direction="col"
  onSubmitAction={{
    type: "update_todo",
    payload: { id: todo.id },
  }}
>
  <Title value="Edit Todo" />
  <Text value="Title" color="secondary" size="sm" />
  <Text
    value={todo.title}
    editable={{ name: "title", required: true }}
  />
  <Text value="Description" color="secondary" size="sm" />
  <Text
    value={todo.description}
    editable={{ name: "description" }}
  />
  <Button label="Save" submit />
</Form>
```

On the server, read the form values from the action payload. Any action originating from inside the form will include the latest field values.

```python
from collections.abc import AsyncIterator

from chatkit.server import ChatKitServer
from chatkit.types import Action, ThreadMetadata, ThreadStreamEvent, WidgetItem


class MyChatKitServer(ChatKitServer[RequestContext]):
    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        if action.type == "update_todo":
            todo_id = action.payload["id"]
            # Any action that originates from within the Form will
            # include title and description
            title = action.payload["title"]
            description = action.payload["description"]

            # ...
```

### Validation

`Form` uses basic native form validation; it enforces `required` and `pattern` on configured fields and blocks submission when any field is invalid.

We may add new validation modes with better UX, more expressive validation, and custom error display. Until then, widgets are not a great medium for complex forms with tricky validation. If you need this, a better pattern is to use client-side action handling to trigger a modal, show a custom form there, then pass the result back into ChatKit with `sendCustomAction`.

### Treating `Card` as a `Form`

You can pass `asForm=True` to `Card` and it will behave as a `Form`, running validation and passing collected fields to the Card’s `confirm` action.

### Payload key collisions

If there is a naming collision with some other existing pre-defined key on your payload, the form value will be ignored. This is probably a bug, so we’ll emit an `error` event when we see this.


