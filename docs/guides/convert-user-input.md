# Convert user input to model input

ChatKit delivers structured thread items (messages, tools, attachments). Before running inference, convert those items into the model's expected input format.

## Load recent thread items

Make the agent aware of recent context before converting input. Load recent thread items and pass them along with the new message so the model sees the conversation state.

```python
# Inside ChatKitServer.respond(...)
items_page = await self.store.load_thread_items(
    thread.id,
    after=None,
    limit=20,
    order="desc",
    context=context,
)
items = list(reversed(items_page.data))
```

## Use default conversion helpers

Start with the defaults: `simple_to_agent_input` converts a `UserMessageItem` into Agents SDK inputs, and `ThreadItemConverter` lets you override specific conversions when you need more control. Combine the converted user input with the `items` you loaded above to send the model both the latest message and recent thread context.

```python
from agents import Agent, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response


async def respond(
    self,
    thread: ThreadMetadata,
    input: UserMessageItem | None,
    context: Any,
) -> AsyncIterator[ThreadStreamEvent]:
    # Assume `items` was loaded as shown in the previous section.

    input_items = await simple_to_agent_input(items)
    agent_context = AgentContext(thread=thread, store=self.store, request_context=context)
    result = Runner.run_streamed(
        assistant_agent,
        input_items,
        context=agent_context,
    )
```

See [Stream thread events](stream-thread-events.md) for how to stream the resulting events back to the client.

## Customize a ThreadItemConverter

Extend `ThreadItemConverter` when the defaults do not match your agent instructions (e.g. your prompt expects special tags around hidden context or tasks) or when you persist items the simple converter does not cover, such as @-mentions (entity tagging) or attachments. The example below wraps hidden context in a dedicated system message so the model treats it as internal-only guidance.

```python
class MyConverter(ThreadItemConverter):
    async def hidden_context_to_input(
        self, item: HiddenContextItem
    ) -> Message:
        text = (
            "DO NOT SHOW TO USER. Internal context for the assistant:\n"
            f"<context>\n{item.content}\n</context>"
        )
        return Message(
            type="message",
            role="system",
            content=[
                ResponseInputTextParam(
                    type="input_text",
                    text=text,
                )
            ],
        )
```

You can also override methods like `attachment_to_message_content` or `tag_to_message_content` to translate @-mentions or attachments into model-readable text.

## Interpret inference options

When you have specified composer options for tools or models in ChatKit.js, user-selected model or tool settings arrive as `input.inference_options`. Pass them through to your model runner—or even switch which agent you invoke—so the experience follows the user's choices.

```python
if input and input.inference_options:
    model = input.inference_options.model
    tool_choice = input.inference_options.tool_choice
    # forward these into your inference call
```

## Next

[Run inference](run-inference.md)