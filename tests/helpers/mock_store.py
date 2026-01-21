import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from chatkit.store import NotFoundError, Store
from chatkit.types import (
    Attachment,
    Page,
    ThreadItem,
    ThreadMetadata,
)
from tests._types import RequestContext

from .mock_widget import SampleWidget

SCHEMA_VERSION = 5  # Bump every time the schema changes


class ThreadData(BaseModel):
    thread: ThreadMetadata


class ItemData(BaseModel):
    item: ThreadItem


class AttachmentData(BaseModel):
    attachment: Attachment


class SampleWidgetData(BaseModel):
    widget: SampleWidget


class SQLiteStore(Store[RequestContext]):
    def __init__(self, db_path: str | None = None):
        self.db_path = (
            db_path or Path(__file__).parent / f"chatkit_v{SCHEMA_VERSION}.db"
        )
        self._create_tables()

    def _create_connection(self):
        return sqlite3.connect(self.db_path, uri=True)

    def _create_tables(self):
        with self._create_connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
                )"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
                )"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                data TEXT NOT NULL
                )"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS sample_widgets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                data TEXT NOT NULL
                )"""
            )

    async def load_thread(
        self, thread_id: str, context: RequestContext
    ) -> ThreadMetadata:
        with self._create_connection() as conn:
            thread_cursor = conn.execute(
                "SELECT data, created_at FROM threads WHERE id = ? AND user_id = ?",
                (thread_id, context.user_id),
            ).fetchone()
            if thread_cursor is None:
                raise NotFoundError(f"Thread {thread_id} not found")

            return ThreadData.model_validate_json(thread_cursor[0]).thread

    async def save_thread(
        self, thread: ThreadMetadata, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            thread_data = ThreadData(thread=thread)
            conn.execute(
                "DELETE FROM threads WHERE id = ? AND user_id = ?",
                (thread.id, context.user_id),
            )
            conn.execute(
                "INSERT INTO threads (id, user_id, created_at, data) VALUES (?, ?, ?, ?)",
                (
                    thread.id,
                    context.user_id,
                    thread.created_at.isoformat(),
                    thread_data.model_dump_json(),
                ),
            )
            conn.commit()

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadItem]:
        with self._create_connection() as conn:
            created_after: str | None = None
            if after:
                created_of_after_thread = conn.execute(
                    "SELECT created_at FROM items WHERE id = ? AND user_id = ?",
                    (after, context.user_id),
                ).fetchone()
                if created_of_after_thread is None:
                    raise NotFoundError(f"Item {after} not found")
                created_after = created_of_after_thread[0]

            query = """
                SELECT id, data FROM items
                WHERE thread_id = ? AND user_id = ?
            """
            params: list[Any] = [thread_id, context.user_id]
            if created_after:
                query += (
                    " AND created_at > ?" if order == "asc" else " AND created_at < ?"
                )
                params.append(created_after)

            query += f" ORDER BY created_at {order} LIMIT ?"
            params.append(limit + 1)

            items_cursor = conn.execute(query, params)
            items = [
                ItemData.model_validate_json(item[1]).item for item in items_cursor
            ]
            has_more = len(items) > limit
            next_after: str | None = None
            if has_more:
                items = items[:limit]
                next_after = items[-1].id
            return Page[ThreadItem](data=items, has_more=has_more, after=next_after)

    async def save_attachment(
        self, attachment: Attachment, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO files (id, user_id, data) VALUES (?, ?, ?)",
                (
                    attachment.id,
                    context.user_id,
                    AttachmentData(attachment=attachment).model_dump_json(),
                ),
            )
            conn.commit()

    async def load_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> Attachment:
        with self._create_connection() as conn:
            file_cursor = conn.execute(
                "SELECT data FROM files WHERE id = ?",  # TODO: consider checking user_id
                (attachment_id,),
            ).fetchone()
            if file_cursor is None:
                raise NotFoundError(f"File {attachment_id} not found")
            return AttachmentData.model_validate_json(file_cursor[0]).attachment

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: RequestContext,
    ) -> Page[ThreadMetadata]:
        with self._create_connection() as conn:
            created_after: str | None = None
            if after:
                created_of_after_thread = conn.execute(
                    "SELECT created_at FROM threads WHERE id = ? AND user_id = ?",
                    (after, context.user_id),
                ).fetchone()
                if created_of_after_thread is None:
                    raise ValueError(f"Thread {after} not found")
                created_after = created_of_after_thread[0]

            query = """
                SELECT data
                FROM threads
                WHERE user_id = ?
            """
            params: list[Any] = [context.user_id]
            if created_after:
                query += (
                    " AND created_at > ?" if order == "asc" else " AND created_at < ?"
                )
                params.append(created_after)
            query += f" ORDER BY created_at {order} LIMIT ?"
            params.append(limit + 1)
            threads_cursor = conn.execute(query, params).fetchall()
            result = []
            for data in threads_cursor:
                thread = ThreadData.model_validate_json(data[0]).thread
                result.append(thread)
            next_after = None
            has_more = len(result) > limit
            if has_more:
                result = result[:limit]
                next_after = result[-1].id
            return Page[ThreadMetadata](
                data=result, has_more=has_more, after=next_after
            )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "INSERT INTO items (id, thread_id, user_id, created_at, data) VALUES (?, ?, ?, ?, ?)",
                (
                    item.id,
                    thread_id,
                    context.user_id,
                    item.created_at.isoformat(),
                    ItemData(item=item).model_dump_json(),
                ),
            )
            conn.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "UPDATE items SET data = ? WHERE id = ? AND thread_id = ? AND user_id = ?",
                (
                    ItemData(item=item).model_dump_json(),
                    item.id,
                    thread_id,
                    context.user_id,
                ),
            )
            conn.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> ThreadItem:
        with self._create_connection() as conn:
            cursor = conn.execute(
                "SELECT data FROM items WHERE id = ? AND thread_id = ? AND user_id = ?",
                (item_id, thread_id, context.user_id),
            ).fetchone()
            if cursor is None:
                raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
            return ItemData.model_validate_json(cursor[0]).item

    async def delete_thread(self, thread_id: str, context: RequestContext) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "DELETE FROM threads WHERE id = ? AND user_id = ?",
                (thread_id, context.user_id),
            )
            conn.execute(
                "DELETE FROM items WHERE thread_id = ? AND user_id = ?",
                (thread_id, context.user_id),
            )
            conn.commit()

    async def delete_attachment(
        self, attachment_id: str, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "DELETE FROM files WHERE id = ? AND user_id = ?",
                (attachment_id, context.user_id),
            )
            conn.commit()

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: RequestContext
    ) -> None:
        with self._create_connection() as conn:
            conn.execute(
                "DELETE FROM items WHERE id = ? AND thread_id = ? AND user_id = ?",
                (item_id, thread_id, context.user_id),
            )
            conn.commit()

    async def save_sample_widget(
        self,
        widget: SampleWidget,
        context: RequestContext,
    ) -> None:
        with self._create_connection() as conn:
            data = SampleWidgetData(widget=widget).model_dump_json()
            conn.execute(
                "INSERT OR REPLACE INTO sample_widgets (id, user_id, data) VALUES (?, ?, ?)",
                (
                    widget.id,
                    context.user_id,
                    data,
                ),
            )
            conn.commit()

    async def load_sample_widget(
        self, widget_id: str, context: RequestContext
    ) -> SampleWidget:
        with self._create_connection() as conn:
            cursor = conn.execute(
                "SELECT data FROM sample_widgets WHERE id = ? AND user_id = ?",
                (widget_id, context.user_id),
            ).fetchone()
            if cursor is None:
                raise NotFoundError(f"SampleWidget {widget_id} not found.")
            return SampleWidgetData.model_validate_json(cursor[0]).widget
