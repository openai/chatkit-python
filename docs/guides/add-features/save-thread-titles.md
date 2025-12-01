# Save thread titles

Threads start untitled. Give them short titles so inboxes and client lists stay readable.

## Save a title

Update `thread.title` and call `store.save_thread(thread, context=...)`. Do this inside your streaming pipeline so ChatKit can emit the resulting `ThreadUpdatedEvent` to connected clients.

```python
class MyChatKitServer(ChatKitServer[RequestContext]):
    async def respond(...):
        ...
        if not thread.title:
            thread.title = "My Thread Title" 
            await self.store.save_thread(thread, context=context)
```

If your integration writes titles elsewhere (for example, a separate FastAPI route that calls `store.save_thread` directly), have the client call `chatkit.fetchUpdates()` command afterward to pull the latest thread metadata.


## Auto-generate a title

Generate a concise title after the first assistant turn once you have enough context. Skip if the thread already has a title or if there isn’t enough content to summarize.

```python
class MyChatKitServer(ChatKitServer[RequestContext]):
    async def respond(...):
        updating_thread_title = asyncio.create_task(
            self._maybe_update_thread_title(thread, item, context)
        )

        # Stream your main response
        async for event in stream_agent_response(agent_context, result):
            yield event

        # Await so the title update streams back as a ThreadUpdatedEvent
        await updating_thread_title

    async def _maybe_update_thread_title(self, thread: ThreadMetadata, context: RequestContext):
        if thread.title is not None:
            return
        items = await self.store.load_thread_items(
            thread.id, after=None, limit=6, order="desc", context=context
        )
        thread.title = await generate_short_title(items.data) # your model call
        await self.store.save_thread(thread, context=context)
```

Use any model call you like for `generate_short_title`: run a tiny Agent, a simple completion, or your own heuristic. Keep titles brief (for example, 3–6 words).
