# Threads

Threads are the core unit of ChatKit: a single conversation timeline that groups messages, tool calls, widgets, and related metadata.

## Lifecycle
- When a user submits a message and no thread exists, `ChatKitServer` creates one by calling your store's [`save_thread`](../../api/chatkit/store/#chatkit.store.Store.save_thread).
- As responses stream back, `ChatKitServer` automatically persists thread items as they are completed—see [Thread items](thread-items.md) and [Stream responses back to your user](../guides/stream-thread-events.md) for how events drive storage.
- Update titles or metadata intentionally in your integration (e.g., after summarizing a topic) by calling [`store.save_thread`](../../api/chatkit/store/#chatkit.store.Store.save_thread) with the new values.
- When history is enabled client-side, ChatKit retrieves past threads. The user can continue any previous thread by default.
- Archive or close threads according to your policies: mark them read-only (e.g., [disable new messages](../guides/add-features/disable-new-messages.md)) or delete them if you no longer want them discoverable.


## Related guides
- [Persist ChatKit threads and messages](../guides/persist-chatkit-data.md)
- [Save thread titles](../guides/add-features/save-thread-titles.md)
- [Disable new messages for a thread](../guides/add-features/disable-new-messages.md)
