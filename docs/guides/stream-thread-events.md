# Stream thread events back to your user

ChatKit.js listens for `ThreadStreamEvent`s over SSE. Stream events from respond so users see model output, tool activity, progress updates, and errors in real time.

Thread events include both persistent thread items (messages, tools, workflows) that are saved to the conversation history, and non-persistent runtime signals (progress updates, notices, errors, and client effects) that drive immediate client behavior without being stored.

## Stream events from `respond`

`stream_agent_response` converts a streamed Agents SDK run into ChatKit events. Yield those events directly from `respond`, or yield any `ThreadStreamEvent` yourself—the server processes them the same way.

```python
async for event in stream_agent_response(agent_context, result):
    yield event
```

You can also stream thread events manually by yielding `ThreadStreamEvent`s directly:

```python
# example manually yielding a Hello, World assistant message
```

When you stream thread events manually, keep in mind that ChatKitServer automatically adds, updates, or deletes thread items for `ThreadItem*Event`s so you do not need to manually save streamed events to store.

## Stream events from tools

Server tools can emit ChatKit events mid-run—progress, widgets, or other thread items—by calling `AgentContext` methods such as `ctx.context.stream`. This keeps the UI responsive even while the tool finishes its work.

```python
@function_tool()
async def long_running_tool(ctx: RunContextWrapper[AgentContext]):
    await ctx.context.stream(ProgressUpdateEvent(text="Working..."))
    # ...do work and return
```

## Show progress updates and workflow items

Use `ProgressUpdateEvent` for transient status updates during long-running work. These updates are not persisted.

For structured, persistent tasks, stream workflow items instead. Use `AgentContext.start_workflow`, `add_workflow_task`, `update_workflow_task`, and `end_workflow` rather than emitting workflow events manually. Workflow items are saved to the thread and restored from history.

## Errors and notices

Raise `NoticeEvent` for user-facing warnings and `ErrorEvent` when the turn should halt or block retries. These can come from `respond` or from tools.

```python
try:
    async for event in stream_agent_response(agent_context, result):
        yield event
except Exception:
    yield ErrorEvent(code=ErrorCode.STREAM_ERROR, allow_retry=True)
```

## Client effects

Use `ClientEffectEvent` to trigger transient client-side behavior—such as opening a dialog or focusing a field—without writing a new thread item. Stream them alongside other events either from `respond` or within a tool call, and keep payloads small so the client can react quickly.

## Stream events when guardrails trigger

Guardrail tripwires raise `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered` once partial assistant output has been rolled back. Catch them around `stream_agent_response` and send a user-facing event so the client knows why the turn stopped.

```python
from agents import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from chatkit.errors import ErrorCode
from chatkit.types import ErrorEvent, NoticeEvent

try:
    async for event in stream_agent_response(agent_context, result):
        yield event
except InputGuardrailTripwireTriggered:
    yield NoticeEvent(level="warning", message="We blocked that message for safety.")
except OutputGuardrailTripwireTriggered:
    yield ErrorEvent(
        code=ErrorCode.STREAM_ERROR,
        message="The assistant response was blocked.",
        allow_retry=False,
    )
```
