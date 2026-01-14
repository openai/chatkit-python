import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import pytest
from helpers.mock_store import SQLiteStore
from pydantic import AnyUrl

from chatkit.store import NotFoundError, Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    FileAttachment,
    ImageAttachment,
    InferenceOptions,
    ThreadItem,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
    WidgetItem,
)
from chatkit.widgets import Card, Col, Text
from tests._types import RequestContext


def make_thread(thread_id="test_thread", created_at=None):
    if created_at is None:
        created_at = datetime.now()
    return ThreadMetadata(
        id=thread_id,
        title="Test Thread",
        created_at=created_at,
        metadata={"test": "test"},
    )


def make_thread_items() -> list[ThreadItem]:
    now = datetime.now()
    user_msg = UserMessageItem(
        id="msg_100000",
        content=[UserMessageTextContent(text="Hello!")],
        attachments=[
            FileAttachment(
                id="file_1",
                type="file",
                mime_type="text/plain",
                name="test.txt",
                metadata={"source": "test"},
            )
        ],
        inference_options=InferenceOptions(),
        thread_id="test_thread",
        created_at=now,
    )
    assistant_msg = AssistantMessageItem(
        id="msg_000001",
        content=[AssistantMessageContent(text="Hi there!")],
        thread_id="test_thread",
        created_at=now + timedelta(seconds=1),
    )
    widget = WidgetItem(
        id="widget_1",
        type="widget",
        thread_id="test_thread",
        created_at=now + timedelta(seconds=2),
        widget=Card(
            children=[
                Col(
                    padding={"x": 4, "y": 3},
                    border={"bottom": 1},
                    children=[
                        Text(
                            value="Title",
                            weight="medium",
                            size="sm",
                            color="secondary",
                        ),
                        Text(
                            value="test",
                        ),
                    ],
                ),
            ]
        ),
    )

    return [user_msg, assistant_msg, widget]


DEFAULT_CONTEXT = RequestContext(user_id="test_user")
ALTERNATIVE_CONTEXT = RequestContext(user_id="alternative_user")


class TestStore(ABC):
    store: Store

    @abstractmethod
    def setup_method(self, method):
        pass

    @abstractmethod
    def teardown_method(self, method):
        pass

    @pytest.mark.asyncio
    async def test_save_and_load_thread_metadata(self):
        thread = make_thread()
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        loaded_meta = await self.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert loaded_meta.id == thread.id
        assert loaded_meta.title == thread.title
        assert loaded_meta.metadata == thread.metadata

    @pytest.mark.asyncio
    async def test_save_and_load_thread_metadata_null_title(self):
        thread = ThreadMetadata(
            id="test_thread",
            title=None,
            created_at=datetime.now(),
            metadata={"test": "test"},
        )
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        loaded_meta = await self.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert loaded_meta.id == thread.id
        assert loaded_meta.title is None
        assert loaded_meta.metadata == thread.metadata

    @pytest.mark.asyncio
    async def test_update_thread_metadata(self):
        thread = make_thread()
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        thread.title = "Updated Title"
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        loaded_meta = await self.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert loaded_meta.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_save_and_load_thread_items(self):
        thread = make_thread()
        items = make_thread_items()
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        for item in items:
            await self.store.add_thread_item(thread.id, item, DEFAULT_CONTEXT)
        loaded_items = (
            await self.store.load_thread_items(
                thread.id, None, 10, "asc", DEFAULT_CONTEXT
            )
        ).data
        assert loaded_items == items

    @pytest.mark.asyncio
    async def test_overwrite_thread_metadata(self):
        thread = make_thread()
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        thread.title = "Updated Title"
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        loaded_meta = await self.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert loaded_meta.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_save_and_load_file(self):
        file = FileAttachment(
            id="file_1",
            type="file",
            mime_type="text/plain",
            name="test.txt",
        )
        await self.store.save_attachment(file, DEFAULT_CONTEXT)
        loaded = await self.store.load_attachment(file.id, DEFAULT_CONTEXT)
        assert loaded == file

    @pytest.mark.asyncio
    async def test_save_and_load_image(self):
        image = ImageAttachment(
            id="image_1",
            type="image",
            mime_type="image/png",
            name="test.png",
            preview_url=AnyUrl("https://example.com/test.png"),
            metadata={"source": "test"},
        )
        await self.store.save_attachment(image, DEFAULT_CONTEXT)
        loaded = await self.store.load_attachment(image.id, DEFAULT_CONTEXT)
        assert loaded == image

    @pytest.mark.asyncio
    async def test_load_threads(self):
        now = datetime.now()
        thread1 = make_thread(thread_id="thread1", created_at=now)
        thread2 = make_thread(
            thread_id="thread2", created_at=now + timedelta(seconds=1)
        )
        thread3 = make_thread(
            thread_id="thread3", created_at=now + timedelta(seconds=2)
        )
        await self.store.save_thread(thread1, DEFAULT_CONTEXT)
        await self.store.save_thread(thread2, DEFAULT_CONTEXT)
        await self.store.save_thread(thread3, DEFAULT_CONTEXT)

        page1 = await self.store.load_threads(
            limit=2, after=None, order="asc", context=DEFAULT_CONTEXT
        )
        assert [t.id for t in page1.data] == ["thread1", "thread2"]
        assert page1.has_more is True
        assert page1.after == "thread2"

        page2 = await self.store.load_threads(
            limit=2, after=page1.data[-1].id, order="asc", context=DEFAULT_CONTEXT
        )
        assert [t.id for t in page2.data] == ["thread3"]
        assert page2.has_more is False
        assert not page2.after

    @pytest.mark.asyncio
    async def test_thread_items_ordering(self):
        thread = make_thread()
        now = datetime.now()
        items = [
            UserMessageItem(
                id="msg1",
                content=[UserMessageTextContent(text="A")],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=now,
            ),
            UserMessageItem(
                id="msg2",
                content=[UserMessageTextContent(text="B")],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=now + timedelta(seconds=1),
            ),
            UserMessageItem(
                id="msg3",
                content=[UserMessageTextContent(text="C")],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=now + timedelta(seconds=2),
            ),
        ]
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        for item in items:
            await self.store.add_thread_item(thread.id, item, DEFAULT_CONTEXT)

        asc = await self.store.load_thread_items(
            thread.id, after=None, limit=3, order="asc", context=DEFAULT_CONTEXT
        )
        desc = await self.store.load_thread_items(
            thread.id, after=None, limit=3, order="desc", context=DEFAULT_CONTEXT
        )
        assert [i.id for i in asc.data] == ["msg1", "msg2", "msg3"]
        assert [i.id for i in desc.data] == ["msg3", "msg2", "msg1"]

    @pytest.mark.asyncio
    async def test_thread_items_offset(self):
        thread = make_thread()
        now = datetime.now()
        items = [
            UserMessageItem(
                id=f"msg{i}",
                content=[UserMessageTextContent(text=str(i))],
                attachments=[],
                inference_options=InferenceOptions(),
                thread_id=thread.id,
                created_at=now + timedelta(seconds=i),
            )
            for i in range(5)
        ]
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        for item in items:
            await self.store.add_thread_item(thread.id, item, DEFAULT_CONTEXT)

        after = await self.store.load_thread_items(
            thread.id, after="msg1", limit=3, order="asc", context=DEFAULT_CONTEXT
        )
        assert [i.id for i in after.data] == ["msg2", "msg3", "msg4"]
        assert after.has_more is False
        assert not after.after

        after_limit = await self.store.load_thread_items(
            thread.id, after=None, limit=2, order="asc", context=DEFAULT_CONTEXT
        )
        assert [i.id for i in after_limit.data] == ["msg0", "msg1"]
        assert after_limit.has_more is True
        assert after_limit.after == "msg1"

    @pytest.mark.asyncio
    async def test_save_and_load_item(self):
        thread = make_thread()
        now = datetime.now()
        assistant_msg = AssistantMessageItem(
            id="msg_000001",
            content=[],
            thread_id=thread.id,
            created_at=now,
        )
        widget = WidgetItem(
            id="widget_1",
            type="widget",
            thread_id=thread.id,
            created_at=now + timedelta(seconds=1),
            widget=Card(children=[Text(value="Test")]),
        )
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        await self.store.add_thread_item(thread.id, assistant_msg, DEFAULT_CONTEXT)
        await self.store.add_thread_item(thread.id, widget, DEFAULT_CONTEXT)

        assistant_msg.content = [
            AssistantMessageContent(text="This is an assistant message.")
        ]
        await self.store.save_item(thread.id, assistant_msg, DEFAULT_CONTEXT)
        loaded_assistant = await self.store.load_item(
            thread.id, assistant_msg.id, DEFAULT_CONTEXT
        )
        assert isinstance(loaded_assistant, AssistantMessageItem)
        assert loaded_assistant.id == assistant_msg.id
        assert loaded_assistant.content[0] == AssistantMessageContent(
            text="This is an assistant message."
        )

        await self.store.save_item(thread.id, widget, DEFAULT_CONTEXT)
        loaded_widget = await self.store.load_item(
            thread.id, widget.id, DEFAULT_CONTEXT
        )
        assert isinstance(loaded_widget, WidgetItem)
        assert loaded_widget.id == widget.id

    @pytest.mark.asyncio
    async def test_load_nonexistent_item(self):
        thread = make_thread()
        await self.store.save_thread(thread, DEFAULT_CONTEXT)
        with pytest.raises(NotFoundError):
            await self.store.load_item(thread.id, "does_not_exist", DEFAULT_CONTEXT)

    @pytest.mark.asyncio
    async def test_thread_isolation_by_user(self):
        # Create a thread for DEFAULT_CONTEXT
        thread = make_thread(thread_id="user1_thread")
        await self.store.save_thread(thread, DEFAULT_CONTEXT)

        # Should be accessible by the same user
        loaded_default = await self.store.load_thread(thread.id, DEFAULT_CONTEXT)
        assert loaded_default.title == thread.title

        # Should not be accessible by another user
        with pytest.raises(NotFoundError):
            await self.store.load_thread(thread.id, ALTERNATIVE_CONTEXT)

    @pytest.mark.asyncio
    async def test_thread_items_isolation_by_user(self):
        thread = make_thread(thread_id="shared_thread")
        await self.store.save_thread(thread, DEFAULT_CONTEXT)

        # Add items for DEFAULT_CONTEXT
        items_default = make_thread_items()
        for item in items_default:
            await self.store.add_thread_item(thread.id, item, DEFAULT_CONTEXT)

        # Should be accessible by the same user
        loaded_items_default = (
            await self.store.load_thread_items(
                thread.id, None, 10, "asc", DEFAULT_CONTEXT
            )
        ).data
        assert loaded_items_default == items_default

        # Should not be accessible by another user (should return empty list)
        loaded_items_alternative = (
            await self.store.load_thread_items(
                thread.id, None, 10, "asc", ALTERNATIVE_CONTEXT
            )
        ).data
        assert loaded_items_alternative == []

        # Try to load a specific item with another user's context (should raise ValueError)
        with pytest.raises(NotFoundError):
            await self.store.load_item(
                thread.id, items_default[0].id, ALTERNATIVE_CONTEXT
            )


class TestSqliteStore(TestStore):
    def setup_method(self, method):
        db_path = f"file:{method.__name__}?mode=memory&cache=shared"
        # Keep the shared in-memory database from being deleted when the last connection is closed
        self.db = sqlite3.connect(db_path, uri=True)
        self.store = SQLiteStore(db_path)

    def teardown_method(self, method):
        self.db.close()

    @pytest.mark.asyncio
    async def test_default_id_generators_use_default_prefixes(self):
        ctx = DEFAULT_CONTEXT
        thread_id = self.store.generate_thread_id(ctx)
        assert thread_id.startswith("thr_")

        thread = make_thread(thread_id=thread_id)
        assert self.store.generate_item_id("message", thread, ctx).startswith("msg_")
        assert self.store.generate_item_id("tool_call", thread, ctx).startswith("tc_")
        assert self.store.generate_item_id("task", thread, ctx).startswith("tsk_")
        assert self.store.generate_item_id("workflow", thread, ctx).startswith("wf_")


class TestSqliteStoreCustomIds(TestStore):
    def setup_method(self, method):
        db_path = f"file:{method.__name__}_custom?mode=memory&cache=shared"
        # Keep the shared in-memory database from being deleted when the last connection is closed
        self.db = sqlite3.connect(db_path, uri=True)

        class CustomSQLiteStore(SQLiteStore):
            def __init__(self, path: str):
                super().__init__(path)
                self.counter = 0

            def generate_thread_id(self, context) -> str:
                self.counter += 1
                return f"thr_custom_{self.counter}"

            def generate_item_id(
                self, item_type: str, thread: ThreadMetadata, context
            ) -> str:
                self.counter += 1
                return f"{item_type}_custom_{self.counter}_{thread.id}"

        self.store = CustomSQLiteStore(db_path)

    def teardown_method(self, method):
        self.db.close()

    @pytest.mark.asyncio
    async def test_overridden_id_generators_are_used(self):
        ctx = DEFAULT_CONTEXT
        thread_id = self.store.generate_thread_id(ctx)
        assert thread_id == "thr_custom_1"

        thread = make_thread(thread_id=thread_id)
        msg_id = self.store.generate_item_id("message", thread, ctx)
        tool_call_id = self.store.generate_item_id("tool_call", thread, ctx)
        task_id = self.store.generate_item_id("task", thread, ctx)

        assert msg_id == "message_custom_2_thr_custom_1"
        assert tool_call_id == "tool_call_custom_3_thr_custom_1"
        assert task_id == "task_custom_4_thr_custom_1"

        thread2 = make_thread(thread_id=self.store.generate_thread_id(ctx))
        assert thread2.id == "thr_custom_5"
        msg_id2 = self.store.generate_item_id("message", thread2, ctx)
        tool_call_id2 = self.store.generate_item_id("tool_call", thread2, ctx)
        task_id2 = self.store.generate_item_id("task", thread2, ctx)

        assert msg_id2 == "message_custom_6_thr_custom_5"
        assert tool_call_id2 == "tool_call_custom_7_thr_custom_5"
        assert task_id2 == "task_custom_8_thr_custom_5"
