import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata
from psycopg.rows import tuple_row
from psycopg.types.json import Json
from pydantic import BaseModel

class ThreadData(BaseModel):
    thread: ThreadMetadata

class ItemData(BaseModel):
    item: ThreadItem

class AttachmentData(BaseModel):
    attachment: Attachment

class PostgresStore(Store):
    """Chat data store backed by Render Postgres."""

    def __init__(self) -> None:
        conninfo = os.getenv("DATABASE_URL")
        if not conninfo:
            raise RuntimeError(
                "DATABASE_URL must be set to connect to Render Postgres."
            )
        self._conninfo: str = conninfo
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self._conninfo) as conn:
            yield conn

    def _init_schema(self) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS threads (
                        id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        data JSONB NOT NULL,
                        PRIMARY KEY (id, user_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS items (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        data JSONB NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attachments (
                        id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        data JSONB NOT NULL,
                        PRIMARY KEY (id, user_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS items_thread_user_created_idx
                        ON items (thread_id, user_id, created_at DESC)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS threads_user_created_idx
                        ON threads (user_id, created_at DESC)
                    """
                )
            conn.commit()

    async def load_thread(self, thread_id: str, context: Any) -> ThreadMetadata:
        user_id = context.user_id
        with self._connection() as conn:
            with conn.cursor(row_factory=tuple_row) as cur:
                cur.execute(
                    "SELECT data FROM threads WHERE id = %s AND user_id = %s",
                    (thread_id, user_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise NotFoundError(f"Thread {thread_id} not found")
                return ThreadData.model_validate(row[0]).thread

    async def save_thread(self, thread: ThreadMetadata, context: Any) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO threads (id, user_id, created_at, data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id, user_id)
                    DO UPDATE SET created_at = EXCLUDED.created_at, data = EXCLUDED.data
                    """,
                    (
                        thread.id,
                        thread.user_id,
                        thread.created_at,
                        Json(thread.model_dump()),
                    ),
                )
            conn.commit()
# You can add the rest of the methods (items, attachments, etc.) similarly if you need full coverage.