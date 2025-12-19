# Stream generated images

Stream generated images to the client while your agent is running, and persist them in a storage-friendly format.

This guide covers:

- Adding an image generation tool to your agent
- Converting streamed base64 images into URLs so your datastore does not store raw base64 strings
- Converting generated image thread items to model input for continued conversation
- Streaming partial images (progressive previews)

## Add an image generation tool to your agent

To let the model generate images, add the Agents SDK image generation tool to your agent's tool list.

```python
from agents import Agent
from agents.tool import ImageGenerationTool


agent = Agent(
    name="designer",
    instructions="Generate images when asked.",
    tools=[ImageGenerationTool(tool_config={"type": "image_generation"})],
)
```

Once enabled, `stream_agent_response` will translate image generation output into ChatKit thread items:

- A `GeneratedImageItem` is added when an image generation call starts.
- It is updated (for partial images) and finalized when the result arrives.

## Avoid storing raw base64 in your datastore

By default, ChatKit stores generated images as a data URL (for example, `data:image/png;base64,...`) by using `ResponseStreamConverter.base64_image_to_url`.

That's convenient for demos, but it can bloat your persisted thread items. In production, you'll usually want to:

- Write the bytes to object storage / a file store
- Persist only a URL (or a signed URL) on the `GeneratedImageItem`

### Override `ResponseStreamConverter.base64_image_to_url`

Subclass `ResponseStreamConverter` and override `base64_image_to_url`. This method is called for both:

- Final images
- Partial images (when `partial_images` streaming is enabled)

```python
import base64

from chatkit.agents import ResponseStreamConverter


class MyResponseStreamConverter(ResponseStreamConverter):
    async def base64_image_to_url(
        self,
        image_id: str,
        base64_image: str,
        partial_image_index: int | None = None,
    ) -> str:
        # `image_id` stays the same for the whole generation call (including partial updates).
        # Use `partial_image_index` to derive distinct blob IDs for each partial image.
        blob_id = (
            image_id
            if partial_image_index is None
            else f"{image_id}-partial-{partial_image_index}"
        )
        # Replace `upload_blob(...)` with your app's storage call (S3, GCS, filesystem, etc).
        # It should return a URL that your client can load later.
        url = upload_blob(
            blob_id,
            base64.b64decode(base64_image),
            "image/png",
        )
        return url
```

### Pass your converter to `stream_agent_response`

Create your converter and pass it into `stream_agent_response`. The returned URL will be what gets persisted on the `GeneratedImageItem`.

```python
from agents import Runner

from chatkit.agents import AgentContext, stream_agent_response


async def respond(...):
    agent_context = AgentContext(
        thread=thread,
        store=self.store,
        request_context=context,
        previous_response_id=thread.previous_response_id,
    )
    result = Runner.run_streamed(agent, input_items, context=agent_context)

    async for event in stream_agent_response(
        agent_context,
        result,
        converter=MyResponseStreamConverter(),
    ):
        yield event
```

## Convert generated image thread items to model input

On later turns, you'll often feed prior thread items (including generated images) back into the model as context.

By default, `ThreadItemConverter.generated_image_to_input` sends the generated image back to the model as:

- A short text preface
- An `input_image` content part with `image_url=item.image.url`

If `item.image.url` is not publicly reachable by the model runtime (for example, it's a private intranet URL, or a localhost URL, or requires cookies), image understanding and image-to-image flows may fail.

Two common fixes:

- Convert the stored image back into a base64 `data:` URL when building model input
- Generate a temporary public (signed) URL for the duration of the run

### Override `ThreadItemConverter.generated_image_to_input`

Override `generated_image_to_input` and replace `image_url` with something the image API can fetch.

```python
import base64

from openai.types.responses import ResponseInputImageParam, ResponseInputTextParam
from openai.types.responses.response_input_item_param import Message

from chatkit.agents import ThreadItemConverter
from chatkit.types import GeneratedImageItem


class MyThreadItemConverter(ThreadItemConverter):
    async def generated_image_to_input(self, item: GeneratedImageItem):
        if not item.image:
            return None

        # Option A: rehydrate to a data URL (works when you can fetch bytes yourself).
        # Replace `download_blob(...)` with your app's storage call to fetch the image bytes.
        image_bytes = download_blob(item.image.id)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{b64}"

        # Option B: generate a temporary public URL instead:
        # image_url = create_signed_url(item.image.id, expires_in_seconds=60)

        return Message(
            type="message",
            role="user",
            content=[
                ResponseInputTextParam(
                    type="input_text",
                    text="The following image was generated by the agent.",
                ),
                ResponseInputImageParam(
                    type="input_image",
                    detail="auto",
                    image_url=image_url,
                ),
            ],
        )
```

When building your model input, use your custom converter instead of `simple_to_agent_input`:

```python
input_items = await MyThreadItemConverter().to_agent_input(items)
```

## Stream partial images (progressive previews)

You can stream partial images so users see progressive previews as the image is being generated.

### Enable partial images in the tool config

Set `partial_images` in the tool config:

```python
from agents.tool import ImageGenerationTool

image_tool = ImageGenerationTool(
    tool_config={"type": "image_generation", "partial_images": 3},
)
```

### Show progress for partial images

Pass the same `partial_images` value to `ResponseStreamConverter` (or your subclass). ChatKit uses it to compute a `progress` value (between 0 and 1) for each partial image update.

```python
async for event in stream_agent_response(
    agent_context,
    result,
    converter=MyResponseStreamConverter(partial_images=3),
):
    yield event
```

During the run, ChatKit will emit:

- `ThreadItemAddedEvent` for the initial `GeneratedImageItem`
- `ThreadItemUpdatedEvent` with `GeneratedImageUpdated(image=..., progress=...)` for each partial image
- `ThreadItemDoneEvent` when the final image arrives
