# Serve ChatKit from your backend

ChatKit's server integration is intentionally small: implement a `ChatKitServer`, wire up a single POST endpoint, and stream `ThreadStreamEvent`s back to the client. You decide where to run the server and how to authenticate requests.

## Install the SDK

Install the `openai-chatkit` package:

```bash
pip install openai-chatkit
```

## Implement a ChatKit server

Subclass `ChatKitServer` and implement `respond`. This method runs every time a user sends a message and should stream back the events that make up your response (assistant messages, tool calls, workflows, tasks, widgets, and so on).

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass
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


@dataclass
class MyRequestContext:
    user_id: str


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

## Pass request context into ChatKit

`ChatKitServer[TContext]` and `Store[TContext]` are generic over a request context type you choose. Your context carries caller-specific data (for example user id, org, auth scopes, feature flags) into `ChatKitServer.respond` and your `Store`. Define a lightweight type and pass it through when you call `server.process`.

```python
context = MyRequestContext(user_id="abc123")
result = await server.process(await request.body(), context)
```

## Expose the ChatKit endpoint

ChatKit is framework-agnostic. Expose a single POST endpoint that returns JSON or streams server‑sent events (SSE).

Example using ChatKit with FastAPI:

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from chatkit.server import ChatKitServer, StreamingResult

app = FastAPI()
data_store = MyPostgresStore(conn_info)
server = MyChatKitServer(data_store)


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    context = MyRequestContext(...)
    result = await server.process(await request.body(), context)
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")
```

### (Optional) Pass through request metadata

Every ChatKit request payload includes a `metadata` field you can use to carry per-request context from the client.

Pull it from the request in your endpoint before calling server.process to use it for auth/tracing/business logic there, or to include it in the context you pass through so respond and tools can read it.
