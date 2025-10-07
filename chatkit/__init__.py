"""
ChatKit Python SDK.

ChatKit is a flexible backend SDK for building realtime chat experiences
with OpenAI integration, rich widgets, and comprehensive i18n/RTL support.
"""

from .actions import Action, ActionConfig
from .agents import AgentContext, ThreadItemConverter, stream_agent_response
from .errors import CustomStreamError, ErrorCode, StreamError
from .server import ChatKitServer
from .store import AttachmentStore, NotFoundError, Store
from .types import (
    AssistantMessageItem,
    Attachment,
    ClientToolCallItem,
    EndOfTurnItem,
    HiddenContextItem,
    Page,
    Task,
    TaskItem,
    Thread,
    ThreadItem,
    ThreadMetadata,
    UserMessageInput,
    UserMessageItem,
    WidgetItem,
    Workflow,
    WorkflowItem,
)
from .version import __version__
from .widgets import (
    Badge,
    Box,
    Button,
    Caption,
    Card,
    Chart,
    Checkbox,
    Col,
    DatePicker,
    Divider,
    Form,
    Icon,
    Image,
    Input,
    Label,
    ListView,
    ListViewItem,
    Markdown,
    RadioGroup,
    Row,
    Select,
    Spacer,
    Text,
    Textarea,
    Title,
    Transition,
    WidgetComponent,
    WidgetRoot,
)

# i18n and RTL support
from .i18n import (
    auto_detect_and_set_direction,
    calculate_rtl_ratio,
    contains_arabic_characters,
    contains_hebrew_characters,
    contains_rtl_characters,
    detect_text_direction,
    get_language_direction,
    guess_language_from_text,
    is_mixed_direction_text,
    is_rtl_language,
)
from .bidi import (
    TextSegment,
    clean_bidi_markers,
    fix_arabic_numbers_in_text,
    normalize_mixed_text,
    split_mixed_direction_text,
    wrap_with_direction_markers,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "ChatKitServer",
    "Store",
    "AttachmentStore",
    "NotFoundError",
    # Agents
    "AgentContext",
    "ThreadItemConverter",
    "stream_agent_response",
    # Actions
    "Action",
    "ActionConfig",
    # Errors
    "StreamError",
    "CustomStreamError",
    "ErrorCode",
    # Types
    "Thread",
    "ThreadMetadata",
    "ThreadItem",
    "Page",
    "UserMessageInput",
    "UserMessageItem",
    "AssistantMessageItem",
    "ClientToolCallItem",
    "EndOfTurnItem",
    "HiddenContextItem",
    "WidgetItem",
    "TaskItem",
    "Task",
    "WorkflowItem",
    "Workflow",
    "Attachment",
    # Widgets
    "WidgetRoot",
    "WidgetComponent",
    "Card",
    "ListView",
    "ListViewItem",
    "Text",
    "Title",
    "Caption",
    "Markdown",
    "Button",
    "Input",
    "Textarea",
    "Label",
    "Select",
    "Checkbox",
    "RadioGroup",
    "DatePicker",
    "Box",
    "Row",
    "Col",
    "Form",
    "Divider",
    "Icon",
    "Image",
    "Badge",
    "Spacer",
    "Chart",
    "Transition",
    # i18n
    "is_rtl_language",
    "get_language_direction",
    "contains_rtl_characters",
    "contains_arabic_characters",
    "contains_hebrew_characters",
    "calculate_rtl_ratio",
    "detect_text_direction",
    "guess_language_from_text",
    "is_mixed_direction_text",
    "auto_detect_and_set_direction",
    # bidi
    "TextSegment",
    "wrap_with_direction_markers",
    "fix_arabic_numbers_in_text",
    "split_mixed_direction_text",
    "normalize_mixed_text",
    "clean_bidi_markers",
]
