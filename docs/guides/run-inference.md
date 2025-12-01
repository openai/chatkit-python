# Run inference

The Agents SDK is the officially supported way to run inference with ChatKit and stream results back, but it is not mandatory. Any pipeline that yields `ThreadStreamEvent`s will work.

If you are not using Agents SDK, emit `ThreadStreamEvent`s yourself from `respond`. Assistant messages, tool status, notices, and widgets are all first-class events; see [Stream thread events](stream-thread-events.md) for patterns.

## Access ChatKit helpers inside tools

`AgentContext` is passed through to server tool calls (via `RunContextWrapper`) so tools can stream events or use the store. For example, use `ctx.context.stream(...)` to update the UI while a tool runs (more details in [Stream thread events](stream-thread-events.md)), or `ctx.context.store` to load or persist thread data during tool execution.

Attach server tools to your agent as usual; each tool receives the same `AgentContext` you constructed before running inference, giving it access to the current thread, store, and request context.

You can subclass `AgentContext` to add app-specific context that tools and agents can use directly, such as a separate data store.

```python
class MyAgentContext(AgentContext[RequestContext]):
    data_store: MyDataStore
    analytics: AnalyticsClient


async def respond(...):
    agent_context = MyAgentContext(
        thread=thread,
        store=self.store,            # your ChatKit data store
        request_context=context,     # your ChatKit request context (headers, auth)
        data_store=self.data_store,  # example addition: app-specific store
        analytics=self.analytics,    # example addition: app-specific service
    )
    result = Runner.run_streamed(
        assistant_agent,
        input_items,
        context=agent_context,
    )
```

Tools now receive `ctx.context` typed as `MyAgentContext`, so they can read or write app state without extra plumbing.

## Client tool calls

Client tool calls mirror server tool calls, except they seamlessly invoke a ChatKit.js client callback you registered on the frontend while inference runs. Trigger one by setting `ctx.context.client_tool_call` inside a tool and registering the same tool on both client and server.

Only one client tool call is allowed per turn, and the agent must stop at the tool before continuing. See also [Use client tool calls](add-features/use-client-tool-calls.md).

```python
@function_tool(description_override="Add an item to the user's todo list.")
async def add_to_todo_list(ctx: RunContextWrapper[AgentContext], item: str) -> None:
    ctx.context.client_tool_call = ClientToolCall(
        name="add_to_todo_list",
        arguments={"item": item},
    )

assistant_agent = Agent[AgentContext](
    model="gpt-5",
    name="Assistant",
    instructions="You are a helpful assistant",
    tools=[add_to_todo_list],
    tool_use_behavior=StopAtTools(stop_at_tool_names=[add_to_todo_list.name]),
)
```

## Send agent reference content

You can supply additional reference context to the model at inference time using server tools, client tools, or manual input injection. Choose the mechanism based on where the data lives and who owns it.

- Use server tools when the reference content lives on the backend and can be retrieved during inference.
- Use client tool calls when the browser or app must supply transient state (for example, active UI selections).
- Manually inject additional model input items when the reference content is already available at inference time and your application is latency-sensitive.
