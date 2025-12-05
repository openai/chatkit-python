# Handle widget actions

Actions let widget interactions trigger server or client logic without posting a chat message.

## Define actions in your widget definition

Configure actions as part of the widget definition while you design it in <https://widgets.chatkit.studio>. Add an action to any action-capable component such as `Button.onClickAction`; explore supported components [here](https://widgets.chatkit.studio/components). The exported `.widget` file already includes the action object, so loading the template is enough for ChatKit to send it.

```jsx
<Button
    label="Send message"
    onClickAction={{
        type: "send_message",
        payload: { text: "Ping support" },
    }}
/>
```

## Choose client vs server handling

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

## Handle actions on the server

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
                generate_id=lambda item_type: self.store.generate_item_id(item_type, thread, context),
            ):
                yield event
```

Treat action payloads as untrusted input from the client.

## Handle actions on the client

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
                payload: { ...result, user_id: action.payload.user_id },
            },
            widgetItem.id,
        );
      }
    },
  },
});
```

On the server, handle the follow-up action (`save_profile_complete`) in the `action` method to stream refreshed widgets or messages.

## Customize how actions interact with loading states in widgets

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
| `auto`      | The action will adapt to how it’s being used. (_default_)                                                                       |
| `self`      | The action triggers loading state on the widget node that the action was bound to.                                              |
| `container` | The action triggers loading state on the entire widget container. This causes the widget to fade out slightly and become inert. |
| `none`      | No loading state                                                                                                                |

### Using `auto` behavior

Generally, we recommend using `auto`, which is the default. `auto` triggers loading states based on where the action is bound, for example:

- `Button.onClickAction` → `self`
- `Select.onChangeAction` → `none`
- `Card.confirm.action` → `container`
