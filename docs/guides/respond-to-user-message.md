# Respond to a user message

This guide covers how to implement and run a ChatKit server that responds to user messages, including thread loading, inference, event streaming, and persistence.

## Install ChatKit

Install the SDK from PyPI:

```bash
pip install openai-chatkit
```

## Build and run your ChatKit server

Your ChatKit server does three main things:

1. Accept HTTP requests from your client.
2. Construct a request context (user id, auth, feature flags, etc.).
3. Call `ChatKitServer.respond` to produce streamed events.

### Define a request context

First, define a small context object that will be created per request and passed through your server, store, and agents:

```python
from dataclasses import dataclass


@dataclass
class MyRequestContext:
    user_id: str
```

### Implement your `ChatKitServer`

Subclass `ChatKitServer` and implement `respond`. It runs once per user turn and should yield the events that make up your response. We’ll keep this example simple for now and fill in history loading and model calls in later sections.

```python
from collections.abc import AsyncIterator
from datetime import datetime

from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)


class MyChatKitServer(ChatKitServer[MyRequestContext]):
    async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: MyRequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        # Replace this with your inference pipeline.
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                thread_id=thread.id,
                id=self.store.generate_item_id("message", thread, context),
                created_at=datetime.now(),
                content=[AssistantMessageContent(text="Hi there!")],
            )
        )
```

### Wire ChatKit to your web framework

Expose a single `/chatkit` endpoint that forwards requests to your `MyChatKitServer` instance. For example, with FastAPI:

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from chatkit.server import ChatKitServer, StreamingResult

app = FastAPI()
store = MyPostgresStore(conn_info)
server = MyChatKitServer(store)


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    # Build a per-request context from the incoming HTTP request.
    context = MyRequestContext(user_id="abc123")

    # Let ChatKit handle the request and return either a streaming or JSON result.
    result = await server.process(await request.body(), context)
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")
```

### How request context flows into ChatKit

`ChatKitServer[TContext]` and `Store[TContext]` are generic over a request context type you choose (user id, org, auth scopes, feature flags). Construct it per request and pass it to `server.process`; it flows into `respond` and your store methods.

```python
context = MyRequestContext(user_id="abc123")
result = await server.process(await request.body(), context)
```

Request metadata in the payload is available before calling `process`; include it in your context for auth, tracing, or feature flags.

## Implement your ChatKit data store

Implement the `Store` interface to control how threads, messages, tool calls, and widgets are stored. Prefer serializing thread items as JSON so schema changes do not break storage. Example Postgres store:

```python
class MyPostgresStore(Store[RequestContext]):
    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data JSONB NOT NULL
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL
                        REFERENCES threads (id)
                        ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data JSONB NOT NULL
                );
                """
            )

            conn.commit()

    async def load_thread(
        self, thread_id: str, context: RequestContext
    ) -> ThreadMetadata:
        with self._connection() as conn, conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(
                "SELECT data FROM threads WHERE id = %s AND user_id = %s",
                (thread_id, context.user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise NotFoundError(f"Thread {thread_id} not found")
            return ThreadMetadata.model_validate(row[0])

    async def save_thread(
        self, thread: ThreadMetadata, context: RequestContext
    ) -> None:
        payload = thread.model_dump(mode="json")
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO threads (id, user_id, created_at, data)
                VALUES (%s, %s, %s, %s)
                """,
                (thread.id, context.user_id, thread.created_at, payload),
            )
            conn.commit()

    # Implement the remaining Store methods following the same pattern.
```

Customize ID generation by overriding `generate_thread_id` and `generate_item_id` if you need external or deterministic IDs. Store metadata such as `previous_response_id` on `ThreadMetadata` to drive your inference pipeline.

## Generate a response using your model

Inside `respond`, you’ll usually:

1. Load recent thread history.
2. Prepare model input for your agent.
3. Run inference and stream events back to the client.

### Load thread history inside `respond`

Fetch recent items so the model sees the conversation state before you build the next turn:

```python
items_page = await self.store.load_thread_items(
    thread.id,
    after=None,
    limit=20,  # Tune this limit based on your model/context budget.
    order="desc",
    context=context,
)
items = list(reversed(items_page.data))
```

### Prepare model input

Use the defaults first: `simple_to_agent_input` converts user items into Agents SDK inputs, and `ThreadItemConverter` handles other item types. Override converter methods if you need special handling for hidden context, attachments, or tags.

Respect any `input.inference_options` the client sends (model, tool choice, etc.) when you build your request to the model.

```python
from agents import Runner
from chatkit.agents import AgentContext, simple_to_agent_input

input_items = await simple_to_agent_input(items)
agent_context = AgentContext(
    thread=thread,
    store=self.store,
    request_context=context,
)
```

### Run inference and stream events

Run your agent and stream events back to the client. `stream_agent_response` converts an Agents run into ChatKit events; you can also yield events manually.

```python
from agents import (
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    Runner,
)
from chatkit.agents import stream_agent_response
from chatkit.types import ErrorEvent

result = Runner.run_streamed(
    assistant_agent,
    input_items,
    context=agent_context,
)

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

To stream events from a server tool during the same turn, use `ctx.context.stream(...)` inside the tool:

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext
from chatkit.types import ProgressUpdateEvent


@function_tool()
async def load_document(ctx: RunContextWrapper[AgentContext], document_id: str):
    await ctx.context.stream(ProgressUpdateEvent(icon="document", text="Loading document..."))
    return await get_document_by_id(document_id)
```

`stream_agent_response` will forward these events alongside any assistant text or tool call updates. Client tool calls are also supported via `ctx.context.client_tool_call` when you register the tool on both client and server.

## Next: add features

- [Let users browse past threads](browse-past-threads.md)
- [Accept attachments](accept-attachments.md)
- [Make client tool calls](make-client-tool-calls.md)
- [Send client effects](send-client-effects.md)
- [Show progress for long-running tools](show-progress-for-long-running-tools.md)
- [Stream widgets](stream-widgets.md)
- [Handle widget actions](handle-widget-actions.md)
- [Create custom forms](create-custom-forms.md)
- [Handle feedback](handle-feedback.md)
- [Allow @-mentions in user messages](allow-mentions.md)
- [Add annotations in assistant messages](add-annotations.md)
