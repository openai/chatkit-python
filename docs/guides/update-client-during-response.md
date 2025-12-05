# Update the client during a response

Keep your UI responsive while the server is working: stream progress text, trigger client-side effects, and run client tools mid-response without blocking everything else.

This guide covers three patterns:

- Progress updates for lightweight status while tools run
- Client effects for fire-and-forget UI behavior
- Client tools for round-trips to the browser/app during inference

## Show progress while tools run

Use `ProgressUpdateEvent` when you need lightweight, real-time status. These updates stream immediately to the client and disappear after the turn—they are not stored in the thread.

### From tools

Inside a tool, use `AgentContext.stream` to enqueue progress events. They are delivered to the client immediately and are not persisted as thread items.

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext
from chatkit.types import ProgressUpdateEvent


@function_tool()
async def ingest_files(ctx: RunContextWrapper[AgentContext], paths: list[str]):
    await ctx.context.stream(ProgressUpdateEvent(icon="upload", text="Uploading..."))
    await upload(paths)

    await ctx.context.stream(
        ProgressUpdateEvent(icon="search", text="Indexing and chunking...")
    )
    await index_files(paths)

    await ctx.context.stream(ProgressUpdateEvent(icon="check", text="Done"))
```

`stream_agent_response` will forward these events for you alongside any assistant text or tool call updates.

### From custom pipelines

If you are not using the Agents SDK, yield `ProgressUpdateEvent` directly from your `respond` or `action` methods while your backend works:

```python
async def respond(...):
    yield ProgressUpdateEvent(icon="search", text="Searching tickets...")
    results = await search_tickets()

    yield ProgressUpdateEvent(icon="code", text="Generating summary...")
    yield from await stream_summary(results)
```

Use short, action-oriented messages and throttle updates to meaningful stages instead of every percent to avoid noisy streams.

## Trigger client-side effects without blocking

Send `ClientEffectEvent` to trigger fire-and-forget UI work (such as refreshing a view, opening a modal, or showing a toast) without creating thread items or pausing the model stream.

Client effects are ephemeral: they stream immediately to ChatKit.js, trigger your registered effect handler, and are not persisted to the thread history. Use client tool calls instead when you need a round-trip response from the client.

### Stream a client effect from your server

Yield client effects directly from the `respond` or `action` method:

```python
async def respond(...):
    yield ClientEffectEvent(
        name="highlight_text",
        data={"index": 142, "length": 35},
    )
```

Or from tools, through `AgentContext`:

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext
from chatkit.types import ClientEffectEvent


@function_tool()
async def highlight_text(ctx: RunContextWrapper[AgentContext], index: int, length: int):
    await ctx.context.stream(
        ClientEffectEvent(
            name="highlight_text",
            data={"index": index, "length": length},
        )
    )
```

### Handle the client effect in ChatKit.js

Register a client effect handler when initializing ChatKit on the client:

```ts
const chatkit = useChatKit({
  // ...
  onEffect: async ({name, data}) => {
    if (name === "highlight_text") {
      const {index, length} = data;
      highlightArticleText({index, length});
      // No return value needed
    }
  },
});
```

## Call client tools mid-inference

Client tool calls let the agent invoke browser/app callbacks mid-inference. Register the tool on both client and server; when triggered, ChatKit pauses the model, sends the tool request to the client, and resumes with the returned result.

Use client effects instead when you do not need to wait for the client callback response for the rest of your response.

### Define a client tool in your agent

Set `ctx.context.client_tool_call` inside a tool and configure the agent to stop at that tool. Only one client tool call can run per turn. Include client tools in `stop_at_tool_names` so the model pauses while the client callback runs and returns its result.

```python
from agents import Agent, RunContextWrapper, StopAtTools, function_tool
from chatkit.agents import AgentContext, ClientToolCall


@function_tool(description_override="Read the user's current canvas selection.")
async def get_selected_canvas_nodes(ctx: RunContextWrapper[AgentContext]) -> None:
    ctx.context.client_tool_call = ClientToolCall(
        name="get_selected_canvas_nodes",
        arguments={"project": my_project()},
    )


assistant = Agent[AgentContext](
    ...,
    tools=[get_selected_canvas_nodes],
    # StopAtTools pauses model generation so the pending client callback can run and resume the run.
    tool_use_behavior=StopAtTools(stop_at_tool_names=[get_selected_canvas_nodes.name]),
)
```

### Register the client tool in ChatKit.js

Provide a matching callback when initializing ChatKit on the client. The function name must match the `ClientToolCall.name`, and its return value is sent back to the server to resume the run.

```ts
const chatkit = useChatKit({
  // ...
  onClientTool: async ({name, params}) => {
    if (name === "get_selected_canvas_nodes") {
      const {project} = params;
      const nodes = myCanvas.getSelectedNodes(project);
      return {
        nodes: nodes.map((node) => ({id: node.id, kind: node.type})),
      };
    }
  },
});
```

### Stream and resume

In `respond`, stream via `stream_agent_response` as usual. ChatKit emits a pending client tool call item; the frontend runs your registered client tool, posts the output back, and the server continues the run.

When the client posts the tool result, ChatKit stores it as a `ClientToolCallItem`. The continued inference after the client tool call handler returns the result feeds both the call and its output back to the model through `ThreadItemConverter.client_tool_call_to_input`, which emits a `function_call` plus matching `function_call_output` so the model sees the browser-provided context.


