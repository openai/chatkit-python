## Manage file and image uploads

Provide an `AttachmentStore` to accept uploads and retrieve bytes or signed URLs. If `attachment_store` is omitted, attachment operations raise an error.

- Enforce access control in every method using the provided `context` so only the right user can upload or fetch bytes.
- Direct upload: return an upload URL and accept `multipart/form-data` with a `file` field.
- Two‑phase upload: register the attachment via `attachments.create`, store the attachment metadata, and return an `upload_url`. The client uploads bytes to that URL in a second step.
- Previews: set `ImageAttachment.preview_url` so the client can render thumbnails; generate expiring URLs on demand if needed.

```python
class AttachmentStore(ABC, Generic[TContext]):
    async def delete_attachment(self, attachment_id: str, context: TContext) -> None: ...
    async def create_attachment(
        self, input: AttachmentCreateParams, context: TContext
    ) -> Attachment: ...
    def generate_attachment_id(self, mime_type: str, context: TContext) -> str: ...
```
