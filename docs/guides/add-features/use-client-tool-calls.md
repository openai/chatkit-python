# Use client tool calls

Client tool calls let the agent invoke browser/app callbacks mid-inference. Register the tool on both client and server; when triggered, ChatKit pauses the model, sends the tool request to the client, and resumes with the returned result.

!!! note "Prefer client effects for non-blocking updates"
    Use client effects instead when you do not need to wait for the client callback response for the rest of your response. See [Send client effects](send-client-effects.md) for more details.

## Define a client tool in your agent

Set `ctx.context.client_tool_call` inside a tool and configure the agent to stop at that tool.

Only one client tool call can run per turn. Include client tools in `stop_at_tool_names` so the model pauses while the client callback runs and returns its result.


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
    ...
    tools=[get_selected_canvas_nodes],
    # StopAtTools pauses model generation so the pending client callback can run and resume the run.
    tool_use_behavior=StopAtTools(stop_at_tool_names=[get_selected_canvas_nodes.name]),
)
```

## Register the client tool in ChatKit.js

Provide a matching callback when initializing ChatKit on the client. The function name must match the `ClientToolCall.name`, and its return value is sent back to the server to resume the run.

```ts
const chatkit = useChatKit({
  // ...
  onClientTool: async ({name, params}) => {
    if (name === "get_selected_canvas_nodes") {
        const {project} = params;
        const nodes = myCanvas.getSelectedNodes(project);
        return {
            nodes: nodes.map((node) => ({ id: node.id, kind: node.type })),
        };
    },
  },
});
```

## Stream and resume

In `respond`, stream via `stream_agent_response` as usual. ChatKit emits a pending client tool call item; the frontend runs your registered client tool, posts the output back, and the server continues the run.

When the client posts the tool result, ChatKit stores it as a `ClientToolCallItem`. The continued inference after the client tool call handler returns the result feeds both the call and its output back to the model through `ThreadItemConverter.client_tool_call_to_input`, which emits a `function_call` plus matching `function_call_output` so the model sees the browser-provided context.
