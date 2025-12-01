# Stream responses back to your user

ChatKit.js listens for `ThreadStreamEvent`s over SSE. Stream events from `ChatKitServer.respond` so users see model output, tool activity, progress updates, and errors in real time.

Thread events include both persistent thread items (messages, tools, workflows) that are saved to the conversation history, and non-persistent runtime signals (progress updates, notices, errors, and client effects) that show ephemeral UI or drive immediate client behavior without being stored.

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

Example streaming workflow updates using `AgentContext` helpers:

```python
@function_tool()
async def long_running_tool_with_steps(ctx: RunContextWrapper[AgentContext]):
    # Create an empty workflow container
    await ctx.context.start_workflow(Workflow(type="custom", tasks=[]))

    # Add and update the first task
    discovery = CustomTask(title="Search data sources", status_indicator="loading")
    await ctx.context.add_workflow_task(discovery)

    # Run the first task
    await search_my_data_sources()

    await ctx.context.update_workflow_task(
        discovery.model_copy(update={"status_indicator": "complete"}), task_index=0
    )

    # Add a follow-up task
    summary = CustomTask(title="Summarize findings", status_indicator="loading")
    await ctx.context.add_workflow_task(summary)

    # Run the second task
    await summarize_my_findings()

    await ctx.context.update_workflow_task(
        summary.model_copy(update={"status_indicator": "complete"}), task_index=1
    )

    # Close the workflow and collapse it in the UI
    await ctx.context.end_workflow(
        summary=CustomSummary(title="Analysis complete"),
        expanded=False,
    )
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

When you stream thread events manually, remember that tools cannot `yield` events. If you skip `stream_agent_response`, you must merge any tool-emitted events yourself—for example, by reading from `AgentContext._events` (populated by `ctx.context.stream(...)` or workflow helpers) and interleaving them with your own `respond` events.

## Thread lifecycle events

Thread item events drive the conversation state. ChatKitServer processes these events to persist conversation state before streaming them back to the client.

- `ThreadItemAddedEvent`: introduce a new item (message, tool call, workflow, widget, etc).
- `ThreadItemUpdatedEvent`: mutate a pending item (e.g., stream text deltas, workflow task updates).
- `ThreadItemDoneEvent`: mark an item complete and persist it.
- `ThreadItemRemovedEvent`: delete an item by id.
- `ThreadItemReplacedEvent`: swap an item in place.

Note: `ThreadItemAddedEvent` does not persist the item. `ChatKitServer` saves on `ThreadItemDoneEvent`/`ThreadItemReplacedEvent`, tracks pending items in between, and handles store writes for all `ThreadItem*Event`s.

## Errors

Stream an `ErrorEvent` for user-facing errors.

```python
async def respond(...) -> AsyncIterator[ThreadStreamEvent]:
    if not user_has_remaining_quota(context):
        yield ErrorEvent(
            message="You have reached your usage limit.",
            allow_retry=False,
        )
        return

    # Rest of your respond method
```

## Client effects

Use `ClientEffectEvent` to trigger fire-and-forget behavior on the client such as opening a dialog or pushing updates.

## Stream options

`StreamOptionsEvent` configures runtime stream behavior (for example, allowing user cancellation). `ChatKitServer` emits one at the start of every stream using `get_stream_options`; override that method to change defaults such as `allow_cancel`.

## Next

Add features:

* [Save thread titles](add-features/save-thread-titles.md)
* [Accept attachments](add-features/accept-attachments.md)
* [Make client tool calls](add-features/make-client-tool-calls.md)
* [Send client effects](add-features/send-client-effects.md)
* [Stream widgets](add-features/stream-widgets.md)
* [Handle widget actionss](add-features/handle-widget-actions.md)
* [Create custom forms](add-features/create-custom-forms.md)