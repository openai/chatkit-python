# Persist ChatKit threads and messages

Implement the `Store` interface to control how threads, messages, tool calls, and widgets are stored. Prefer serializing thread items as JSON so schema changes in future releases do not break your storage.

## Implement a Store

Example `Store` backed by Postgres and `psycopg`:

```python
class MyPostgresStore(Store[RequestContext]):
    """Chat data store backed by Postgres."""

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[psycopg.Connection]:
        # Uses blocking psycopg for simplicity.
        # In production async servers, consider an async driver or connection pool.
        with psycopg.connect(self._conninfo) as conn:
            yield conn

    def _init_schema(self) -> None:
        with self._connection() as conn, conn.cursor() as cur:
            # Threads are typically queried by (user_id, created_at),
            # so you may want to add an index on those columns in production.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data JSONB NOT NULL
                );
                """
            )

            # Items are typically streamed by (thread_id, created_at) and
            # sometimes filtered by user_id, so add indexes accordingly in production.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL
                        REFERENCES threads (id)
                        ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    data JSONB NOT NULL
                );
                """
            )

            conn.commit()

    async def load_thread(
        self, thread_id: str, context: RequestContext
    ) -> ThreadMetadata:
        with self._connection() as conn, conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(
                "SELECT data FROM threads WHERE id = %s AND user_id = %s",
                (thread_id, context.user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise NotFoundError(f"Thread {thread_id} not found")

            return ThreadMetadata.model_validate(row[0])

    async def save_thread(
        self, thread: ThreadMetadata, context: RequestContext
    ) -> None:
        payload = thread.model_dump(mode="json")

        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO threads (id, user_id, created_at, data)
                VALUES (%s, %s, %s, %s)
                """,
                (thread.id, context.user_id, thread.created_at, payload),
            )
            conn.commit()

    # Remaining Store methods follow the same pattern
```

See the [`Store` interface](../../api/chatkit/store/#chatkit.store.Store) for the full list of required methods.

### Customize ID generation

If you need custom thread or item IDs you can override the store's ID generation methods `generate_thread_id` and `generate_item_id`.

This is useful when integrating with an external ID system, enforcing a specific ID format, or requiring deterministic or cross-service–unique IDs.

For most applications, the default implementations are sufficient.

### Store thread metadata

`ThreadMetadata` can hold arbitrary, non-UI data needed for your application such as the last `previous_response_id` or customer identifiers.

```python
previous_response_id = thread.metadata.get("previous_response_id")

result = Runner.run_streamed(
    agent,
    input=...,
    previous_response_id=previous_response_id,
)

thread.metadata["previous_response_id"] = result.response_id
```

## Next

[Compose model input](compose-model-input.md)