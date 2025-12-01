# Send client effects

Send ClientEffectEvent to trigger fire-and-forget UI work (such as refreshing a view, opening a modal, showing a toast) without creating thread items or pausing the model stream.

!!! note "Client effects vs. client tool calls"
    Client effects are ephemeral: they stream immediately to ChatKit.js, trigger your registered effect handler, and are not persisted to the thread history. Use client tool calls instead when you need a round-trip response from the client.

## Stream a client effect from your server

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

## Handle the client effect in ChatKit.js

Register a client effect handler when initializing ChatKit on the client.

```ts
const chatkit = useChatKit({
  // ...
  onEffect: async ({name, data}) => {
    if (name === "highlight_text") {
        const {index, length} = data;
        const nodes = highlightArticleText({index, length});
        // No return value needed
    },
  },
});
```
