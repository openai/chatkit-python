import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, Literal

from typing_extensions import TypeVar

from .types import (
    Attachment,
    AttachmentCreateParams,
    Page,
    ThreadItem,
    ThreadMetadata,
)

TContext = TypeVar("TContext", default=Any)

StoreItemType = Literal[
    "thread",
    "message",
    "tool_call",
    "task",
    "workflow",
    "attachment",
    "sdk_hidden_context",
]


_ID_PREFIXES: dict[StoreItemType, str] = {
    "thread": "thr",
    "message": "msg",
    "tool_call": "tc",
    "workflow": "wf",
    "task": "tsk",
    "attachment": "atc",
    "sdk_hidden_context": "shcx",
}


def default_generate_id(item_type: StoreItemType) -> str:
    prefix = _ID_PREFIXES[item_type]
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class NotFoundError(Exception):
    pass


class AttachmentStore(ABC, Generic[TContext]):
    @abstractmethod
    async def delete_attachment(self, attachment_id: str, context: TContext) -> None:
        """Delete an attachment by id."""
        pass

    async def create_attachment(
        self, input: AttachmentCreateParams, context: TContext
    ) -> Attachment:
        """Create an attachment record from upload metadata."""
        raise NotImplementedError(
            f"{type(self).__name__} must override create_attachment() to support two-phase file upload"
        )

    def generate_attachment_id(self, mime_type: str, context: TContext) -> str:
        """Return a new identifier for a file. Override this method to customize file ID generation."""

        return default_generate_id("attachment")


class Store(ABC, Generic[TContext]):
    def generate_thread_id(self, context: TContext) -> str:
        """Return a new identifier for a thread. Override this method to customize thread ID generation."""

        return default_generate_id("thread")

    def generate_item_id(
        self, item_type: StoreItemType, thread: ThreadMetadata, context: TContext
    ) -> str:
        """Return a new identifier for a thread item. Override this method to customize item ID generation."""

        return default_generate_id(item_type)

    @abstractmethod
    async def load_thread(self, thread_id: str, context: TContext) -> ThreadMetadata:
        """Load a thread's metadata by id."""
        pass

    @abstractmethod
    async def save_thread(self, thread: ThreadMetadata, context: TContext) -> None:
        """Persist thread metadata (title, status, etc.)."""
        pass

    @abstractmethod
    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: TContext,
    ) -> Page[ThreadItem]:
        """Load a page of thread items with pagination controls."""
        pass

    @abstractmethod
    async def save_attachment(self, attachment: Attachment, context: TContext) -> None:
        """Upsert attachment metadata."""
        pass

    @abstractmethod
    async def load_attachment(
        self, attachment_id: str, context: TContext
    ) -> Attachment:
        """Load attachment metadata by id."""
        pass

    @abstractmethod
    async def delete_attachment(self, attachment_id: str, context: TContext) -> None:
        """Delete attachment metadata by id."""
        pass

    @abstractmethod
    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: TContext,
    ) -> Page[ThreadMetadata]:
        """Load a page of threads with pagination controls."""
        pass

    @abstractmethod
    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: TContext
    ) -> None:
        """Persist a newly created thread item."""
        pass

    @abstractmethod
    async def save_item(
        self, thread_id: str, item: ThreadItem, context: TContext
    ) -> None:
        """Upsert a thread item by id."""
        pass

    @abstractmethod
    async def load_item(
        self, thread_id: str, item_id: str, context: TContext
    ) -> ThreadItem:
        """Load a thread item by id."""
        pass

    @abstractmethod
    async def delete_thread(self, thread_id: str, context: TContext) -> None:
        """Delete a thread and its items."""
        pass

    @abstractmethod
    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: TContext
    ) -> None:
        """Delete a thread item by id."""
        pass
