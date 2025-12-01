# Accept attachments

Let users attach files/images by turning on client support, choosing an upload strategy, wiring the upload endpoints, and converting attachments to model inputs.

## Enable attachments in the client

Enable attachments in the composer and configure client-side limits:

- Set `ChatKitOptions.composer.attachments.enabled = true` so the composer accepts file attachments.
- In the same `composer.attachments` block, configure accepted MIME types,per-message maximum attachment count, and per-file size limits: see [docs](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/composeroption/#attachments).

## Configure an upload strategy

Set [`ChatKitOptions.api.uploadStrategy`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/fileuploadstrategy/) to:

- **Direct**: your backend exposes a single upload URL that accepts the bytes and writes attachment metadata to your `Store`. Simpler and faster when you control uploads directly from the app server.
- **Two-phase**: the client makes a ChatKit API request to create an attachment metadata record (which forwards the request to `AttachmentStore`), you return an `upload_url` as part of the created attachment metadata, and the client uploads bytes in a second step. Prefer this when you front object storage with presigned/temporary URLs or want to offload upload bandwidth (e.g. to a third-party blob storage).

Both strategies still require an `AttachmentStore` for delete cleanup. Choose direct for simplicity on the same origin; choose two-phase for cloud storage and larger files.

## Enforce attachment access control

Neither attachment metadata nor file bytes are protected by ChatKit. Use the `context` passed into your `AttachmentStore` methods to authorize every create/read/delete. Only return IDs, bytes, or signed URLs when the caller owns the attachment, and prefer short-lived download URLs. Skipping these checks can leak customer data.

## If you chose direct upload

Add the upload endpoint referenced in `uploadStrategy`. It must:

- accept `multipart/form-data` with a `file` field,
- store the bytes wherever you like,
- create `Attachment` metadata, persist it via `Store.save_attachment`, and
- return the `Attachment` JSON.

Implement `AttachmentStore.delete_attachment` to delete the stored bytes; `ChatKitServer` will then call `Store.delete_attachment` to drop metadata.

Example client configuration:

```js
{
  type: "direct",
  uploadUrl: "/files",
}
```

Example FastAPI direct upload endpoint:

```python
@app.post("/files")
async def upload_file(request: Request):
    form_data = await request.form()
    file = form_data.get("file")

    # Your blob store upload
    attachment = await upload_to_blob_store(file)

    return Response(content=attachment.model_dump_json(), media_type="application/json")
```

## If you chose two-phase upload

Implement `AttachmentStore.create_attachment` to:

- build an `upload_url` that accepts `multipart/form-data` with a `file` field (direct PUTs are currently not supported),
- build the `Attachment` model,
- persist it via `Store.save_attachment`, and
- return it.

Implement `AttachmentStore.delete_attachment` to delete the stored bytes; `ChatKitServer` will call `Store.delete_attachment` afterward.

- The client POSTs the bytes to `upload_url` after it receives the created attachment metadata in the response.

Client configuration:

```js
{
  type: "two_phase",
}
```

Example two-phase store issuing a multipart upload URL:

```python
attachment_store = BlobAttachmentStore()
server = MyChatKitServer(store=data_store, attachment_store=attachment_store)

class BlobAttachmentStore(AttachmentStore[RequestContext]):
    def generate_attachment_id(self, mime_type: str, context: RequestContext) -> str:
        return f"att_{uuid4().hex}"

    async def create_attachment(
        self, input: AttachmentCreateParams, context: RequestContext
    ) -> Attachment:
        att_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = issue_multipart_upload_url(att_id, input.mime_type)  # your blob store
        attachment = Attachment(
            id=att_id,
            mime_type=input.mime_type,
            name=input.name,
            upload_url=upload_url,
        )
        await data_store.save_attachment(attachment, context=context)
        return attachment

    async def delete_attachment(self, attachment_id: str, context: RequestContext) -> None:
        await delete_blob(att_id=attachment_id)  # your blob store
```

## Convert attachments to model input

Attachments arrive on `input_user_message.attachments` in `ChatKitServer.respond`. The default `ThreadItemConverter` does not handle them, so subclass and implement `attachment_to_message_content` to return a `ResponseInputContentParam` before calling `Runner.run_streamed`.

Example using a blob fetch helper:

```python
from chatkit.agents import ThreadItemConverter
from chatkit.types import ImageAttachment
from openai.types.responses import ResponseInputFileParam, ResponseInputImageParam

async def read_bytes(attachment_id: str) -> bytes:
    ...  # fetch from your blob store

def as_data_url(mime: str, content: bytes) -> str:
    return "data:" + mime + ";base64," + base64.b64encode(content).decode("utf-8")

class MyConverter(ThreadItemConverter):
    async def attachment_to_message_content(self, attachment):
        content = await read_bytes(attachment.id)
        if isinstance(attachment, ImageAttachment):
            return ResponseInputImageParam(
                type="input_image",
                detail="auto",
                image_url=as_data_url(attachment.mime_type, content),
            )
        if attachment.mime_type == "application/pdf":
            return ResponseInputFileParam(
                type="input_file",
                file_data=as_data_url(attachment.mime_type, content),
                filename=attachment.name or "unknown",
            )
        # For other text formats, check for API support first before
        # sending as a ResponseInputFileParam.
```

## Show image attachment previews in thread

Set `ImageAttachment.preview_url` to allow the client to render thumbnails.

- If your preview URLs are **permanent/public**, set `preview_url` once when creating the attachment and persist it.
- If your storage uses **expiring URLs**, generate a fresh `preview_url` when returning attachment metadata (for example, in `Store.load_thread_items` and `Store.load_attachment`) rather than persisting a long-lived URL. In this case, returning a short-lived signed URL directly is the simplest approach. Alternatively, you may return a redirect that resolves to a temporary signed URL, as long as the final URL serves image bytes with appropriate CORS headers.
