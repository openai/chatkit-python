# Pass extra app context to your model

Sometimes the model needs information that is not part of the thread: the current route, user plan, selected document, feature flags, or host-app state. This guide shows several patterns for passing that extra context into your inference pipeline.

At a high level:

- Send app/user context from the client to your ChatKit server on every request.
- Fetch context on demand with tools (including client tools).
- Inject extra context as an additional model input item when you build the request.

## Send app context with each request

### Attach headers from `useChatKit`

Use a custom `fetch` (or equivalent) when configuring `useChatKit` to attach app/user context via headers to every request:

```tsx
const chatkit = useChatKit({
  api: {
    // ...
    fetch: (input, init) =>
      fetch(input, {
        ...init,
        headers: {
          // Make sure to pipe through headers sent by ChatKit
          ...(init?.headers || {}),
          "X-Org-Id": currentOrgId,
          "X-Plan": currentPlan,
        },
      }),
  },
});
```

On the server, read these headers before calling `ChatKitServer.process` and add them to your request context:

```python
from dataclasses import dataclass


@dataclass
class RequestContext:
    user_id: str
    org_id: str
    plan: str
```

Use this context in your `respond` method, tools, and store methods to keep the model and your business logic aware of the current app state.

## Fetch context on demand with tools

Sometimes you only need extra context for certain requests—fetch it on demand with tools instead of sending it for every turn.

### Server tools that fetch app context

Define a server tool that looks up app state (for example, the user’s current workspace or preferences) and returns a JSON payload to the model:

```python
@function_tool(description_override="Fetch the user's workspace context.")
async def get_workspace_context(ctx: RunContextWrapper[AgentContext]):
    workspace = await load_workspace(ctx.context.request_context.org_id)
    return {
        "workspace_id": workspace.id,
        "features": workspace.feature_flags,
    }
```

Include this tool in your agent so the model can call it when it needs that information.

### Client tools for browser/app-only state

When the context only exists on the client (selection, viewport, local app state), use a client tool:

```python
@function_tool(description_override="Read the user's current canvas selection.")
async def get_canvas_selection(ctx: RunContextWrapper[AgentContext]) -> None:
    ctx.context.client_tool_call = ClientToolCall(
        name="get_canvas_selection",
        arguments={},
    )
```

On the client, implement the callback:

```ts
const chatkit = useChatKit({
  // ...
  onClientTool: async ({name, params}) => {
    if (name === "get_canvas_selection") {
      const selection = myCanvas.getSelection();
      return {
        nodes: selection.map((node) => {
          name: node.name,
          description: node.description,
        }),
      };
    }
  },
});
```

ChatKit will send the client tool result back to the server and continue the run with that data included as model input.

## Inject extra context as model input item

You can also inject context directly as an extra model input item when you build the request.

### Add a dedicated context item

Before running your agent, prepend a short, structured context item describing app/user state:

```python
from openai.types.responses import ResponseInputTextParam


extra_context = ResponseInputTextParam(
    type="input_text",
    text=(
        "<APP_CONTEXT>\n"
        f"user_id: {context.user_id}\n"
        f"org_id: {context.org_id}\n"
        f"plan: {context.plan}\n"
        "</APP_CONTEXT>"
    ),
)

input_items = [extra_context, *input_items]
```

Pair this with a short system prompt telling the model how to interpret the `<APP_CONTEXT>` block.

### Combine ids + tools

A useful pattern is to combine a lightweight context item with a follow-up tool call:

1. Add an input item that contains a stable id or handle:

   ```python
   extra_context = ResponseInputTextParam(
       type="input_text",
       text=f"<WORKSPACE_REF id={workspace.id} />",
   )
   input_items = [extra_context, *input_items]
   ```

2. Provide a tool (server or client) that can fetch the full details when needed:

   ```python
   @function_tool(description_override="Fetch full workspace details.")
   async def fetch_workspace(ctx: RunContextWrapper[AgentContext], id: str):
       workspace = await load_workspace(id)
       return {
           "id": workspace.id,
           "features": workspace.feature_flags,
           "limits": workspace.limits,
       }
   ```

3. In your prompt, tell the model:

   - The `<WORKSPACE_REF>` tag carries the id it should use.
   - It should call `fetch_workspace` when it needs more detail instead of guessing.

This keeps your model inputs compact while still giving the model a reliable way to pull detailed context on demand.


