# Stream responses back to your user

ChatKit.js listens for [`ThreadStreamEvent`](../../api/chatkit/types/#chatkit.types.ThreadStreamEvent)s over SSE. Stream events from [`ChatKitServer.respond`](../../api/chatkit/server/#chatkit.server.ChatKitServer.respond) so users see model output, tool activity, progress updates, and errors in real time.

Thread stream events include both persistent thread items (messages, tools, workflows) that are saved to the conversation history, and non-persistent runtime signals (progress updates, notices, errors, and client effects) that show ephemeral UI or drive immediate client behavior without being stored.

See [Thread stream events](../concepts/thread-stream-events.md) for an overview of supported event types.

### From `respond`

`stream_agent_response` converts a streamed Agents SDK run into ChatKit events. Yield those events directly from `respond`, or yield any `ThreadStreamEvent` yourself—the server processes them the same way.

Example using `stream_agent_response` with a run result:

```python
class MyChatKitServer(ChatKitServer[MyRequestContext]):
    async def respond(...) -> AsyncIterator[ThreadStreamEvent]:
        # Build model inputs and agent context as shown in previous guides.

        result = Runner.run_streamed(...)
        async for event in stream_agent_response(agent_context, result):
            yield event
```

### From tools

Server tools enqueue events with the `AgentContext` helpers; `stream_agent_response` drains and forwards them.

Example emitting an ephemeral progress update event during a tool call:

```python
@function_tool()
async def long_running_tool(ctx: RunContextWrapper[AgentContext]):
    await ctx.context.stream(ProgressUpdateEvent(text="Working..."))

    # Tool logic omitted for brevity
```

### Handle guardrail triggers

Guardrail tripwires raise `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered` once partial assistant output has been rolled back. Catch them around `stream_agent_response` and optionally send a user-facing event so the client knows why the turn stopped.

```python
from agents import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from chatkit.types import ErrorEvent

try:
    async for event in stream_agent_response(agent_context, result):
        yield event
except InputGuardrailTripwireTriggered:
    yield ErrorEvent(message="We blocked that message for safety.")
except OutputGuardrailTripwireTriggered:
    yield ErrorEvent(
        message="The assistant response was blocked.",
        allow_retry=False,
    )
```

## Stream events without `stream_agent_response`

You can bypass the Agents SDK helper and yield `ThreadStreamEvent`s directly from `respond`. ChatKitServer will persist and route them the same way.

```python
class MyChatKitServer(ChatKitServer[MyRequestContext]):
    async def respond(...) -> AsyncIterator[ThreadStreamEvent]:
        # Example transient progress update
        yield ProgressUpdateEvent(
            icon="search",
            text="Searching..."
        )

        # Run your inference pipeline here
        output = await run_inference(thread, input, context)

        # Stream a persisted assistant message
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                thread_id=thread.id,
                id=self.store.generate_item_id("message", thread, context),
                created_at=datetime.now(),
                content=[AssistantMessageContent(text=output)],
            )
        )
```

When you stream events manually, remember that tools cannot `yield` events. If you skip `stream_agent_response`, you must merge any tool-emitted events yourself—for example, by reading from `AgentContext._events` (populated by `ctx.context.stream(...)` or workflow helpers) and interleaving them with your own `respond` events.


## Next

Add features:

* [Save thread titles](add-features/save-thread-titles.md)
* [Accept attachments](add-features/accept-attachments.md)
* [Make client tool calls](add-features/make-client-tool-calls.md)
* [Send client effects](add-features/send-client-effects.md)
* [Show progress for long-running tools](add-features/show-progress-for-long-running-tools.md)
* [Stream widgets](add-features/stream-widgets.md)
* [Handle widget actionss](add-features/handle-widget-actions.md)
* [Create custom forms](add-features/create-custom-forms.md)
* [Handle feedback](add-features/handle-feedback.md)
* [Allow @-mentions in user messages](add-features/allow-mentions.md)
* [Add annotations in assistant messages](add-features/add-annotations.md)
* [Disable new messages for a thread](add-features/disable-new-messages.md)
