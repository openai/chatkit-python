import asyncio
import base64
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import contextmanager
from datetime import datetime
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    Generic,
)

import agents
from agents.models.chatcmpl_helpers import (
    HEADERS_OVERRIDE as chat_completions_headers_override,
)
from agents.models.openai_responses import (
    _HEADERS_OVERRIDE as responses_headers_override,
)
from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypeVar, assert_never

from chatkit.errors import CustomStreamError, StreamError

from .logger import logger
from .store import AttachmentStore, Store, StoreItemType, default_generate_id
from .types import (
    Action,
    AssistantMessageContent,
    AssistantMessageContentPartAdded,
    AssistantMessageContentPartAnnotationAdded,
    AssistantMessageContentPartDone,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    AttachmentsCreateReq,
    AttachmentsDeleteReq,
    AudioInput,
    ChatKitReq,
    ClientToolCallItem,
    ErrorCode,
    ErrorEvent,
    FeedbackKind,
    HiddenContextItem,
    InputTranscribeReq,
    ItemsFeedbackReq,
    ItemsListReq,
    NonStreamingReq,
    Page,
    SDKHiddenContextItem,
    StreamingReq,
    StreamOptions,
    StreamOptionsEvent,
    Thread,
    ThreadCreatedEvent,
    ThreadItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemRemovedEvent,
    ThreadItemReplacedEvent,
    ThreadItemUpdatedEvent,
    ThreadMetadata,
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
    TranscriptionResult,
    UserMessageInput,
    UserMessageItem,
    WidgetComponentUpdated,
    WidgetItem,
    WidgetRootUpdated,
    WidgetStreamingTextValueDelta,
    WorkflowItem,
    WorkflowTaskAdded,
    WorkflowTaskUpdated,
    is_streaming_req,
)
from .version import __version__
from .widgets import WidgetComponent, WidgetComponentBase, WidgetRoot

DEFAULT_PAGE_SIZE = 20
DEFAULT_ERROR_MESSAGE = "An error occurred when generating a response."


def diff_widget(
    before: WidgetRoot, after: WidgetRoot
) -> list[WidgetStreamingTextValueDelta | WidgetRootUpdated | WidgetComponentUpdated]:
    """
    Compare two WidgetRoots and return a list of deltas.
    """

    def is_streaming_text(component: WidgetComponentBase) -> bool:
        return getattr(component, "type", None) in {"Markdown", "Text"} and isinstance(
            getattr(component, "value", None), str
        )

    def full_replace(before: WidgetComponentBase, after: WidgetComponentBase) -> bool:
        if (
            before.type != after.type
            or before.id != after.id
            or before.key != after.key
        ):
            return True

        def full_replace_value(before_value: Any, after_value: Any) -> bool:
            if isinstance(before_value, list) and isinstance(after_value, list):
                if len(before_value) != len(after_value):
                    return True
                for nth_before_value, nth_after_value in zip(before_value, after_value):
                    if full_replace_value(nth_before_value, nth_after_value):
                        return True
            elif before_value != after_value:
                if isinstance(before_value, WidgetComponentBase) and isinstance(
                    after_value, WidgetComponentBase
                ):
                    return full_replace(before_value, after_value)
                else:
                    return True
            return False

        for field in before.model_fields_set.union(after.model_fields_set):
            if (
                is_streaming_text(before)
                and is_streaming_text(after)
                and field == "value"
                and getattr(after, "value", "").startswith(getattr(before, "value", ""))
            ):
                # Appends to the value prop of Markdown or Text do not trigger a full replace
                continue
            if full_replace_value(getattr(before, field), getattr(after, field)):
                return True

        return False

    if full_replace(before, after):
        return [WidgetRootUpdated(widget=after)]

    deltas: list[
        WidgetStreamingTextValueDelta | WidgetComponentUpdated | WidgetRootUpdated
    ] = []

    def find_all_streaming_text_components(
        component: WidgetComponent | WidgetRoot,
    ) -> dict[str, WidgetComponentBase]:
        components = {}

        def recurse(component: WidgetComponent | WidgetRoot):
            if is_streaming_text(component) and component.id:
                components[component.id] = component

            if hasattr(component, "children"):
                children = getattr(component, "children", None) or []
                for child in children:
                    recurse(child)

        recurse(component)
        return components

    before_nodes = find_all_streaming_text_components(before)
    after_nodes = find_all_streaming_text_components(after)

    for id, after_node in after_nodes.items():
        before_node = before_nodes.get(id)
        if before_node is None:
            raise ValueError(
                f"Node {id} was not present when the widget was initially rendered. All nodes with ID must persist across all widget updates."
            )

        before_value = str(getattr(before_node, "value", None))
        after_value = str(getattr(after_node, "value", None))

        if before_value != after_value:
            if not after_value.startswith(before_value):
                raise ValueError(
                    f"Node {id} was updated with a new value that is not a prefix of the initial value. All widget updates must be cumulative."
                )
            done = not getattr(after_node, "streaming", False)
            deltas.append(
                WidgetStreamingTextValueDelta(
                    component_id=id,
                    delta=after_value[len(before_value) :],
                    done=done,
                )
            )

    return deltas


async def stream_widget(
    thread: ThreadMetadata,
    widget: WidgetRoot | AsyncGenerator[WidgetRoot, None],
    copy_text: str | None = None,
    generate_id: Callable[[StoreItemType], str] = default_generate_id,
) -> AsyncIterator[ThreadStreamEvent]:
    """Stream a widget root (or async sequence of roots) as ThreadStreamEvents."""
    item_id = generate_id("message")

    if not isinstance(widget, AsyncGenerator):
        yield ThreadItemDoneEvent(
            item=WidgetItem(
                id=item_id,
                thread_id=thread.id,
                created_at=datetime.now(),
                widget=widget,
                copy_text=copy_text,
            ),
        )
        return

    initial_state = await widget.__anext__()

    item = WidgetItem(
        id=item_id,
        created_at=datetime.now(),
        widget=initial_state,
        copy_text=copy_text,
        thread_id=thread.id,
    )

    yield ThreadItemAddedEvent(item=item)

    last_state = initial_state

    while widget:
        try:
            new_state = await widget.__anext__()
            for update in diff_widget(last_state, new_state):
                yield ThreadItemUpdatedEvent(
                    item_id=item_id,
                    update=update,
                )
            last_state = new_state
        except StopAsyncIteration:
            break

    yield ThreadItemDoneEvent(
        item=item.model_copy(update={"widget": last_state}),
    )


@contextmanager
def agents_sdk_user_agent_override():
    ua = f"Agents/Python {agents.__version__} ChatKit/Python {__version__}"
    chat_completions_token = chat_completions_headers_override.set({"User-Agent": ua})
    responses_token = responses_headers_override.set({"User-Agent": ua})

    yield

    chat_completions_headers_override.reset(chat_completions_token)
    responses_headers_override.reset(responses_token)


class StreamingResult(AsyncIterable[bytes]):
    def __init__(self, stream: AsyncGenerator[bytes, None]):
        self.json_events = stream

    async def __aiter__(self):
        async for event in self.json_events:
            yield event


class NonStreamingResult:
    def __init__(self, result: bytes):
        self.json = result


TContext = TypeVar("TContext", default=Any)


class ChatKitServer(ABC, Generic[TContext]):
    def __init__(
        self,
        store: Store[TContext],
        attachment_store: AttachmentStore[TContext] | None = None,
    ):
        """Create a ChatKitServer with the backing Store and optional AttachmentStore."""
        self.store = store
        self.attachment_store = attachment_store

    def _get_attachment_store(self) -> AttachmentStore[TContext]:
        """Return the configured AttachmentStore or raise if missing."""
        if self.attachment_store is None:
            raise RuntimeError(
                "AttachmentStore is not configured. Provide a AttachmentStore to ChatKitServer to handle file operations."
            )
        return self.attachment_store

    @abstractmethod
    def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: TContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Stream `ThreadStreamEvent` instances for a new user message.

        Args:
            thread: Metadata for the thread being processed.
            input_user_message: The incoming message the server should respond to, if any.
            context: Arbitrary per-request context provided by the caller.

        Returns:
            An async iterator that yields events representing the server's response.
        """
        pass

    async def add_feedback(  # noqa: B027
        self,
        thread_id: str,
        item_ids: list[str],
        feedback: FeedbackKind,
        context: TContext,
    ) -> None:
        """Persist user feedback for one or more thread items."""
        pass

    async def transcribe(  # noqa: B027
        self, audio_input: AudioInput, context: TContext
    ) -> TranscriptionResult:
        """Transcribe speech audio to text (dictation).

        Audio bytes are in `audio_input.data`. The raw MIME type is `audio_input.mime_type`; use
        `audio_input.media_type` for the base media type (one of: `audio/webm`, `audio/ogg`, `audio/mp4`).

        Args:
            audio_input: Audio bytes plus MIME type metadata for transcription.
            context: Arbitrary per-request context provided by the caller.

        Returns:
            A `TranscriptionResult` whose `text` is what should appear in the composer.
        """
        raise NotImplementedError(
            "transcribe() must be overridden to support the input.transcribe request."
        )

    def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: TContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Handle a widget or client-dispatched action and yield response events."""
        raise NotImplementedError(
            "The action() method must be overridden to react to actions. "
            "See https://github.com/openai/chatkit-python/blob/main/docs/widgets.md#widget-actions"
        )

    def get_stream_options(
        self, thread: ThreadMetadata, context: TContext
    ) -> StreamOptions:
        """
        Return stream-level runtime options. Allows the user to cancel the stream by default.
        Override this method to customize behavior.
        """
        return StreamOptions(allow_cancel=True)

    async def handle_stream_cancelled(
        self,
        thread: ThreadMetadata,
        pending_items: list[ThreadItem],
        context: TContext,
    ):
        """Perform custom cleanup / stop inference when a stream is cancelled.
        Updates you make here will not be reflected in the UI until a reload.

        The default implementation persists any non-empty pending assistant messages
        to the thread but does not auto-save pending widget items or workflow items.

        Args:
            thread: The thread that was being processed.
            pending_items: Items that were not done streaming at cancellation time.
            context: Arbitrary per-request context provided by the caller.
        """
        pending_assistant_message_items: list[AssistantMessageItem] = [
            item for item in pending_items if isinstance(item, AssistantMessageItem)
        ]
        for item in pending_assistant_message_items:
            is_empty = len(item.content) == 0 or all(
                (not content.text.strip()) for content in item.content
            )
            if not is_empty:
                await self.store.add_thread_item(thread.id, item, context=context)

        # Add a hidden context item to the thread to indicate that the stream was cancelled.
        # Otherwise, depending on the timing of the cancellation, subsequent responses may
        # attempt to continue the cancelled response.
        await self.store.add_thread_item(
            thread.id,
            SDKHiddenContextItem(
                thread_id=thread.id,
                created_at=datetime.now(),
                id=self.store.generate_item_id("sdk_hidden_context", thread, context),
                content="The user cancelled the stream. Stop responding to the prior request.",
            ),
            context=context,
        )

    async def process(
        self, request: str | bytes | bytearray, context: TContext
    ) -> StreamingResult | NonStreamingResult:
        """Parse an incoming ChatKit request and route it to streaming or non-streaming handlers."""
        parsed_request = TypeAdapter[ChatKitReq](ChatKitReq).validate_json(request)
        logger.info(f"Received request op: {parsed_request.type}")

        if is_streaming_req(parsed_request):
            return StreamingResult(self._process_streaming(parsed_request, context))
        else:
            return NonStreamingResult(
                await self._process_non_streaming(parsed_request, context)
            )

    async def _process_non_streaming(
        self, request: NonStreamingReq, context: TContext
    ) -> bytes:
        match request:
            case ThreadsGetByIdReq():
                thread = await self._load_full_thread(
                    request.params.thread_id, context=context
                )
                return self._serialize(self._to_thread_response(thread))
            case ThreadsListReq():
                params = request.params
                threads = await self.store.load_threads(
                    limit=params.limit or DEFAULT_PAGE_SIZE,
                    after=params.after,
                    order=params.order,
                    context=context,
                )
                return self._serialize(
                    Page(
                        has_more=threads.has_more,
                        after=threads.after,
                        data=[
                            self._to_thread_response(thread) for thread in threads.data
                        ],
                    )
                )
            case ItemsFeedbackReq():
                await self.add_feedback(
                    request.params.thread_id,
                    request.params.item_ids,
                    request.params.kind,
                    context,
                )
                return b"{}"
            case AttachmentsCreateReq():
                attachment_store = self._get_attachment_store()
                attachment = await attachment_store.create_attachment(
                    request.params, context
                )
                await self.store.save_attachment(attachment, context=context)
                return self._serialize(attachment)
            case AttachmentsDeleteReq():
                attachment_store = self._get_attachment_store()
                await attachment_store.delete_attachment(
                    request.params.attachment_id, context=context
                )
                await self.store.delete_attachment(
                    request.params.attachment_id, context=context
                )
                return b"{}"
            case InputTranscribeReq():
                audio_bytes = base64.b64decode(request.params.audio_base64)
                transcription_result = await self.transcribe(
                    AudioInput(data=audio_bytes, mime_type=request.params.mime_type),
                    context=context,
                )
                return self._serialize(transcription_result)
            case ItemsListReq():
                items_list_params = request.params
                items = await self.store.load_thread_items(
                    items_list_params.thread_id,
                    limit=items_list_params.limit or DEFAULT_PAGE_SIZE,
                    order=items_list_params.order,
                    after=items_list_params.after,
                    context=context,
                )
                # filter out hidden context items
                items.data = [
                    item
                    for item in items.data
                    if not isinstance(item, (HiddenContextItem, SDKHiddenContextItem))
                ]
                return self._serialize(items)
            case ThreadsUpdateReq():
                thread = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                thread.title = request.params.title
                await self.store.save_thread(thread, context=context)
                return self._serialize(self._to_thread_response(thread))
            case ThreadsDeleteReq():
                await self.store.delete_thread(
                    request.params.thread_id, context=context
                )
                return b"{}"
            case _:
                assert_never(request)

    async def _process_streaming(
        self, request: StreamingReq, context: TContext
    ) -> AsyncGenerator[bytes, None]:
        try:
            async for event in self._process_streaming_impl(request, context):
                b = self._serialize(event)
                yield b"data: " + b + b"\n\n"
        except asyncio.CancelledError:
            # Let cancellation bubble up without logging as an error.
            raise
        except Exception:
            logger.exception("Error while generating streamed response")
            raise

    async def _process_streaming_impl(
        self, request: StreamingReq, context: TContext
    ) -> AsyncGenerator[ThreadStreamEvent, None]:
        match request:
            case ThreadsCreateReq():
                thread = Thread(
                    id=self.store.generate_thread_id(context),
                    created_at=datetime.now(),
                    items=Page(),
                )
                await self.store.save_thread(
                    ThreadMetadata(**thread.model_dump()),
                    context=context,
                )
                yield ThreadCreatedEvent(thread=self._to_thread_response(thread))
                user_message = await self._build_user_message_item(
                    request.params.input, thread, context
                )
                async for event in self._process_new_thread_item_respond(
                    thread,
                    user_message,
                    context,
                ):
                    yield event

            case ThreadsAddUserMessageReq():
                thread = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                user_message = await self._build_user_message_item(
                    request.params.input, thread, context
                )
                async for event in self._process_new_thread_item_respond(
                    thread,
                    user_message,
                    context,
                ):
                    yield event

            case ThreadsAddClientToolOutputReq():
                thread = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                items = await self.store.load_thread_items(
                    thread.id, None, 1, "desc", context
                )
                tool_call = next(
                    (
                        item
                        for item in items.data
                        if isinstance(item, ClientToolCallItem)
                        and item.status == "pending"
                    ),
                    None,
                )
                if not tool_call:
                    raise ValueError(
                        f"Last thread item in {thread.id} was not a ClientToolCallItem"
                    )

                tool_call.output = request.params.result
                tool_call.status = "completed"

                await self.store.save_item(thread.id, tool_call, context=context)

                # Safety against dangling pending tool calls if there are
                # multiple in a row, which should be impossible, and
                # integrations should ultimately filter out pending tool calls
                # when creating input response messages.
                await self._cleanup_pending_client_tool_call(thread, context)

                async for event in self._process_events(
                    thread,
                    context,
                    lambda: self.respond(thread, None, context),
                ):
                    yield event

            case ThreadsRetryAfterItemReq():
                thread_metadata = await self.store.load_thread(
                    request.params.thread_id, context=context
                )

                # Collect items to remove (all items after the user message)
                items_to_remove: list[ThreadItem] = []
                user_message_item = None

                async for item in self._paginate_thread_items_reverse(
                    request.params.thread_id, context
                ):
                    if item.id == request.params.item_id:
                        if not isinstance(item, UserMessageItem):
                            raise ValueError(
                                f"Item {request.params.item_id} is not a user message"
                            )
                        user_message_item = item
                        break
                    items_to_remove.append(item)

                if user_message_item:
                    for item in items_to_remove:
                        await self.store.delete_thread_item(
                            request.params.thread_id, item.id, context=context
                        )
                    async for event in self._process_events(
                        thread_metadata,
                        context,
                        lambda: self.respond(
                            thread_metadata,
                            user_message_item,
                            context,
                        ),
                    ):
                        yield event
            case ThreadsCustomActionReq():
                thread_metadata = await self.store.load_thread(
                    request.params.thread_id, context=context
                )

                item: ThreadItem | None = None
                if request.params.item_id:
                    item = await self.store.load_item(
                        request.params.thread_id,
                        request.params.item_id,
                        context=context,
                    )

                if item and not isinstance(item, WidgetItem):
                    # shouldn't happen if the caller is using the API correctly.
                    yield ErrorEvent(
                        code=ErrorCode.STREAM_ERROR,
                        allow_retry=False,
                    )
                    return

                async for event in self._process_events(
                    thread_metadata,
                    context,
                    lambda: self.action(
                        thread_metadata,
                        request.params.action,
                        item,
                        context,
                    ),
                ):
                    yield event

            case _:
                assert_never(request)

    async def _cleanup_pending_client_tool_call(
        self, thread: ThreadMetadata, context: TContext
    ) -> None:
        items = await self.store.load_thread_items(
            thread.id, None, DEFAULT_PAGE_SIZE, "desc", context
        )
        for tool_call in items.data:
            if not isinstance(tool_call, ClientToolCallItem):
                continue
            if tool_call.status == "pending":
                logger.warning(
                    f"Client tool call {tool_call.call_id} was not completed, ignoring"
                )
                await self.store.delete_thread_item(
                    thread.id, tool_call.id, context=context
                )

    async def _process_new_thread_item_respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem,
        context: TContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        # Store the updated attachments (now that they have a thread id).
        for attachment in item.attachments:
            await self.store.save_attachment(attachment, context=context)

        await self.store.add_thread_item(thread.id, item, context=context)
        yield ThreadItemDoneEvent(item=item)

        async for event in self._process_events(
            thread,
            context,
            lambda: self.respond(thread, item, context),
        ):
            yield event

    async def _process_events(
        self,
        thread: ThreadMetadata,
        context: TContext,
        stream: Callable[[], AsyncIterator[ThreadStreamEvent]],
    ) -> AsyncIterator[ThreadStreamEvent]:
        await asyncio.sleep(0)  # allow the response to start streaming

        # Send initial stream options
        yield StreamOptionsEvent(
            stream_options=self.get_stream_options(thread, context)
        )

        last_thread = thread.model_copy(deep=True)

        # Keep track of items that were streamed but not yet saved
        # so that we can persist them when the stream is cancelled.
        pending_items: dict[str, ThreadItem] = {}

        try:
            with agents_sdk_user_agent_override():
                async for event in stream():
                    if isinstance(event, ThreadItemAddedEvent):
                        # Stash an isolated copy in case we need to persist unfinished items
                        # on cancellation; downstream handlers keep using the original event.item.
                        pending_items[event.item.id] = event.item.model_copy(deep=True)

                    match event:
                        case ThreadItemDoneEvent():
                            await self.store.add_thread_item(
                                thread.id, event.item, context=context
                            )
                            pending_items.pop(event.item.id, None)
                        case ThreadItemRemovedEvent():
                            await self.store.delete_thread_item(
                                thread.id, event.item_id, context=context
                            )
                            pending_items.pop(event.item_id, None)
                        case ThreadItemReplacedEvent():
                            await self.store.save_item(
                                thread.id, event.item, context=context
                            )
                            pending_items.pop(event.item.id, None)
                        case ThreadItemUpdatedEvent():
                            # Keep pending assistant message and workflow items up to date
                            # so that we have a reference to the latest version of these pending items
                            # when the stream is cancelled.
                            self._update_pending_items(pending_items, event)

                    # special case - don't send hidden context items back to the client
                    should_swallow_event = isinstance(
                        event, ThreadItemDoneEvent
                    ) and isinstance(
                        event.item, (HiddenContextItem, SDKHiddenContextItem)
                    )

                    if not should_swallow_event:
                        yield event

                    # in case user updated the thread while streaming
                    if thread != last_thread:
                        last_thread = thread.model_copy(deep=True)
                        await self.store.save_thread(thread, context=context)
                        yield ThreadUpdatedEvent(
                            thread=self._to_thread_response(thread)
                        )
                # in case user updated the thread while streaming
                if thread != last_thread:
                    last_thread = thread.model_copy(deep=True)
                    await self.store.save_thread(thread, context=context)
                    yield ThreadUpdatedEvent(thread=self._to_thread_response(thread))
        except asyncio.CancelledError:
            await self.handle_stream_cancelled(
                thread, list(pending_items.values()), context
            )
            raise
        except CustomStreamError as e:
            yield ErrorEvent(
                code="custom",
                message=e.message,
                allow_retry=e.allow_retry,
            )
        except StreamError as e:
            yield ErrorEvent(
                code=e.code,
                allow_retry=e.allow_retry,
            )
        except Exception as e:
            yield ErrorEvent(
                code=ErrorCode.STREAM_ERROR,
                allow_retry=True,
            )
            logger.exception(e)

        if thread != last_thread:
            # in case user updated the thread at the end of the stream
            await self.store.save_thread(thread, context=context)
            yield ThreadUpdatedEvent(thread=self._to_thread_response(thread))

    def _apply_assistant_message_update(
        self,
        item: AssistantMessageItem,
        update: AssistantMessageContentPartAdded
        | AssistantMessageContentPartTextDelta
        | AssistantMessageContentPartAnnotationAdded
        | AssistantMessageContentPartDone,
    ) -> AssistantMessageItem:
        # Pad the content list so the requested content_index exists before we write into it.
        # (Streaming updates can arrive for an index that hasn’t been created yet)
        while len(item.content) <= update.content_index:
            item.content.append(AssistantMessageContent(text="", annotations=[]))

        match update:
            case AssistantMessageContentPartAdded():
                item.content[update.content_index] = update.content
            case AssistantMessageContentPartTextDelta():
                item.content[update.content_index].text += update.delta
            case AssistantMessageContentPartAnnotationAdded():
                annotations = item.content[update.content_index].annotations
                if update.annotation_index <= len(annotations):
                    annotations.insert(update.annotation_index, update.annotation)
                else:
                    annotations.append(update.annotation)
            case AssistantMessageContentPartDone():
                item.content[update.content_index] = update.content
        return item

    def _update_pending_items(
        self,
        pending_items: dict[str, ThreadItem],
        event: ThreadItemUpdatedEvent,
    ):
        updated_item = pending_items.get(event.item_id)
        update = event.update
        match updated_item:
            case AssistantMessageItem():
                if isinstance(
                    update,
                    (
                        AssistantMessageContentPartAdded,
                        AssistantMessageContentPartTextDelta,
                        AssistantMessageContentPartAnnotationAdded,
                        AssistantMessageContentPartDone,
                    ),
                ):
                    pending_items[updated_item.id] = (
                        self._apply_assistant_message_update(updated_item, update)
                    )
            case WorkflowItem():
                if isinstance(update, (WorkflowTaskUpdated, WorkflowTaskAdded)):
                    match update:
                        case WorkflowTaskUpdated():
                            updated_item.workflow.tasks[update.task_index] = update.task
                        case WorkflowTaskAdded():
                            updated_item.workflow.tasks.append(update.task)

                    pending_items[updated_item.id] = updated_item
            case _:
                pass

    async def _build_user_message_item(
        self, input: UserMessageInput, thread: ThreadMetadata, context: TContext
    ) -> UserMessageItem:
        return UserMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            content=input.content,
            thread_id=thread.id,
            attachments=[
                (await self.store.load_attachment(attachment_id, context)).model_copy(
                    update={"thread_id": thread.id}
                )
                for attachment_id in input.attachments
            ],
            quoted_text=input.quoted_text,
            inference_options=input.inference_options,
            created_at=datetime.now(),
        )

    async def _load_full_thread(self, thread_id: str, context: TContext) -> Thread:
        thread_meta = await self.store.load_thread(thread_id, context=context)
        thread_items = await self.store.load_thread_items(
            thread_id,
            after=None,
            limit=DEFAULT_PAGE_SIZE,
            order="asc",
            context=context,
        )
        return Thread(**thread_meta.model_dump(), items=thread_items)

    async def _paginate_thread_items_reverse(
        self, thread_id: str, context: TContext
    ) -> AsyncIterator[ThreadItem]:
        """Paginate through thread items in reverse order (newest first)."""
        after = None
        while True:
            items = await self.store.load_thread_items(
                thread_id, after, DEFAULT_PAGE_SIZE, "desc", context
            )
            for item in items.data:
                yield item

            if not items.has_more:
                break
            after = items.after

    def _serialize(self, obj: BaseModel) -> bytes:
        return obj.model_dump_json(
            by_alias=True,
            exclude_none=True,
            context={"exclude_metadata": True},
        ).encode("utf-8")

    def _to_thread_response(self, thread: ThreadMetadata | Thread) -> Thread:
        def is_hidden(item: ThreadItem) -> bool:
            return isinstance(item, (HiddenContextItem, SDKHiddenContextItem))

        items = thread.items if isinstance(thread, Thread) else Page()
        items.data = [item for item in items.data if not is_hidden(item)]

        return Thread(
            id=thread.id,
            title=thread.title,
            created_at=thread.created_at,
            items=items,
            status=thread.status,
        )
