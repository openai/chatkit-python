from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal

from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    SerializationInfo,
    model_serializer,
)
from typing_extensions import Annotated, TypeIs, TypeVar

from chatkit.errors import ErrorCode

from .actions import Action
from .icons import IconName
from .widgets import WidgetComponent, WidgetRoot

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated collection of records returned from the API."""

    data: list[T] = []
    has_more: bool = False
    after: str | None = None


### REQUEST TYPES


class BaseReq(BaseModel):
    """Base class for all request payloads."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Arbitrary integration-specific metadata."""


class ThreadsGetByIdReq(BaseReq):
    """Request to fetch a single thread by its identifier."""

    type: Literal["threads.get_by_id"] = "threads.get_by_id"
    params: ThreadGetByIdParams


class ThreadGetByIdParams(BaseModel):
    """Parameters for retrieving a thread by id."""

    thread_id: str


class ThreadsCreateReq(BaseReq):
    """Request to create a new thread from a user message."""

    type: Literal["threads.create"] = "threads.create"
    params: ThreadCreateParams


class ThreadCreateParams(BaseModel):
    """User input required to create a thread."""

    input: UserMessageInput


class ThreadListParams(BaseModel):
    """Pagination parameters for listing threads."""

    limit: int | None = None
    order: Literal["asc", "desc"] = "desc"
    after: str | None = None


class ThreadsListReq(BaseReq):
    """Request to list threads."""

    type: Literal["threads.list"] = "threads.list"
    params: ThreadListParams


class ThreadsAddUserMessageReq(BaseReq):
    """Request to append a user message to a thread."""

    type: Literal["threads.add_user_message"] = "threads.add_user_message"
    params: ThreadAddUserMessageParams


class ThreadAddUserMessageParams(BaseModel):
    """Parameters for adding a user message to a thread."""

    input: UserMessageInput
    thread_id: str


class ThreadsAddClientToolOutputReq(BaseReq):
    """Request to add a client tool's output to a thread."""

    type: Literal["threads.add_client_tool_output"] = "threads.add_client_tool_output"
    params: ThreadAddClientToolOutputParams


class ThreadAddClientToolOutputParams(BaseModel):
    """Parameters for recording tool output in a thread."""

    thread_id: str
    result: Any


class ThreadsCustomActionReq(BaseReq):
    """Request to execute a custom action within a thread."""

    type: Literal["threads.custom_action"] = "threads.custom_action"
    params: ThreadCustomActionParams


class ThreadCustomActionParams(BaseModel):
    """Parameters describing the custom action to execute."""

    thread_id: str
    item_id: str | None = None
    action: Action[str, Any]


class ThreadsRetryAfterItemReq(BaseReq):
    """Request to retry processing after a specific thread item."""

    type: Literal["threads.retry_after_item"] = "threads.retry_after_item"
    params: ThreadRetryAfterItemParams


class ThreadRetryAfterItemParams(BaseModel):
    """Parameters specifying which item to retry."""

    thread_id: str
    item_id: str


class ItemsFeedbackReq(BaseReq):
    """Request to submit feedback on specific items."""

    type: Literal["items.feedback"] = "items.feedback"
    params: ItemFeedbackParams


class ItemFeedbackParams(BaseModel):
    """Parameters describing feedback targets and sentiment."""

    thread_id: str
    item_ids: list[str]
    kind: FeedbackKind


class AttachmentsDeleteReq(BaseReq):
    """Request to remove an attachment."""

    type: Literal["attachments.delete"] = "attachments.delete"
    params: AttachmentDeleteParams


class AttachmentDeleteParams(BaseModel):
    """Parameters identifying an attachment to delete."""

    attachment_id: str


class AttachmentsCreateReq(BaseReq):
    """Request to register a new attachment."""

    type: Literal["attachments.create"] = "attachments.create"
    params: AttachmentCreateParams


class AttachmentCreateParams(BaseModel):
    """Metadata needed to initialize an attachment."""

    name: str
    size: int
    mime_type: str


class InputTranscribeReq(BaseReq):
    """Request to transcribe an audio payload into text."""

    type: Literal["input.transcribe"] = "input.transcribe"
    params: InputTranscribeParams


class InputTranscribeParams(BaseModel):
    """Parameters for speech transcription."""

    audio_base64: str
    """Base64-encoded audio bytes."""

    mime_type: str
    """Raw MIME type for the audio payload, e.g. "audio/webm;codecs=opus"."""


class AudioInput(BaseModel):
    """Audio input data for transcription."""

    data: bytes
    """Audio data bytes."""

    mime_type: str
    """Raw MIME type for the audio payload, e.g. "audio/webm;codecs=opus"."""

    @property
    def media_type(self) -> str:
        """Media type for the audio payload, e.g. "audio/webm"."""
        return self.mime_type.split(";", 1)[0]


class TranscriptionResult(BaseModel):
    """Input speech transcription result."""

    text: str


class ItemsListReq(BaseReq):
    """Request to list items inside a thread."""

    type: Literal["items.list"] = "items.list"
    params: ItemsListParams


class ItemsListParams(BaseModel):
    """Pagination parameters for listing thread items."""

    thread_id: str
    limit: int | None = None
    order: Literal["asc", "desc"] = "desc"
    after: str | None = None


class ThreadsUpdateReq(BaseReq):
    """Request to update thread metadata."""

    type: Literal["threads.update"] = "threads.update"
    params: ThreadUpdateParams


class ThreadUpdateParams(BaseModel):
    """Parameters for updating a thread's properties."""

    thread_id: str
    title: str


class ThreadsDeleteReq(BaseReq):
    """Request to delete a thread."""

    type: Literal["threads.delete"] = "threads.delete"
    params: ThreadDeleteParams


class ThreadDeleteParams(BaseModel):
    """Parameters identifying a thread to delete."""

    thread_id: str


StreamingReq = (
    ThreadsCreateReq
    | ThreadsAddUserMessageReq
    | ThreadsAddClientToolOutputReq
    | ThreadsRetryAfterItemReq
    | ThreadsCustomActionReq
)
"""Union of request types that produce streaming responses."""


NonStreamingReq = (
    ThreadsGetByIdReq
    | ThreadsListReq
    | ItemsListReq
    | ItemsFeedbackReq
    | AttachmentsCreateReq
    | AttachmentsDeleteReq
    | ThreadsUpdateReq
    | ThreadsDeleteReq
    | InputTranscribeReq
)
"""Union of request types that yield immediate responses."""


ChatKitReq = Annotated[
    StreamingReq | NonStreamingReq,
    Field(discriminator="type"),
]


def is_streaming_req(request: ChatKitReq) -> TypeIs[StreamingReq]:
    """Return True if the given request should be processed as streaming."""
    return isinstance(
        request,
        (
            ThreadsCreateReq,
            ThreadsAddUserMessageReq,
            ThreadsRetryAfterItemReq,
            ThreadsAddClientToolOutputReq,
            ThreadsCustomActionReq,
        ),
    )


### THREAD STREAM EVENT TYPES


class ThreadCreatedEvent(BaseModel):
    """Event emitted when a thread is created."""

    type: Literal["thread.created"] = "thread.created"
    thread: Thread


class ThreadUpdatedEvent(BaseModel):
    """Event emitted when a thread is updated."""

    type: Literal["thread.updated"] = "thread.updated"
    thread: Thread


class ThreadItemAddedEvent(BaseModel):
    """Event emitted when a new item is added to a thread."""

    type: Literal["thread.item.added"] = "thread.item.added"
    item: ThreadItem


class ThreadItemUpdatedEvent(BaseModel):
    """Event describing an update to an existing thread item."""

    type: Literal["thread.item.updated"] = "thread.item.updated"
    item_id: str
    update: ThreadItemUpdate


# Type alias for backwards compatibility
ThreadItemUpdated = ThreadItemUpdatedEvent


class ThreadItemDoneEvent(BaseModel):
    """Event emitted when a thread item is marked complete."""

    type: Literal["thread.item.done"] = "thread.item.done"
    item: ThreadItem


class ThreadItemRemovedEvent(BaseModel):
    """Event emitted when a thread item is removed."""

    type: Literal["thread.item.removed"] = "thread.item.removed"
    item_id: str


class ThreadItemReplacedEvent(BaseModel):
    """Event emitted when a thread item is replaced."""

    type: Literal["thread.item.replaced"] = "thread.item.replaced"
    item: ThreadItem


class StreamOptions(BaseModel):
    """Settings that control runtime stream behavior."""

    allow_cancel: bool
    """Allow the client to request cancellation mid-stream."""


class StreamOptionsEvent(BaseModel):
    """Event emitted to set stream options at runtime."""

    type: Literal["stream_options"] = "stream_options"
    stream_options: StreamOptions


class ProgressUpdateEvent(BaseModel):
    """Event providing incremental progress from the assistant."""

    type: Literal["progress_update"] = "progress_update"
    icon: IconName | None = None
    text: str


class ClientEffectEvent(BaseModel):
    """Event emitted to trigger a client side-effect."""

    type: Literal["client_effect"] = "client_effect"
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(BaseModel):
    """Event indicating an error occurred while processing a thread."""

    type: Literal["error"] = "error"
    code: ErrorCode | Literal["custom"] = Field(default="custom")
    message: str | None = None
    allow_retry: bool = Field(default=False)


class NoticeEvent(BaseModel):
    """Event conveying a user-facing notice."""

    type: Literal["notice"] = "notice"
    level: Literal["info", "warning", "danger"]
    message: str
    """
    Supports markdown e.g. "You've reached your limit of 100 messages. [Upgrade](https://...) to a paid plan."
    """
    title: str | None = None


ThreadStreamEvent = Annotated[
    ThreadCreatedEvent
    | ThreadUpdatedEvent
    | ThreadItemDoneEvent
    | ThreadItemAddedEvent
    | ThreadItemUpdated
    | ThreadItemRemovedEvent
    | ThreadItemReplacedEvent
    | StreamOptionsEvent
    | ProgressUpdateEvent
    | ClientEffectEvent
    | ErrorEvent
    | NoticeEvent,
    Field(discriminator="type"),
]
"""Union of all streaming events emitted to clients."""

### THREAD ITEM UPDATE TYPES


class AssistantMessageContentPartAdded(BaseModel):
    """Event emitted when new assistant content is appended."""

    type: Literal["assistant_message.content_part.added"] = (
        "assistant_message.content_part.added"
    )
    content_index: int
    content: AssistantMessageContent


class AssistantMessageContentPartTextDelta(BaseModel):
    """Event carrying incremental assistant text output."""

    type: Literal["assistant_message.content_part.text_delta"] = (
        "assistant_message.content_part.text_delta"
    )
    content_index: int
    delta: str


class AssistantMessageContentPartAnnotationAdded(BaseModel):
    """Event announcing a new annotation on assistant content."""

    type: Literal["assistant_message.content_part.annotation_added"] = (
        "assistant_message.content_part.annotation_added"
    )
    content_index: int
    annotation_index: int
    annotation: Annotation


class AssistantMessageContentPartDone(BaseModel):
    """Event indicating an assistant content part is finalized."""

    type: Literal["assistant_message.content_part.done"] = (
        "assistant_message.content_part.done"
    )
    content_index: int
    content: AssistantMessageContent


class WidgetStreamingTextValueDelta(BaseModel):
    """Event streaming widget text deltas."""

    type: Literal["widget.streaming_text.value_delta"] = (
        "widget.streaming_text.value_delta"
    )
    component_id: str
    delta: str
    done: bool


class WidgetRootUpdated(BaseModel):
    """Event published when the widget root changes."""

    type: Literal["widget.root.updated"] = "widget.root.updated"
    widget: WidgetRoot


class WidgetComponentUpdated(BaseModel):
    """Event emitted when a widget component updates."""

    type: Literal["widget.component.updated"] = "widget.component.updated"
    component_id: str
    component: WidgetComponent


class WorkflowTaskAdded(BaseModel):
    """Event emitted when a workflow task is added."""

    type: Literal["workflow.task.added"] = "workflow.task.added"
    task_index: int
    task: Task


class WorkflowTaskUpdated(BaseModel):
    """Event emitted when a workflow task is updated."""

    type: Literal["workflow.task.updated"] = "workflow.task.updated"
    task_index: int
    task: Task


class GeneratedImageUpdated(BaseModel):
    """Event emitted when a generated image is updated."""

    type: Literal["generated_image.updated"] = "generated_image.updated"
    image: GeneratedImage
    progress: float | None = None


ThreadItemUpdate = (
    AssistantMessageContentPartAdded
    | AssistantMessageContentPartTextDelta
    | AssistantMessageContentPartAnnotationAdded
    | AssistantMessageContentPartDone
    | WidgetStreamingTextValueDelta
    | WidgetComponentUpdated
    | WidgetRootUpdated
    | WorkflowTaskAdded
    | WorkflowTaskUpdated
    | GeneratedImageUpdated
)
"""Union of possible updates applied to thread items."""


### THREAD TYPES


class ThreadMetadata(BaseModel):
    """Metadata describing a thread without its items."""

    title: str | None = None
    id: str
    created_at: datetime
    status: ThreadStatus = Field(default_factory=lambda: ActiveStatus())
    # TODO - make not client rendered
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveStatus(BaseModel):
    """Status indicating the thread is active."""

    type: Literal["active"] = Field(default="active", frozen=True)


class LockedStatus(BaseModel):
    """Status indicating the thread is locked."""

    type: Literal["locked"] = Field(default="locked", frozen=True)
    reason: str | None = None


class ClosedStatus(BaseModel):
    """Status indicating the thread is closed."""

    type: Literal["closed"] = Field(default="closed", frozen=True)
    reason: str | None = None


ThreadStatus = Annotated[
    ActiveStatus | LockedStatus | ClosedStatus,
    Field(discriminator="type"),
]
"""Union of lifecycle states for a thread."""


class Thread(ThreadMetadata):
    """Thread with its paginated items."""

    items: Page[ThreadItem]


### THREAD ITEM TYPES


class ThreadItemBase(BaseModel):
    """Base fields shared by all thread items."""

    id: str
    thread_id: str
    created_at: datetime


class UserMessageItem(ThreadItemBase):
    """Thread item representing a user message."""

    type: Literal["user_message"] = "user_message"
    content: list[UserMessageContent]
    attachments: list[Attachment] = Field(default_factory=list)
    quoted_text: str | None = None
    inference_options: InferenceOptions


class AssistantMessageItem(ThreadItemBase):
    """Thread item representing an assistant message."""

    type: Literal["assistant_message"] = "assistant_message"
    content: list[AssistantMessageContent]


class ClientToolCallItem(ThreadItemBase):
    """Thread item capturing a client tool call."""

    type: Literal["client_tool_call"] = "client_tool_call"
    status: Literal["pending", "completed"] = "pending"
    call_id: str
    name: str
    arguments: dict[str, Any]
    output: Any | None = None


class WidgetItem(ThreadItemBase):
    """Thread item containing widget content."""

    type: Literal["widget"] = "widget"
    widget: WidgetRoot
    copy_text: str | None = None


class GeneratedImage(BaseModel):
    """Generated image."""

    id: str
    url: str


class GeneratedImageItem(ThreadItemBase):
    """Thread item containing a generated image."""

    type: Literal["generated_image"] = "generated_image"
    image: GeneratedImage | None = None


class TaskItem(ThreadItemBase):
    """Thread item containing a task."""

    type: Literal["task"] = "task"
    task: Task


class WorkflowItem(ThreadItemBase):
    """Thread item representing a workflow."""

    type: Literal["workflow"] = "workflow"
    workflow: Workflow


class EndOfTurnItem(ThreadItemBase):
    """Marker item indicating the assistant ends its turn."""

    type: Literal["end_of_turn"] = "end_of_turn"


class HiddenContextItem(ThreadItemBase):
    """
    HiddenContext is never sent to the client. It's not officially part of ChatKit.js.
    It is only used internally to store additional context in a specific place in the thread.
    """

    type: Literal["hidden_context_item"] = "hidden_context_item"
    content: Any


class SDKHiddenContextItem(ThreadItemBase):
    """
    Hidden context that is used by the ChatKit Python SDK for storing additional context
    for internal operations.
    """

    type: Literal["sdk_hidden_context"] = "sdk_hidden_context"
    content: str


ThreadItem = Annotated[
    UserMessageItem
    | AssistantMessageItem
    | ClientToolCallItem
    | WidgetItem
    | GeneratedImageItem
    | WorkflowItem
    | TaskItem
    | HiddenContextItem
    | SDKHiddenContextItem
    | EndOfTurnItem,
    Field(discriminator="type"),
]
"""Union of all thread item variants."""


### ASSISTANT MESSAGE TYPES


class AssistantMessageContent(BaseModel):
    """Assistant message content consisting of text and annotations."""

    annotations: list[Annotation] = Field(default_factory=list)
    text: str
    type: Literal["output_text"] = "output_text"


class Annotation(BaseModel):
    """Reference to supporting context attached to assistant output."""

    type: Literal["annotation"] = "annotation"
    source: URLSource | FileSource | EntitySource
    index: int | None = None


### USER MESSAGE TYPES


class UserMessageInput(BaseModel):
    """Payload describing a user message submission."""

    content: list[UserMessageContent]
    attachments: list[str]
    quoted_text: str | None = None
    inference_options: InferenceOptions


class UserMessageTextContent(BaseModel):
    """User message content containing plaintext."""

    type: Literal["input_text"] = "input_text"
    text: str


class UserMessageTagContent(BaseModel):
    """User message content representing an interactive tag."""

    type: Literal["input_tag"] = "input_tag"
    id: str
    text: str
    data: dict[str, Any]
    group: str | None = None
    interactive: bool = False


UserMessageContent = Annotated[
    UserMessageTextContent | UserMessageTagContent, Field(discriminator="type")
]
"""Union of allowed user message content payloads."""


class InferenceOptions(BaseModel):
    """Model and tool configuration for message processing."""

    tool_choice: ToolChoice | None = None
    model: str | None = None


class ToolChoice(BaseModel):
    """Explicit tool selection for the assistant to invoke."""

    id: str


class AttachmentUploadDescriptor(BaseModel):
    """Two-phase upload instructions."""

    url: AnyUrl
    method: Literal["POST", "PUT"]
    """The HTTP method to use when uploading the file for two-phase upload."""
    headers: dict[str, str] = Field(default_factory=dict)
    """Optional headers to include in the upload request."""


class AttachmentBase(BaseModel):
    """Base metadata shared by all attachments."""

    id: str
    name: str
    mime_type: str
    upload_descriptor: AttachmentUploadDescriptor | None = None
    """
    Two-phase upload instructions.
    Should be set to None after upload is complete or when using direct upload
    where uploading happens when creating the attachment object.
    """
    thread_id: str | None = None
    """
    The thread the attachment belongs to, if any.
    Added when the user message that contains the attachment is saved to store.
    """
    metadata: dict[str, Any] | None = None
    """
    Integration-only metadata stored with the attachment. Ignored by ChatKit and not
    returned in ChatKitServer responses. If you serialize attachments from a custom
    direct-upload endpoint and want to omit this field, pass context={"exclude_metadata": True}.
    """

    @model_serializer(mode="wrap")
    def _serialize(self, serializer, info: SerializationInfo):
        data = serializer(self)
        if isinstance(data, dict) and (info.context or {}).get("exclude_metadata"):
            data.pop("metadata", None)
        return data


class FileAttachment(AttachmentBase):
    """Attachment representing a generic file."""

    type: Literal["file"] = "file"


class ImageAttachment(AttachmentBase):
    """Attachment representing an image resource."""

    type: Literal["image"] = "image"
    preview_url: AnyUrl


Attachment = Annotated[
    FileAttachment | ImageAttachment,
    Field(discriminator="type"),
]
"""Union of supported attachment types."""


### WORKFLOW TYPES


class Workflow(BaseModel):
    """Workflow attached to a thread with optional summary."""

    type: Literal["custom", "reasoning"]
    tasks: list[Task]
    summary: WorkflowSummary | None = None
    expanded: bool = False


class CustomSummary(BaseModel):
    """Custom summary for a workflow."""

    title: str
    icon: IconName | None = None


class DurationSummary(BaseModel):
    """Summary providing total workflow duration."""

    duration: int
    """The duration of the workflow in seconds"""


WorkflowSummary = CustomSummary | DurationSummary
"""Summary variants available for workflows."""

### TASK TYPES


class BaseTask(BaseModel):
    """Base fields common to all workflow tasks."""

    status_indicator: Literal["none", "loading", "complete"] = "none"
    """Only used when rendering the task as part of a workflow. Indicates the status of the task."""


class CustomTask(BaseTask):
    """Workflow task displaying custom content."""

    type: Literal["custom"] = "custom"
    title: str | None = None
    icon: IconName | None = None
    content: str | None = None


class SearchTask(BaseTask):
    """Workflow task representing a web search."""

    type: Literal["web_search"] = "web_search"
    title: str | None = None
    title_query: str | None = None
    queries: list[str] = Field(default_factory=list)
    sources: list[URLSource] = Field(default_factory=list)


class ThoughtTask(BaseTask):
    """Workflow task capturing assistant reasoning."""

    type: Literal["thought"] = "thought"
    title: str | None = None
    content: str


class FileTask(BaseTask):
    """Workflow task referencing file sources."""

    type: Literal["file"] = "file"
    title: str | None = None
    sources: list[FileSource] = Field(default_factory=list)


class ImageTask(BaseTask):
    """Workflow task rendering image content."""

    type: Literal["image"] = "image"
    title: str | None = None


Task = Annotated[
    CustomTask | SearchTask | ThoughtTask | FileTask | ImageTask,
    Field(discriminator="type"),
]
"""Union of workflow task variants."""


### SOURCE TYPES


class SourceBase(BaseModel):
    """Base class for sources displayed to users."""

    title: str
    description: str | None = None
    timestamp: str | None = None
    group: str | None = None


class FileSource(SourceBase):
    """Source metadata for file-based references."""

    type: Literal["file"] = "file"
    filename: str


class URLSource(SourceBase):
    """Source metadata for external URLs."""

    type: Literal["url"] = "url"
    url: str
    attribution: str | None = None


class EntitySource(SourceBase):
    """Source metadata for entity references."""

    type: Literal["entity"] = "entity"
    id: str
    icon: IconName | None = None
    label: str | None = None
    """Optional label shown with the icon in the default entity hover header
    when no preview callback is provided.
    """
    inline_label: str | None = None
    """Optional label for the inline annotation view. When not provided, the icon is used instead."""
    interactive: bool = False
    """Per-entity toggle to wire client callbacks and render this entity as interactive."""
    data: dict[str, Any] = Field(default_factory=dict)
    """Additional data for the entity source that is passed to client entity callbacks."""

    preview: Literal["lazy"] | None = Field(
        default=None,
        deprecated=True,
        description="This field is ignored. Please use the entities.onRequestPreview ChatKit.js option instead.",
    )


Source = Annotated[
    URLSource | FileSource | EntitySource,
    Field(discriminator="type"),
]
"""Union of supported source types."""


### MISC TYPES


FeedbackKind = Literal["positive", "negative"]
"""Literal type for feedback sentiment."""
