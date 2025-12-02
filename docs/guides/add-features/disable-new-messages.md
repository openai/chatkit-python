# Disable new messages for a thread

There are two ways to stop new user messages: temporarily lock a thread or permanently close it when the conversation is finished.

| State   | When to use                                    | Input UI                                       | What the user sees |
|---------|------------------------------------------------|------------------------------------------------|--------------------|
| Locked  | Temporary pause for moderation or admin action | Composer stays on screen but is disabled; the placeholder shows the lock reason. | The reason for the lock in the disabled composer. |
| Closed  | Final state when the conversation is done      | The input UI is replaced with an informational banner.                  | A static default message or a custom reason, if provided. |

## Update thread status (lock, close, or re-open)

Update `thread.status`—whether moving between active, locked, or closed—and persist it.

```python
from chatkit.types import ActiveStatus, LockedStatus, ClosedStatus

# lock
thread.status = LockedStatus(reason="Escalated to support.")
await store.save_thread(thread, context=context)

# close (final)
thread.status = ClosedStatus(reason="Resolved.")
await store.save_thread(thread, context=context)

# re-open
thread.status = ActiveStatus()
await store.save_thread(thread, context=context)
```

If you update the thread status within the `respond` method, ChatKit will emit a `ThreadUpdatedEvent` so connected clients update immediately.

You can also update the thread status from a custom client-facing endpoint that updates the store directly (outside of the ChatKit server request flow). If the user is currently viewing the thread, have the client call `chatkit.fetchUpdates()` after the status is persisted so the UI picks up the latest thread state.

## Block server-side work when locked or closed

Thread status only affects the composer UI; ChatKitServer does not automatically reject actions, tool calls, or imperative message adds. Your integration should short-circuit handlers when a thread is disabled:

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

