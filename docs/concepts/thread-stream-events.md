# Thread stream events

[`ThreadStreamEvent`](../../api/chatkit/types/#chatkit.types.ThreadStreamEvent)s are the Server-Sent Event (SSE) payloads streamed by ChatKitServer while responding to a user message or action. They keep the client UI in sync with server-side processing and drive persistence in your store.

## Thread metadata updates

ChatKitServer emits these after it creates a thread or notices metadata changes (title, status, etc.) so the UI stays in sync.

- [`ThreadCreatedEvent`](../../api/chatkit/types/#chatkit.types.ThreadCreatedEvent): introduce a new thread
- [`ThreadUpdatedEvent`](../../api/chatkit/types/#chatkit.types.ThreadUpdatedEvent): update the current thread metadata such as title or status

## Thread item events

Thread item events drive the conversation state. ChatKitServer processes these events to persist conversation state before streaming them back to the client.

- [`ThreadItemAddedEvent`](../../api/chatkit/types/#chatkit.types.ThreadItemAddedEvent): introduce a new item (message, tool call, workflow, widget, etc).
- [`ThreadItemUpdatedEvent`](../../api/chatkit/types/#chatkit.types.ThreadItemUpdatedEvent): mutate a pending item (e.g., stream text deltas, workflow task updates).
- [`ThreadItemDoneEvent`](../../api/chatkit/types/#chatkit.types.ThreadItemDoneEvent): mark an item complete and persist it.
- [`ThreadItemRemovedEvent`](../../api/chatkit/types/#chatkit.types.ThreadItemRemovedEvent): delete an item by id.
- [`ThreadItemReplacedEvent`](../../api/chatkit/types/#chatkit.types.ThreadItemReplacedEvent): swap an item in place.

Note: `ThreadItemAddedEvent` does not persist the item. `ChatKitServer` saves on `ThreadItemDoneEvent`/`ThreadItemReplacedEvent`, tracks pending items in between, and handles store writes for all `ThreadItem*Event`s.

## Errors

Stream [`ErrorEvent`](../../api/chatkit/types/#chatkit.types.ErrorEvent)s for user-facing errors in the chat UI. You can configure a custom message and whether a retry button is shown to the user.

## Progress updates

Stream [`ProgressUpdateEvent`](../../api/chatkit/types/#chatkit.types.ProgressUpdateEvent)s to show the user transient status while work is in flight.

See [Show progress for long-running tools](../guides/show-progress-for-long-running-tools.md) for more info.

## Client effects

Use [`ClientEffectEvent`](../../api/chatkit/types/#chatkit.types.ClientEffectEvent) to trigger fire-and-forget behavior on the client such as opening a dialog or pushing updates.

See [Send client effects](../guides/send-client-effects.md) for more info.

## Stream options

[`StreamOptionsEvent`](../../api/chatkit/types/#chatkit.types.StreamOptionsEvent) configures runtime stream behavior (for example, allowing user cancellation). `ChatKitServer` emits one at the start of every stream using `get_stream_options`; override that method to change defaults such as `allow_cancel`.


## Related guides
- [Stream responses back to your user](../guides/stream-thread-events.md)
