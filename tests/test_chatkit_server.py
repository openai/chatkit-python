import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Callable, cast

import pytest
from helpers.mock_store import SQLiteStore
from pydantic import AnyUrl, TypeAdapter

from chatkit.actions import Action
from chatkit.errors import ErrorCode
from chatkit.server import (
    ChatKitServer,
    NonStreamingResult,
    StreamingResult,
    stream_widget,
)
from chatkit.store import (
    AttachmentStore,
    NotFoundError,
    StoreItemType,
    default_generate_id,
)
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    Attachment,
    AttachmentCreateParams,
    AttachmentDeleteParams,
    AttachmentsCreateReq,
    AttachmentsDeleteReq,
    ClientToolCallItem,
    FeedbackKind,
    FileAttachment,
    ImageAttachment,
    InferenceOptions,
    ItemFeedbackParams,
    ItemsFeedbackReq,
    ItemsListParams,
    ItemsListReq,
    LockedStatus,
    Page,
    ProgressUpdateEvent,
    Thread,
    ThreadAddClientToolOutputParams,
    ThreadAddUserMessageParams,
    ThreadCreatedEvent,
    ThreadCreateParams,
    ThreadCustomActionParams,
    ThreadDeleteParams,
    ThreadGetByIdParams,
    ThreadItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemRemovedEvent,
    ThreadItemReplacedEvent,
    ThreadItemUpdatedEvent,
    ThreadListParams,
    ThreadMetadata,
    ThreadRetryAfterItemParams,
    ThreadsAddClientToolOutputReq,
    ThreadsAddUserMessageReq,
    ThreadsCreateReq,
    ThreadsCustomActionReq,
    ThreadsDeleteReq,
    ThreadsGetByIdReq,
    ThreadsListReq,
    ThreadsRetryAfterItemReq,
    ThreadStreamEvent,
    ThreadsUpdateReq,
    ThreadUpdatedEvent,
    ThreadUpdateParams,
    ToolChoice,
    UserMessageInput,
    UserMessageItem,
    UserMessageTextContent,
    WidgetItem,
    WidgetRootUpdated,
)
from chatkit.widgets import Card, Text
from tests._types import RequestContext
from tests.test_store import make_thread_items

server_id = 0


DEFAULT_CONTEXT = RequestContext(user_id="test_user")


class InMemoryFileStore(AttachmentStore):
    def __init__(self):
        self.files = {}

    async def delete_attachment(self, attachment_id: str, context: Any) -> None:
        del self.files[attachment_id]

    async def create_attachment(
        self, input: AttachmentCreateParams, context: RequestContext
    ) -> Attachment:
        # Simple in-memory attachment creation
        id = f"atc_{len(self.files) + 1}"
        if input.mime_type.startswith("image/"):
            attachment = ImageAttachment(
                id=id,
                mime_type=input.mime_type,
                name=input.name,
                preview_url=AnyUrl(f"https://example.com/{id}/preview"),
                upload_url=AnyUrl(f"https://example.com/{id}/upload"),
            )
        else:
            attachment = FileAttachment(
                id=id,
                mime_type=input.mime_type,
                name=input.name,
                upload_url=AnyUrl(f"https://example.com/{id}/upload"),
            )
        self.files[attachment.id] = attachment
        return attachment


def decode_event(event: bytes) -> ThreadStreamEvent:
    return TypeAdapter(ThreadStreamEvent).validate_json(event.split(b"data: ")[1])


async def decode_streaming_result(
    streaming_result: StreamingResult,
) -> list[ThreadStreamEvent]:
    return [decode_event(event) async for event in streaming_result.json_events]


@contextmanager
def make_server(
    responder: Callable[
        [ThreadMetadata, UserMessageItem | None, Any], AsyncIterator[ThreadStreamEvent]
    ]
    | None = None,
    handle_feedback: Callable[[str, list[str], FeedbackKind, Any], None] | None = None,
    action_callback: Callable[
        [ThreadMetadata, Action[str, Any], WidgetItem | None, Any],
        AsyncIterator[ThreadStreamEvent],
    ]
    | None = None,
    file_store: AttachmentStore | None = None,
):
    global server_id
    db_path = f"file:{server_id}?mode=memory&cache=shared"
    server_id += 1
    # Keep the shared in-memory database from being deleted when the last connection is closed
    db = sqlite3.connect(db_path, uri=True)

    class TestChatKitServer(ChatKitServer):
        def __init__(self):
            super().__init__(SQLiteStore(db_path), file_store)

        def action(
            self,
            thread: ThreadMetadata,
            action: Action[str, Any],
            sender: WidgetItem | None,
            context: Any,
        ) -> AsyncIterator[ThreadStreamEvent]:
            if action_callback is None:
                raise ValueError("action_callback not wired up")
            return action_callback(thread, action, sender, context)

        def respond(
            self,
            thread: ThreadMetadata,
            input_user_message: UserMessageItem | None,
            context: Any,
        ) -> AsyncIterator[ThreadStreamEvent]:
            if responder is None:
                return self._empty_responder()
            return responder(thread, input_user_message, context)

        async def _empty_responder(self) -> AsyncIterator[ThreadStreamEvent]:
            return
            yield

        async def add_feedback(
            self,
            thread_id: str,
            item_ids: list[str],
            feedback: FeedbackKind,
            context: Any,
        ) -> None:
            if handle_feedback is None:
                return
            handle_feedback(thread_id, item_ids, feedback, context)

        async def process_streaming(
            self, request_obj, context: Any | None = None
        ) -> list[ThreadStreamEvent]:
            result = await self.process(
                request_obj.model_dump_json(), context or DEFAULT_CONTEXT
            )
            assert isinstance(result, StreamingResult)
            return await decode_streaming_result(result)

        async def process_non_streaming(self, request_obj, context: Any | None = None):
            result = await self.process(
                request_obj.model_dump_json(), context or DEFAULT_CONTEXT
            )
            assert isinstance(result, NonStreamingResult)
            return result

    try:
        yield TestChatKitServer()
    finally:
        db.close()


async def test_stream_cancellation_persists_pending_assistant_message_and_hidden_context():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemAddedEvent(
            item=AssistantMessageItem(
                id="assistant-message-pending",
                created_at=datetime.now(),
                content=[AssistantMessageContent(text="Hello, ")],
                thread_id=thread.id,
            )
        )
        yield ThreadItemUpdatedEvent(
            item_id="assistant-message-pending",
            update=AssistantMessageContentPartTextDelta(
                content_index=0,
                delta="World!",
            ),
        )
        raise asyncio.CancelledError()

    with make_server(responder) as server:
        # Allow hidden_context id generation in this test store
        original_generate_item_id = server.store.generate_item_id

        def generate_item_id(
            item_type: StoreItemType, thread: ThreadMetadata, context: Any
        ):
            if item_type == "sdk_hidden_context":
                return default_generate_id("sdk_hidden_context")
            return original_generate_item_id(item_type, thread, context)

        server.store.generate_item_id = generate_item_id  # type: ignore[method-assign]

        stream = await server.process(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            ).model_dump_json(),
            DEFAULT_CONTEXT,
        )
        assert isinstance(stream, StreamingResult)

        events: list[ThreadStreamEvent] = []
        with pytest.raises(asyncio.CancelledError):  # noqa: PT012
            async for raw in stream.json_events:
                events.append(decode_event(raw))

        thread = next(e.thread for e in events if e.type == "thread.created")
        items = await server.store.load_thread_items(
            thread.id, None, 1, "desc", DEFAULT_CONTEXT
        )
        hidden_context_item = items.data[-1]
        assert hidden_context_item.type == "sdk_hidden_context"
        assert (
            hidden_context_item.content
            == "The user cancelled the stream. Stop responding to the prior request."
        )

        assistant_message_item = await server.store.load_item(
            thread.id, "assistant-message-pending", DEFAULT_CONTEXT
        )
        assert assistant_message_item.type == "assistant_message"
        assert assistant_message_item.content[0].text == "Hello, World!"


async def test_stream_cancellation_does_not_persist_pending_empty_assistant_message():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemAddedEvent(
            item=AssistantMessageItem(
                id="assistant-message-pending",
                created_at=datetime.now(),
                content=[],
                thread_id=thread.id,
            )
        )
        raise asyncio.CancelledError()

    with make_server(responder) as server:
        original_generate_item_id = server.store.generate_item_id

        def generate_item_id(
            item_type: StoreItemType, thread: ThreadMetadata, context: Any
        ):
            if item_type == "sdk_hidden_context":
                return default_generate_id("sdk_hidden_context")
            return original_generate_item_id(item_type, thread, context)

        server.store.generate_item_id = generate_item_id  # type: ignore[method-assign]

        stream = await server.process(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            ).model_dump_json(),
            DEFAULT_CONTEXT,
        )
        assert isinstance(stream, StreamingResult)

        events: list[ThreadStreamEvent] = []
        with pytest.raises(asyncio.CancelledError):  # noqa: PT012
            async for raw in stream.json_events:
                events.append(decode_event(raw))

        thread = next(e.thread for e in events if e.type == "thread.created")
        items = await server.store.load_thread_items(
            thread.id, None, 1, "desc", DEFAULT_CONTEXT
        )
        hidden_context_item = items.data[-1]
        assert hidden_context_item.type == "sdk_hidden_context"
        assert (
            hidden_context_item.content
            == "The user cancelled the stream. Stop responding to the prior request."
        )

        with pytest.raises(NotFoundError):
            await server.store.load_item(
                thread.id, "assistant-message-pending", DEFAULT_CONTEXT
            )


async def test_flows_context_to_responder():
    responder_context = None
    add_feedback_context = None

    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        nonlocal responder_context
        responder_context = context
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="msg_1",
                created_at=datetime.now(),
                content=[AssistantMessageContent(text="Hello, world!")],
                thread_id=thread.id,
            ),
        )

    def add_feedback(
        thread_id: str, item_ids: list[str], feedback: FeedbackKind, context: Any
    ) -> None:
        nonlocal add_feedback_context
        add_feedback_context = context

    context = RequestContext(user_id="text_ctx")
    with make_server(responder, add_feedback) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            ),
            context,
        )
        assert responder_context == context
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        item = next(
            event.item
            for event in events
            if event.type == "thread.item.done"
            and event.item.type == "assistant_message"
        )
        await server.process_non_streaming(
            ItemsFeedbackReq(
                params=ItemFeedbackParams(
                    thread_id=thread.id,
                    item_ids=[item.id],
                    kind="positive",
                )
            ),
            context,
        )
        assert add_feedback_context == context


async def test_creates_thread():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        return
        yield

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                        quoted_text="Quoted text",
                    )
                )
            )
        )

        thread_created_event = next(
            event for event in events if event.type == "thread.created"
        )
        assert thread_created_event.thread.title is None

        item_done_event = next(
            event.item for event in events if event.type == "thread.item.done"
        )

        assert item_done_event.type == "user_message"
        assert item_done_event.content[0].text == "Hello, world!"
        assert item_done_event.quoted_text == "Quoted text"


async def test_saves_thread_title():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        thread.title = "Updated title"
        return
        yield

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        assert (
            await server.store.load_thread(
                thread.id, RequestContext(user_id="test_user")
            )
        ).title == "Updated title"
        assert events[-1].type == "thread.updated"
        assert events[-1].thread.title == "Updated title"


async def test_saves_thread_metadata():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        thread.metadata["test_key"] = "test_value"
        return
        yield

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        assert (await server.store.load_thread(thread.id, DEFAULT_CONTEXT)).metadata[
            "test_key"
        ] == "test_value"
        assert events[-1].type == "thread.updated"


async def test_saves_thread_locked_fields():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        thread.status = LockedStatus(reason="Because")
        return
        yield

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        loaded = await server.store.load_thread(
            thread.id, RequestContext(user_id="test_user")
        )
        assert loaded.status == LockedStatus(reason="Because")
        assert events[-1].type == "thread.updated"
        assert events[-1].thread.status == LockedStatus(reason="Because")


async def test_emits_thread_updated_mid_stream_and_persists():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        # First assistant message
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_a",
                content=[AssistantMessageContent(text="A")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

        # Update the thread mid-stream
        thread.title = "Mid-stream title"

        # Second assistant message, after which thread.updated should be emitted
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_b",
                content=[AssistantMessageContent(text="B")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

        # Continue streaming after the update event
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_c",
                content=[AssistantMessageContent(text="C")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )

        # Find the created thread
        thread = next(e.thread for e in events if isinstance(e, ThreadCreatedEvent))

        # Ensure a thread.updated event occurs right after assistant_b
        idx_b = next(
            i
            for i, e in enumerate(events)
            if isinstance(e, ThreadItemDoneEvent)
            and isinstance(e.item, AssistantMessageItem)
            and e.item.id == "assistant_b"
        )
        assert isinstance(events[idx_b + 1], ThreadUpdatedEvent)
        updated_event = cast(ThreadUpdatedEvent, events[idx_b + 1])
        assert updated_event.thread.title == "Mid-stream title"

        # Streaming continues after the update event
        assert isinstance(events[idx_b + 2], ThreadItemDoneEvent)
        done_event = cast(ThreadItemDoneEvent, events[idx_b + 2])
        assert isinstance(done_event.item, AssistantMessageItem)
        assert done_event.item.id == "assistant_c"

        # Persisted in the store
        saved = await server.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert saved.title == "Mid-stream title"


async def test_respond_with_tool_call():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        if isinstance(input, UserMessageItem):
            yield ThreadItemDoneEvent(
                item=ClientToolCallItem(
                    id="msg_1",
                    created_at=datetime.now(),
                    name="tool_call_1",
                    arguments={"arg1": "val1", "arg2": False},
                    call_id="tool_call_1",
                    thread_id=thread.id,
                ),
            )
        elif input is None:
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id="msg_2",
                    content=[
                        AssistantMessageContent(text="Glad the tool call succeeded!")
                    ],
                    created_at=datetime.now(),
                    thread_id=thread.id,
                ),
            )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )

        assert len(events) == 4
        assert events[0].type == "thread.created"
        thread = events[0].thread

        assert events[1].type == "thread.item.done"
        assert events[1].item.type == "user_message"

        assert events[2].type == "stream_options"

        assert events[3].type == "thread.item.done"
        assert events[3].item.type == "client_tool_call"
        assert events[3].item.id == "msg_1"
        assert events[3].item.name == "tool_call_1"
        assert events[3].item.arguments == {"arg1": "val1", "arg2": False}
        assert events[3].item.call_id == "tool_call_1"

        events = await server.process_streaming(
            ThreadsAddClientToolOutputReq(
                params=ThreadAddClientToolOutputParams(
                    thread_id=thread.id,
                    result={"text": "Wow!"},
                )
            )
        )

        assert len(events) == 2
        assert events[0].type == "stream_options"
        assert events[1].type == "thread.item.done"
        assert events[1].item.type == "assistant_message"


async def test_removes_tool_call_if_no_output_provided():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        assert isinstance(input, UserMessageItem)
        assert input.content[0].type == "input_text"
        if input.content[0].text == "Message 1":
            yield ThreadItemDoneEvent(
                item=ClientToolCallItem(
                    id="msg_1",
                    created_at=datetime.now(),
                    name="tool_call_1",
                    arguments={"arg1": "val1", "arg2": False},
                    call_id="tool_call_1",
                    thread_id=thread.id,
                ),
            )
        else:
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id="msg_2",
                    content=[AssistantMessageContent(text="All done!")],
                    created_at=datetime.now(),
                    thread_id=thread.id,
                ),
            )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Message 1")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        await server.process_streaming(
            ThreadsAddUserMessageReq(
                params=ThreadAddUserMessageParams(
                    thread_id=thread.id,
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Message 2")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    ),
                )
            )
        )

        items_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(items_result.json)
        assert len(items.data) == 3
        assert items.data[0].type == "assistant_message"
        assert items.data[1].type == "user_message"
        assert items.data[2].type == "user_message"


async def test_respond_with_tool_status():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ProgressUpdateEvent(text="Tool status")
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="msg_4",
                content=[AssistantMessageContent(text="Hello, world!")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )

        assert len(events) == 5
        assert events[0].type == "thread.created"
        assert events[1].type == "thread.item.done"
        assert events[2].type == "stream_options"
        assert events[3].type == "progress_update"
        assert events[4].type == "thread.item.done"


async def test_list_threads_response():
    with make_server() as server:
        for i in range(25):
            await server.process_streaming(
                ThreadsCreateReq(
                    params=ThreadCreateParams(
                        input=UserMessageInput(
                            content=[UserMessageTextContent(text=f"Thread {i}")],
                            attachments=[],
                            inference_options=InferenceOptions(),
                        )
                    )
                )
            )
        list_result = await server.process_non_streaming(
            ThreadsListReq(params=ThreadListParams(limit=20))
        )
        threads = TypeAdapter(Page[ThreadMetadata]).validate_json(list_result.json)
        assert len(threads.data) == 20

        # Newest first
        assert threads.data[0].created_at > threads.data[1].created_at
        assert threads.has_more is True
        assert threads.after is not None

        more_threads = await server.process_non_streaming(
            ThreadsListReq(params=ThreadListParams(after=threads.data[-1].id))
        )
        threads = TypeAdapter(Page[ThreadMetadata]).validate_json(more_threads.json)
        assert len(threads.data) == 5
        assert threads.has_more is False
        assert not threads.after


async def test_list_items_response():
    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        for i in range(25):
            yield ThreadItemDoneEvent(
                item=UserMessageItem(
                    id=f"msg_{i}",
                    content=[UserMessageTextContent(text=f"Message {i}")],
                    attachments=[],
                    inference_options=InferenceOptions(),
                    thread_id=thread.id,
                    created_at=datetime.now(),
                ),
            )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Thread 1")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json)
        assert len(items.data) == 20
        # Newest first
        assert items.data[0].created_at > items.data[1].created_at
        assert items.has_more is True
        assert items.after is not None

        list_result = await server.process_non_streaming(
            ItemsListReq(
                params=ItemsListParams(thread_id=thread.id, after=items.data[-1].id)
            )
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json)
        assert len(items.data) == 6  # +1 for user message
        assert items.has_more is False


async def test_calls_action():
    actions = []

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemDoneEvent(
            item=WidgetItem(
                id="widget_1",
                type="widget",
                created_at=datetime.now(),
                thread_id=thread.id,
                widget=Card(
                    children=[
                        Text(
                            key="text_1",
                            value="test",
                        )
                    ],
                ),
            ),
        )

    async def action(
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        actions.append((action, sender))
        assert sender

        yield ThreadItemUpdatedEvent(
            item_id=sender.id,
            update=WidgetRootUpdated(
                widget=Card(
                    children=[
                        Text(value="Email sent!"),
                    ]
                ),
            ),
        )

    with make_server(responder, action_callback=action) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Show widget")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        widget_item = next(
            event.item
            for event in events
            if isinstance(event, ThreadItemDoneEvent)
            and isinstance(event.item, WidgetItem)
        )

        events = await server.process_streaming(
            ThreadsCustomActionReq(
                params=ThreadCustomActionParams(
                    thread_id=thread.id,
                    item_id=widget_item.id,
                    action=Action(type="create_user", payload={"user_id": "123"}),
                )
            )
        )

        assert actions
        assert actions[0] == (
            Action(type="create_user", payload={"user_id": "123"}),
            widget_item,
        )

        assert len(events) == 2
        assert events[0].type == "stream_options"
        assert events[1].type == "thread.item.updated"
        assert isinstance(events[1], ThreadItemUpdatedEvent)
        assert events[1].update.type == "widget.root.updated"
        assert events[1].update.widget == Card(children=[Text(value="Email sent!")])


async def test_add_feedback():
    called = []

    def handle_feedback(thread_id, item_ids, feedback, context):
        called.append((thread_id, item_ids, feedback, context))

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_msg_1",
                content=[
                    AssistantMessageContent(text="Feedback received!"),
                ],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )
        yield ThreadItemDoneEvent(
            item=WidgetItem(
                id="widget_1",
                type="widget",
                created_at=datetime.now(),
                widget=Card(children=[Text(key="text", value="Widget content")]),
                thread_id=thread.id,
            ),
        )

    with make_server(responder, handle_feedback=handle_feedback) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Test feedback")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        await server.process_non_streaming(
            ItemsFeedbackReq(
                params=ItemFeedbackParams(
                    thread_id=thread.id,
                    item_ids=["assistant_msg_1"],
                    kind="positive",
                )
            )
        )
        await server.process_non_streaming(
            ItemsFeedbackReq(
                params=ItemFeedbackParams(
                    thread_id=thread.id,
                    item_ids=["widget_1"],
                    kind="negative",
                )
            )
        )

        assert len(called) == 2
        assert called[0][0] == thread.id
        assert called[0][1] == ["assistant_msg_1"]
        assert called[0][2] == "positive"

        assert called[1][0] == thread.id
        assert called[1][1] == ["widget_1"]
        assert called[1][2] == "negative"


async def test_get_thread_by_id():
    make_thread_items()

    with make_server() as server:
        # Create a thread by sending a ThreadCreateRequest
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Test thread")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        # Retrieve the thread by id
        result = await server.process_non_streaming(
            ThreadsGetByIdReq(
                params=ThreadGetByIdParams(thread_id=thread.id),
            )
        )
        loaded_thread = TypeAdapter(Thread).validate_json(result.json)
        assert loaded_thread.id == thread.id
        assert loaded_thread.title == thread.title
        assert loaded_thread.items.data[0].type == "user_message"
        assert loaded_thread.items.data[0].content[0].text == "Test thread"


async def test_create_file():
    store = InMemoryFileStore()
    file_name = "test-file-name"
    file_content_type = "text/plain"

    with make_server(file_store=store) as server:
        result = await server.process_non_streaming(
            AttachmentsCreateReq(
                params=AttachmentCreateParams(
                    name=file_name, size=1024, mime_type=file_content_type
                )
            )
        )
        attachment = TypeAdapter[Attachment](Attachment).validate_json(result.json)

        # Verify response includes file
        assert attachment.id is not None
        assert attachment.mime_type == file_content_type
        assert attachment.name == file_name
        assert attachment.type == "file"
        assert attachment.upload_url == AnyUrl(
            f"https://example.com/{attachment.id}/upload"
        )
        assert attachment.id in store.files


async def test_create_image_file():
    store = InMemoryFileStore()
    file_name = "test-file-name"
    file_content_type = "image/png"

    with make_server(file_store=store) as server:
        result = await server.process_non_streaming(
            AttachmentsCreateReq(
                params=AttachmentCreateParams(
                    name=file_name,
                    size=1024,
                    mime_type=file_content_type,
                )
            )
        )
        attachment = TypeAdapter[Attachment](Attachment).validate_json(result.json)

        assert attachment.id is not None
        assert attachment.mime_type == file_content_type
        assert attachment.name == file_name
        assert attachment.type == "image"
        assert attachment.preview_url == AnyUrl(
            f"https://example.com/{attachment.id}/preview"
        )
        assert attachment.upload_url == AnyUrl(
            f"https://example.com/{attachment.id}/upload"
        )

        assert attachment.id in store.files


async def test_create_file_without_filestore():
    with pytest.raises(RuntimeError):
        with make_server() as server:
            await server.process_non_streaming(
                AttachmentsCreateReq(
                    params=AttachmentCreateParams(
                        name="test-file-name",
                        size=1024,
                        mime_type="text/plain",
                    )
                )
            )


async def test_delete_file():
    store = InMemoryFileStore()
    store.files["test-file-id"] = {"id": "test-file-id"}
    with make_server(file_store=store) as server:
        await server.process_non_streaming(
            AttachmentsDeleteReq(
                params=AttachmentDeleteParams(attachment_id="test-file-id")
            )
        )
        assert store.files == {}


async def test_delete_file_without_filestore():
    with pytest.raises(RuntimeError):
        with make_server() as server:
            await server.process_non_streaming(
                AttachmentsDeleteReq(
                    params=AttachmentDeleteParams(attachment_id="test-file-id")
                )
            )


async def test_list_threads_paginated_response():
    with make_server() as server:
        for i in range(25):
            await server.process_streaming(
                ThreadsCreateReq(
                    params=ThreadCreateParams(
                        input=UserMessageInput(
                            content=[UserMessageTextContent(text=f"Thread {i}")],
                            attachments=[],
                            inference_options=InferenceOptions(),
                        )
                    )
                )
            )
        list_result = await server.process_non_streaming(
            ThreadsListReq(params=ThreadListParams(limit=20))
        )
        threads = TypeAdapter(Page[ThreadMetadata]).validate_json(list_result.json)
        assert len(threads.data) == 20
        assert threads.has_more is True
        assert threads.after is not None

        list_result = await server.process_non_streaming(
            ThreadsListReq(params=ThreadListParams(after=threads.data[-1].id))
        )
        threads = TypeAdapter(Page[ThreadMetadata]).validate_json(list_result.json)
        assert len(threads.data) == 5
        assert threads.has_more is False


async def test_threads_update_request():
    with make_server() as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        updated_thread = await server.process_non_streaming(
            ThreadsUpdateReq(
                params=ThreadUpdateParams(thread_id=thread.id, title="New Title")
            )
        )
        updated_thread = TypeAdapter[Thread](Thread).validate_json(updated_thread.json)
        assert updated_thread.title == "New Title"


async def test_returns_widget_item_generator():
    thread = ThreadMetadata(
        id="test-thread-id", title="Test thread", metadata={}, created_at=datetime.now()
    )

    def render_widget(i: int) -> Card:
        return Card(children=[Text(id="text", value="Hello, world"[:i])])

    async def widget_generator():
        yield render_widget(0)
        yield render_widget(3)
        yield render_widget(6)
        yield render_widget(12)

    events = [event async for event in stream_widget(thread, widget_generator())]

    assert len(events) == 5
    assert isinstance(events[0], ThreadItemAddedEvent)
    assert isinstance(events[0].item, WidgetItem)
    assert events[0].item.widget == Card(children=[Text(id="text", value="")])

    assert isinstance(events[1], ThreadItemUpdatedEvent)
    assert events[1].update.type == "widget.streaming_text.value_delta"
    assert events[1].update.component_id == "text"
    assert events[1].update.delta == "Hel"

    assert isinstance(events[2], ThreadItemUpdatedEvent)
    assert events[2].update.type == "widget.streaming_text.value_delta"
    assert events[2].update.component_id == "text"
    assert events[2].update.delta == "lo,"

    assert isinstance(events[3], ThreadItemUpdatedEvent)
    assert events[3].update.type == "widget.streaming_text.value_delta"
    assert events[3].update.component_id == "text"
    assert events[3].update.delta == " world"

    assert isinstance(events[4], ThreadItemDoneEvent)
    assert isinstance(events[4].item, WidgetItem)
    assert events[4].item.widget == Card(
        children=[Text(id="text", value="Hello, world")]
    )


async def test_returns_widget_item_generator_full_replace():
    thread = ThreadMetadata(
        id="test-thread-id", title="Test thread", metadata={}, created_at=datetime.now()
    )

    async def widget_generator():
        yield Card(children=[Text(id="text", value="Hello")])
        yield Card(children=[Text(id="text", value="World")])

    events = [event async for event in stream_widget(thread, widget_generator())]

    assert len(events) == 3
    assert isinstance(events[0], ThreadItemAddedEvent)
    assert isinstance(events[0].item, WidgetItem)
    assert events[0].item.widget == Card(children=[Text(id="text", value="Hello")])

    assert isinstance(events[1], ThreadItemUpdatedEvent)
    assert events[1].update.type == "widget.root.updated"
    assert events[1].update.widget == Card(children=[Text(id="text", value="World")])

    assert isinstance(events[2], ThreadItemDoneEvent)
    assert isinstance(events[2].item, WidgetItem)
    assert events[2].item.widget == Card(children=[Text(id="text", value="World")])


async def test_delete_thread():
    with make_server() as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Thread to delete")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        response = await server.process_non_streaming(
            ThreadsDeleteReq(params=ThreadDeleteParams(thread_id=thread.id))
        )
        assert response.json == b"{}"

        try:
            await server.process_non_streaming(
                ThreadsGetByIdReq(
                    params=ThreadGetByIdParams(thread_id=thread.id),
                )
            )
            assert False, "Expected ValueError for deleted thread"
        except NotFoundError as e:
            assert f"Thread {thread.id} not found" in str(e)


async def test_thread_item_removed_event_removes_item():
    removed_id = "msg_to_remove"

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemDoneEvent(
            item=UserMessageItem(
                id=removed_id,
                content=[UserMessageTextContent(text="To be removed")],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=datetime.now(),
            ),
        )
        yield ThreadItemRemovedEvent(item_id=removed_id)

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Trigger removal")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )
        assert any(
            e.type == "thread.item.removed" and e.item_id == removed_id for e in events
        )
        # The item should not be present in the store
        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json).data
        assert all(i.id != removed_id for i in items)


async def test_raising_in_responder_yields_error_event():
    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        raise ValueError("Test error")
        yield

    with make_server(responder) as server:
        result = await server.process(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Test error")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            ).model_dump_json(),
            RequestContext(user_id="test_user"),
        )
        assert isinstance(result, StreamingResult)
        iter = result.__aiter__()

        # Yield an errro
        async for e in iter:
            e = decode_event(e)
            if e.type == "error":
                assert e.code == ErrorCode.STREAM_ERROR
                break
        else:
            assert False, "Expected error event"

        # Then finish
        try:
            await iter.__anext__()
        except StopAsyncIteration:
            pass
        else:
            assert False, "Expected StopAsyncIteration"


async def test_thread_item_replaced_event_replaces_item():
    original_id = "msg_to_replace"

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        # First add an item
        yield ThreadItemDoneEvent(
            item=UserMessageItem(
                id=original_id,
                content=[UserMessageTextContent(text="Original content")],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=datetime.now(),
            ),
        )
        # Then replace it
        replacement_item = AssistantMessageItem(
            id=original_id,
            content=[AssistantMessageContent(text="This is the replacement content")],
            created_at=datetime.now(),
            thread_id=thread.id,
        )
        yield ThreadItemReplacedEvent(item=replacement_item)

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Trigger replacement")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        # Verify the replacement event was generated
        assert any(
            e.type == "thread.item.replaced" and e.item.id == original_id
            for e in events
        )

        # Verify the item was replaced in the store
        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json).data

        # Find the replaced item
        replaced_item = next((i for i in items if i.id == original_id), None)
        assert replaced_item is not None
        assert isinstance(replaced_item, AssistantMessageItem)
        assert isinstance(replaced_item.content[0], AssistantMessageContent)
        assert replaced_item.content[0].text == "This is the replacement content"


async def test_thread_item_replaced_event_with_widget():
    widget_id = "widget_to_replace"
    original_widget = Card(children=[Text(value="Original widget content")])
    replacement_widget = Card(children=[Text(value="Replaced widget content")])

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        # First add a widget item
        yield ThreadItemDoneEvent(
            item=WidgetItem(
                id=widget_id,
                widget=original_widget,
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )
        # Then replace it
        yield ThreadItemReplacedEvent(
            item=WidgetItem(
                id=widget_id,
                widget=replacement_widget,
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[
                            UserMessageTextContent(text="Trigger widget replacement")
                        ],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        # Verify the replacement event was generated
        replacement_event = next(
            (
                e
                for e in events
                if e.type == "thread.item.replaced" and e.item.id == widget_id
            ),
            None,
        )
        assert replacement_event is not None
        assert isinstance(replacement_event.item, WidgetItem)
        assert replacement_event.item.widget == replacement_widget

        # Verify the item was replaced in the store
        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json).data

        # Find the replaced widget item
        replaced_item = next((i for i in items if i.id == widget_id), None)
        assert replaced_item is not None
        assert isinstance(replaced_item, WidgetItem)
        assert isinstance(replaced_item.widget, Card)
        assert isinstance(replaced_item.widget.children[0], Text)
        assert replaced_item.widget.children[0].value == "Replaced widget content"


async def test_retry_after_item():
    responder_calls = []

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        responder_calls.append(input)

        if len(responder_calls) == 1:
            # First response - return an assistant message
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id="assistant_msg_1",
                    content=[AssistantMessageContent(text="First response")],
                    created_at=datetime.now(),
                    thread_id=thread.id,
                ),
            )
        else:
            # Retry response - return different content
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id="assistant_msg_2",
                    content=[AssistantMessageContent(text="Retried response")],
                    created_at=datetime.now(),
                    thread_id=thread.id,
                ),
            )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello, world!")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items_before = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json)
        assert len(items_before.data) == 2
        assert items_before.data[0].type == "assistant_message"
        assert items_before.data[0].content[0].type == "output_text"
        assert items_before.data[0].content[0].text == "First response"
        assert items_before.data[1].type == "user_message"
        assert items_before.data[1].content[0].text == "Hello, world!"

        # Get the user message ID for retrying after it
        user_message_id = items_before.data[1].id

        # Retry after the user message
        retry_events = await server.process_streaming(
            ThreadsRetryAfterItemReq(
                params=ThreadRetryAfterItemParams(
                    thread_id=thread.id, item_id=user_message_id
                )
            )
        )

        # Verify the retry generated new response
        assert len(retry_events) == 2
        assert retry_events[0].type == "stream_options"
        assert retry_events[1].type == "thread.item.done"
        assert retry_events[1].item.type == "assistant_message"
        assert retry_events[1].item.content[0].type == "output_text"
        assert retry_events[1].item.content[0].text == "Retried response"

        # Verify the responder was called twice with the same user message
        assert len(responder_calls) == 2
        assert responder_calls[0] == responder_calls[1]
        assert responder_calls[0].type == "user_message"
        assert responder_calls[0].content[0].text == "Hello, world!"

        # Verify the assistant response was replaced in storage
        list_result_after = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items_after = TypeAdapter(Page[ThreadItem]).validate_json(
            list_result_after.json
        )
        assert len(items_after.data) == 2  # Still user message + assistant message
        assert items_after.data[0].type == "assistant_message"
        assert items_after.data[0].content[0].type == "output_text"
        assert items_after.data[0].content[0].text == "Retried response"  # New response
        assert items_after.data[1].type == "user_message"
        assert items_after.data[1].content[0].text == "Hello, world!"


async def test_retry_after_item_invalid_item():
    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_msg_1",
                content=[AssistantMessageContent(text="Response")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        items_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items = TypeAdapter(Page[ThreadItem]).validate_json(items_result.json)
        assistant_item_id = items.data[0].id

        # Try to retry after an assistant message (should fail)
        with pytest.raises(ValueError, match="is not a user message"):
            await server.process_streaming(
                ThreadsRetryAfterItemReq(
                    params=ThreadRetryAfterItemParams(
                        thread_id=thread.id, item_id=assistant_item_id
                    )
                )
            )


async def test_retry_after_item_with_multiple_messages():
    responder_calls = []

    async def responder(
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        responder_calls.append(input)
        assert input is not None
        assert input.type == "user_message"
        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id=f"assistant_msg_{len(responder_calls)}",
                content=[
                    AssistantMessageContent(
                        text=f"Response to: {input.content[0].text}"
                    )
                ],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="First message")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            )
        )
        thread = next(
            event.thread for event in events if event.type == "thread.created"
        )

        await server.process_streaming(
            ThreadsAddUserMessageReq(
                params=ThreadAddUserMessageParams(
                    thread_id=thread.id,
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Second message")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    ),
                )
            )
        )

        # Verify we have 4 items: user1, assistant1, user2, assistant2
        list_result = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items_before = TypeAdapter(Page[ThreadItem]).validate_json(list_result.json)
        assert len(items_before.data) == 4

        # Get the second user message ID to retry after it
        second_user_message_id = items_before.data[1].id  # Second user message

        # Retry after the second user message
        retry_events = await server.process_streaming(
            ThreadsRetryAfterItemReq(
                params=ThreadRetryAfterItemParams(
                    thread_id=thread.id, item_id=second_user_message_id
                )
            )
        )

        assert len(retry_events) == 2
        assert retry_events[0].type == "stream_options"
        assert retry_events[1].type == "thread.item.done"

        # Verify retry used the second user message
        assert len(responder_calls) == 3  # Original 2 + 1 retry
        assert responder_calls[2].type == "user_message"
        assert responder_calls[2].content[0].text == "Second message"

        # Verify only the last assistant response was removed and regenerated
        list_result_after = await server.process_non_streaming(
            ItemsListReq(params=ItemsListParams(thread_id=thread.id))
        )
        items_after = TypeAdapter(Page[ThreadItem]).validate_json(
            list_result_after.json
        )
        assert len(items_after.data) == 4  # Still 4 items
        # First user message and response should remain unchanged
        assert items_after.data[3].type == "user_message"
        assert items_after.data[3].content[0].text == "First message"
        assert items_after.data[3].content[0].type == "input_text"
        assert items_after.data[3].content[0].text == "First message"
        assert items_after.data[2].type == "assistant_message"
        assert items_after.data[2].content[0].type == "output_text"
        assert items_after.data[2].content[0].text == "Response to: First message"
        # Second user message should remain, but assistant response should be new
        assert items_after.data[1].type == "user_message"
        assert items_after.data[1].content[0].text == "Second message"
        assert items_after.data[0].type == "assistant_message"
        assert items_after.data[0].content[0].type == "output_text"
        assert items_after.data[0].content[0].text == "Response to: Second message"
        assert items_after.data[0].id != items_before.data[0].id


async def test_threads_create_passes_tools_to_responder():
    tool_choice = ToolChoice(id="web_search")

    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        assert input is not None
        assert input.inference_options.tool_choice is not None
        assert input.inference_options.tool_choice.id == tool_choice.id

        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_msg_tools_create",
                content=[AssistantMessageContent(text="ok")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello with tools")],
                        attachments=[],
                        inference_options=InferenceOptions(tool_choice=tool_choice),
                    )
                )
            )
        )
        # Sanity check that the request flowed through.
        assert any(e.type == "thread.item.done" for e in events)


async def test_retry_after_item_passes_tools_to_responder():
    pass


async def test_threads_add_message_passes_tools_to_responder():
    tool_choice = ToolChoice(id="retrieval")

    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        assert input is not None
        assert input.inference_options.tool_choice is not None
        assert input.inference_options.tool_choice.id == tool_choice.id

        yield ThreadItemDoneEvent(
            item=AssistantMessageItem(
                id="assistant_msg_tools_add",
                content=[AssistantMessageContent(text="ok")],
                created_at=datetime.now(),
                thread_id=thread.id,
            ),
        )

    with make_server(responder) as server:
        # Create a thread first.
        events = await server.process_streaming(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Start")],
                        attachments=[],
                        inference_options=InferenceOptions(tool_choice=tool_choice),
                    )
                )
            )
        )
        thread = next(e.thread for e in events if e.type == "thread.created")

        # Add a message with tools and verify they reach the responder.
        events = await server.process_streaming(
            ThreadsAddUserMessageReq(
                params=ThreadAddUserMessageParams(
                    thread_id=thread.id,
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Second")],
                        attachments=[],
                        inference_options=InferenceOptions(tool_choice=tool_choice),
                    ),
                )
            )
        )
        # Sanity check that the request flowed through.
        assert any(e.type == "thread.item.done" for e in events)


async def test_custom_id_generators_on_server():
    class UniqueIdStore(SQLiteStore):
        def __init__(self, path):
            super().__init__(path)
            self.counter = 0

        def generate_thread_id(self, context) -> str:
            self.counter += 1
            return f"thr_custom_{self.counter}"

        def generate_item_id(
            self,
            item_type: str,
            thread: ThreadMetadata,
            context,
        ) -> str:
            self.counter += 1
            return f"{item_type}_custom_{self.counter}_{thread.id}"

    async def responder(
        thread: ThreadMetadata, input: UserMessageItem | None, context: Any
    ) -> AsyncIterator[ThreadStreamEvent]:
        # Emit a tool call to later verify tool_call_output id generation
        return
        yield

    with make_server(responder) as server:
        # Swap in our custom ID-generating store, reusing the same DB path.
        db_path = cast(SQLiteStore, server.store).db_path
        server.store = UniqueIdStore(db_path)

        # Create thread and verify thread id and user message id
        result = await server.process(
            ThreadsCreateReq(
                params=ThreadCreateParams(
                    input=UserMessageInput(
                        content=[UserMessageTextContent(text="Hello")],
                        attachments=[],
                        inference_options=InferenceOptions(),
                    )
                )
            ).model_dump_json(),
            DEFAULT_CONTEXT,
        )
        assert isinstance(result, StreamingResult)
        events = await decode_streaming_result(result)

        thread_created = next(e for e in events if e.type == "thread.created")
        assert thread_created.thread.id == "thr_custom_1"

        user_message = next(
            e.item
            for e in events
            if e.type == "thread.item.done" and e.item.type == "user_message"
        )
        assert user_message.id == "message_custom_2_thr_custom_1"
