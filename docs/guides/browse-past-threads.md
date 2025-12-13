# Let users browse past threads

Let users return to previous conversations, see readable titles in a history list, and decide which threads can be continued.

## Enable thread history in the client

The ChatKit React hooks support a built-in history view that lists past threads. History is enabled by default, but you can configure it explicitly when you create your ChatKit controller:

```tsx
const chatkit = useChatKit({
  // ...
  history: {
    enabled: true,
    showDelete: true,
    showRename: true,
  },
});
```

With `history.enabled: true`, ChatKit.js will:

- Fetch threads from your ChatKit server.
- Show them in a history list using `thread.title` when available.
- Let users click a past thread to load its items and continue the conversation.
- Let users delete and rename threads.

Set `history.enabled: false` if you want a single-thread, stateless chat experience with no history UI.

## Show readable titles in history

Threads start untitled. Give them short, descriptive titles so the history list is easy to scan.

### Set a title directly

Set `thread.title` on the server and persist it with your store:

```python
from chatkit.server import ChatKitServer


class MyChatKitServer(ChatKitServer[RequestContext]):
    async def respond(...):
        ...
        if not thread.title:
            thread.title = "Order #1234"
            await self.store.save_thread(thread, context=context)
```

ChatKit will emit a `ThreadUpdatedEvent` so connected clients update the title in their history views.

### Auto-generate a title after the first turn

Generate a concise title after the first assistant turn once you have enough context. Skip if the thread already has a title or if there isn’t enough content to summarize.

```python
class MyChatKitServer(ChatKitServer[RequestContext]):
    async def respond(...):
        updating_thread_title = asyncio.create_task(
            self._maybe_update_thread_title(thread, context)
        )

        # Stream your main response
        async for event in stream_agent_response(agent_context, result):
            yield event

        # Await so the title update streams back as a ThreadUpdatedEvent
        await updating_thread_title

    async def _maybe_update_thread_title(
        self, thread: ThreadMetadata, context: RequestContext
    ) -> None:
        if thread.title is not None:
            return
        items = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=6,
            order="desc",
            context=context,
        )
        thread.title = await generate_short_title(items.data)  # your model call
        await self.store.save_thread(thread, context=context)
```

Use any model call you like for `generate_short_title`: run a tiny Agent, a simple completion, or your own heuristic. Keep titles brief (for example, 3–6 words).

## Decide which threads can be continued

By default, users can continue any past thread: selecting it in the history view loads its items and reuses the same thread when they send a new message.

Use `thread.status` to mark conversations that should no longer accept new messages. Locked and closed threads still appear in history, but the composer UI changes.

There are two ways to stop new user messages: temporarily lock a thread or permanently close it when the conversation is finished.

| State   | When to use                                    | Input UI                                       | What the user sees |
|---------|------------------------------------------------|------------------------------------------------|--------------------|
| Locked  | Temporary pause for moderation or admin action | Composer stays on screen but is disabled; the placeholder shows the lock reason. | The reason for the lock in the disabled composer. |
| Closed  | Final state when the conversation is done      | The input UI is replaced with an informational banner.                  | A static default message or a custom reason, if provided. |

### Update thread status (lock, close, or re-open)


```python
from chatkit.types import ActiveStatus, LockedStatus, ClosedStatus

# lock (temporary pause)
thread.status = LockedStatus(reason="Escalated to support.")
await store.save_thread(thread, context=context)

# close (final state)
thread.status = ClosedStatus(reason="Resolved.")
await store.save_thread(thread, context=context)

# re-open
thread.status = ActiveStatus()
await store.save_thread(thread, context=context)
```

When you persist a new status during `respond`, ChatKit emits a `ThreadUpdatedEvent` so all viewers see the updated state.

You can also update the thread status from a custom client-facing endpoint that updates the store directly (outside of the ChatKit server request flow). If the user is currently viewing the thread, have the client call `chatkit.fetchUpdates()` after the status is persisted so the UI picks up the latest thread state.

### Block server-side work when locked or closed

Thread status only affects the composer UI; `ChatKitServer` does not automatically reject actions, tool calls, or imperative message adds. Your integration should short-circuit handlers when a thread is disabled:

```python
class MyChatKitServer(...):
    async def respond(thread, input_user_message, context):
        if thread.status.type in {"locked", "closed"}:
            return
        # normal processing

    async def action(thread, action, sender, context):
        if thread.status.type in {"locked", "closed"}:
            return
        # normal processing
```

