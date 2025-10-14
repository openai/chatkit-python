# ChatKit server integration

ChatKit's server integration offers a flexible and framework-agnostic approach for building realtime chat experiences. By implementing the `ChatKitServer` base class and its `respond` method, you can configure how your workflow responds to user inputs, from using tools to returning rich display widgets. The ChatKit server integration exposes a single endpoint and supports JSON and server‑sent events (SSE) to stream real-time updates.

## Installation

Install the `openai-chatkit` package with the following command:

```bash
pip install openai-chatkit
```

## Defining a server class

The `ChatKitServer` base class is the main building block of the ChatKit server implementation.

The `respond` method is executed each time a user sends a message. It is responsible for providing an answer by streaming a set of events. The `respond` method can return assistant messages, tool status messages, workflows, tasks, and widgets.

ChatKit also provides helpers to implement `respond` using Agents SDK. The main one is `stream_agent_response`, which converts a streamed Agents SDK run into ChatKit events.

If you've enabled model or tool options in the composer, they'll appear in `respond` under `input_user_message.inference_options`. Your integration is responsible for handling these values when performing inference.

Example server implementation that calls the Agent SDK runner and streams the result to the ChatKit UI:

```python
class MyChatKitServer(ChatKitServer):
    def __init__(
        self, data_store: Store, attachment_store: AttachmentStore | None = None
    ):
        super().__init__(data_store, attachment_store)

    assistant_agent = Agent[AgentContext](
        model="gpt-4.1",
        name="Assistant",
        instructions="You are a helpful assistant"
    )

    async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )
        result = Runner.run_streamed(
            self.assistant_agent,
            await simple_to_agent_input(input) if input else [],
            context=context,
        )
        async for event in stream_agent_response(
            context,
            result,
        ):
            yield event

    # ...
```

## Setting up the endpoint

ChatKit is server-agnostic. All communication happens through a single POST endpoint that returns either JSON directly or streams SSE JSON events.

You are responsible for defining the endpoint using the web server framework of your choice.

Example using ChatKit with FastAPI:

```python
app = FastAPI()
data_store = PostgresStore()
attachment_store = BlobStorageStore(data_store)
server = MyChatKitServer(data_store, attachment_store)

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await server.process(await request.body(), {})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    else:
        return Response(content=result.json, media_type="application/json")
```

## Data store

ChatKit needs to store information about threads, messages, and attachments. The examples above use a provided development-only data store implementation using SQLite (`SQLiteStore`).

You are responsible for implementing the `chatkit.store.Store` class using the data store of your choice. When implementing the store, you must allow for the Thread/Attachment/ThreadItem type shapes changing between library versions. The recommended approach for relational databases is to serialize models into JSON-typed columns instead of separating model fields across multiple columns.

```python
class Store(ABC, Generic[TContext]):
    def generate_thread_id(self, context: TContext) -> str: ...

    def generate_item_id(
        self,
        item_type: Literal["message", "tool_call", "task", "workflow", "attachment"],
        thread: ThreadMetadata,
        context: TContext,
    ) -> str: ...

    async def load_thread(self, thread_id: str, context: TContext) -> ThreadMetadata: ...

    async def save_thread(self, thread: ThreadMetadata, context: TContext) -> None: ...

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: TContext,
    ) -> Page[ThreadItem]: ...

    async def save_attachment(self, attachment: Attachment, context: TContext) -> None: ...

    async def load_attachment(self, attachment_id: str, context: TContext) -> Attachment: ...

    async def delete_attachment(self, attachment_id: str, context: TContext) -> None: ...

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: TContext,
    ) -> Page[ThreadMetadata]: ...

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: TContext
    ) -> None: ...

    async def save_item(self, thread_id: str, item: ThreadItem, context: TContext) -> None: ...

    async def load_item(self, thread_id: str, item_id: str, context: TContext) -> ThreadItem: ...

    async def delete_thread(self, thread_id: str, context: TContext) -> None: ...
```

The default implementation prefixes identifiers (for example `msg_4f62d6a7f2c34bd084f57cfb3df9f6bd`) using UUID4 strings. Override `generate_thread_id` and/or `generate_item_id` if your
integration needs deterministic or pre-allocated identifiers; they will be used whenever ChatKit needs to create a new thread id or a new thread item id.

## Attachment store

Users can upload attachments (files and images) to include with chat messages. You are responsible for providing a storage implementation and handling uploads. The `attachment_store` argument to `ChatKitServer` should implement the `AttachmentStore` interface. If not provided, operations on attachments will raise an error.

ChatKit supports both direct uploads and two‑phase upload, configurable client-side via `ChatKitOptions.composer.attachments.uploadStrategy`.

### Access control

Attachment metadata and file bytes are not protected by ChatKit. Each `AttachmentStore` method receives your request context so you can enforce thread- and user-level authorization before handing out attachment IDs, bytes, or signed URLs. Deny access when the caller does not own the attachment, and generate download URLs that expire quickly. Skipping these checks can leak customer data.

### Direct upload

The direct upload URL is provided client-side as a create option.

The client will POST `multipart/form-data` with a `file` field to that URL. The server should:

1. persist the attachment metadata (`FileAttachment | ImageAttachment`) to the data store and the file bytes to your storage.
2. respond with JSON representation of `FileAttachment | ImageAttachment`.

### Two‑phase upload

- **Phase 1 (registration and upload URL provisioning)**: The client calls `attachments.create`. ChatKit persists a `FileAttachment | ImageAttachment` sets the `upload_url` and returns it. It's recommended to include the `id` of the `Attachment` in the `upload_url` so that you can associate the file bytes with the `Attachment`.
- **Phase 2 (upload)**: The client POSTs the bytes to the returned `upload_url` with `multipart/form-data` field `file`.

### Previews

To render thumbnails of an image attached to a user message, set `ImageAttachment.preview_url` to a renderable URL. If you need expiring URLs, do not persist the URL; generate it on demand when returning the attachment to the client.

### AttachmentStore interface

You implement the storage specifics by providing the `AttachmentStore` methods:

```python
class AttachmentStore(ABC, Generic[TContext]):
    async def delete_attachment(self, attachment_id: str, context: TContext) -> None: ...
    async def create_attachment(self, input: AttachmentCreateParams, context: TContext) -> Attachment: ...
    def generate_attachment_id(self, mime_type: str, context: TContext) -> str: ...
```

Note: The store does not have to persist bytes itself. It can act as a proxy that issues signed URLs for upload and preview (e.g., S3/GCS/Azure), while your separate upload endpoint writes to object storage.

### Attaching files to Agent SDK inputs

You are also responsible for deciding how to attach attachments to Agent SDK inputs. You can store files in your own storage and attach them as base64-encoded payloads or upload them to the OpenAI Files API and provide the file ID to the Agent SDK.

The example below shows how to create base64-encoded payloads for attachments by customizing a `ThreadItemConverter`. The helper `read_attachment_bytes` stands in for whatever storage accessor you provide (for example, fetching from S3 or a database) because `AttachmentStore` only handles ChatKit protocol calls.

```python
async def read_attachment_bytes(attachment_id: str) -> bytes:
    """Replace with your blob-store fetch (S3, local disk, etc.)."""
    ...


class MyConverter(ThreadItemConverter):
    async def attachment_to_message_content(
        self, input: Attachment
    ) -> ResponseInputContentParam:
        content = await read_attachment_bytes(input.id)
        data = (
            "data:"
            + str(input.mime_type)
            + ";base64,"
            + base64.b64encode(content).decode("utf-8")
        )
        if isinstance(input, ImageAttachment):
            return ResponseInputImageParam(
                type="input_image",
                detail="auto",
                image_url=data,
            )
        # Note: Agents SDK currently only supports pdf files as ResponseInputFileParam.
        # To send other text file types, either convert them to pdf on the fly or
        # add them as input text.
        return ResponseInputFileParam(
            type="input_file",
            file_data=data,
            filename=input.name or "unknown",
        )

# In respond(...):
result = Runner.run_streamed(
    assistant_agent,
    await MyConverter().to_agent_input(input),
    context=context,
)
```

## Client tools usage

The ChatKit server implementation can trigger client-side tools.

The tool must be registered both when initializing ChatKit on the client and when setting up Agents SDK on the server.

To trigger a client-side tool from Agents SDK, set `ctx.context.client_tool_call` in the tool implementation with the client-side tool name and arguments. The result of the client tool execution will be provided back to the model.

**Note:** The agent behavior must be set to `tool_use_behavior=StopAtTools` with all client-side tools included in `stop_at_tool_names`. This causes the agent to stop generating new messages until the client tool call is acknowledged by the ChatKit UI.

**Note:** Only one client tool call can be triggered per turn.

**Note:** Client tools are client-side callbacks invoked by the agent during server-side inference. If you're interested in client-side callbacks triggered by a user interacting with a widget, refer to [client actions](actions.md/#client).

```python
@function_tool(description_override="Add an item to the user's todo list.")
async def add_to_todo_list(ctx: RunContextWrapper[AgentContext], item: str) -> None:
    ctx.context.client_tool_call = ClientToolCall(
        name="add_to_todo_list",
        arguments={"item": item},
    )

assistant_agent = Agent[AgentContext](
    model="gpt-4.1",
    name="Assistant",
    instructions="You are a helpful assistant",
    tools=[add_to_todo_list],
    tool_use_behavior=StopAtTools(stop_at_tool_names=[add_to_todo_list.name]),
)
```

## Agents SDK integration

The ChatKit server is independent of Agents SDK. As long as correct events are returned from the `respond` method, the ChatKit UI will display the conversation as expected.

The ChatKit library provides helpers to integrate with Agents SDK:

- `AgentContext` - The context type that should be used when calling Agents SDK. It provides helpers to stream events from tool calls, render widgets, and initiate client tool calls.
- `stream_agent_response` - A helper to convert a streamed Agents SDK run into ChatKit events.
- `ThreadItemConverter` - A helper class that you'll probably extend to convert ChatKit thread items to Agents SDK input items.
- `simple_to_agent_input` - A helper function that uses the default thread item conversions. The default conversion is limited, but useful for getting started quickly.

```python
async def respond([]
    self,
    thread: ThreadMetadata,
    input: UserMessageItem | None,
    context: Any,
) -> AsyncIterator[ThreadStreamEvent]:
    context = AgentContext(
        thread=thread,
        store=self.store,
        request_context=context,
    )

    result = Runner.run_streamed(
        self.assistant_agent,
        await simple_to_agent_input(input) if input else [],
        context=context,
    )

    async for event in stream_agent_response(context, result):
        yield event
```

### ThreadItemConverter

Extend `ThreadItemConverter` when your integration supports:

- Attachments
- @-mentions (entity tagging)
- `HiddenContextItem`
- Custom thread item formats

```python
from agents import Message, Runner, ResponseInputTextParam
from chatkit.agents import AgentContext, ThreadItemConverter, stream_agent_response
from chatkit.types import Attachment, HiddenContextItem, ThreadMetadata, UserMessageItem


class MyThreadConverter(ThreadItemConverter):
    async def attachment_to_message_content(
        self, attachment: Attachment
    ) -> ResponseInputTextParam:
        content = await attachment_store.get_attachment_contents(attachment.id)
        data_url = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("utf-8"))
        if isinstance(attachment, ImageAttachment):
            return ResponseInputImageParam(
                type="input_image",
                detail="auto",
                image_url=data_url,
            )

        # ..handle other attachment types

    def hidden_context_to_input(self, item: HiddenContextItem) -> Message:
        return Message(
            type="message",
            role="system",
            content=[
                ResponseInputTextParam(
                    type="input_text",
                    text=f"<HIDDEN_CONTEXT>{item.content}</HIDDEN_CONTEXT>",
                )
            ],
        )

    def tag_to_message_content(self, tag: UserMessageTagContent):
        tag_context = await retrieve_context_for_tag(tag.id)
        return ResponseInputTextParam(
            type="input_text",
            text=f"<TAG>Name:{tag.data.name}\nType:{tag.data.type}\nDetails:{tag_context}</TAG>"
        )

        # ..handle other @-mentions

    # ..override defaults for other methods

```

## Widgets

Widgets are rich UI components that can be displayed in chat. You can return a widget either directly from the `respond` method (if you want to do so unconditionally) or from a tool call triggered by the model.

Example of a widget returned directly from the `respond` method:

```python
async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
    widget = Text(
        id="description",
        value="Text widget",
    )

    async for event in stream_widget(
        thread,
        widget,
        generate_id=lambda item_type: self.store.generate_item_id(
            item_type, thread, context
        ),
    ):
        yield event
```

Example of a widget returned from a tool call:

```python
@function_tool(description_override="Display a sample widget to the user.")
async def sample_widget(ctx: RunContextWrapper[AgentContext]) -> None:
    widget = Text(
        id="description",
        value="Text widget",
    )

    await ctx.context.stream_widget(widget)
```

The examples above return a fully completed static widget. You can also stream an updating widget by yielding new versions of the widget from a generator function. The ChatKit framework will send updates for the parts of the widget that have changed.

**Note:** Currently, only `<Text>` and `<Markdown>` components marked with an `id` have their text updates streamed.

```python
async def sample_widget(ctx: RunContextWrapper[AgentContext]) -> None:
     description_text = Runner.run_streamed(
        email_generator, "ChatKit is the best thing ever"
    )

    async def widget_generator() -> AsyncGenerator[Widget, None]:
        text_widget_updates = accumulate_text(
            description_text.stream_events(),
            Text(
                id="description",
                value="",
                streaming=True
            ),
        )

        async for text_widget in text_widget_updates:
            yield Card(
                children=[text_widget]
            )

    await ctx.context.stream_widget(widget_generator())
```

In the example above, the `accumulate_text` function is used to stream the results of an Agents SDK run into a `Text` widget.

### Defining a widget

You may find it easier to write widgets in JSON. To you can parse JSON widgets to `WidgetRoot` instances for your server to stream:

```python
try:
    WidgetRoot.model_validate_json(WIDGET_JSON_STRING)
except ValidationError:
    # handle invalid json
```

### Widget reference and examples

See full reference of components, props, and examples in [widgets.md ➡️](./widgets.md).

## Thread metadata

ChatKit provides a way to store arbitrary information associated with a thread. This information is not sent to the UI.

One use case for the metadata is to preserve the [`previous_response_id`](https://platform.openai.com/docs/api-reference/responses/create#responses-create-previous_response_id) and avoid having to re-send all items for an Agent SDK run.

```python
previous_response_id = thread.metadata.get("previous_response_id")

# Run the Agent SDK run with the previous response id
result = Runner.run_streamed(
    agent,
    input=...,
    previous_response_id=previous_response_id,
)

# Save the previous response id for the next run
thread.metadata["previous_response_id"] = result.response_id
```

## Automatic thread titles

ChatKit does not automatically title threads, but you can easily implement your own logic to do so.

First, decide when to trigger the thread title update. A simple approach might be to set the thread title the first time a user sends a message.

```python
from chatkit.agents import simple_to_agent_input

async def maybe_update_thread_title(
    self,
    thread: ThreadMetadata,
    input_item: UserMessageItem,
) -> None:
    if thread.title is not None:
        return
    agent_input = await simple_to_agent_input(input_item)
    run = await Runner.run(title_agent, input=agent_input)
    thread.title = run.final_output

async def respond(
    self,
    thread: ThreadMetadata,
    input: UserMessageItem | None,
    context: Any,
) -> AsyncIterator[ThreadStreamEvent]:
    if input is not None:
        asyncio.create_task(self.maybe_update_thread_title(thread, input))

    # Generate the model response
    ...
```

## Progress updates

If your server-side tool takes a while to run, you can use the progress update event to display the progress to the user.

```python
@function_tool()
async def long_running_tool(ctx: RunContextWrapper[AgentContext]) -> str:
    await ctx.context.stream(
        ProgressUpdateEvent(text="Loading a user profile...")
    )

    await asyncio.sleep(1)
```

The progress update will be automatically replaced by the next assistant message, widget, or another progress update.

## Server context

Sometimes it's useful to pass additional information (like `userId`) to the ChatKit server implementation. The `ChatKitServer.process` method accepts a `context` parameter that it passes to the `respond` method and all data store and file store methods.

```python
class MyChatKitServer(ChatKitServer):
    async def respond(..., context) -> AsyncIterator[ThreadStreamEvent]:
        # consume context["userId"]

server.process(..., context={"userId": "user_123"})
```

Server context may be used to implement permission checks in AttachmentStore and Store.

```python
class MyChatKitServer(ChatKitServer):
    async def load_attachment(..., context) -> Attachment:
        # check context["userId"] has access to the file
```
pip install openai-chatkit
