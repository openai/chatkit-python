import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrail,
    InputGuardrailResult,
    InputGuardrailTripwireTriggered,
    OutputGuardrail,
    OutputGuardrailResult,
    OutputGuardrailTripwireTriggered,
    RawResponsesStreamEvent,
    RunContextWrapper,
    RunItemStreamEvent,
    Runner,
    RunResultStreaming,
    StreamEvent,
    ToolCallItem,
)
from agents._run_impl import QueueCompleteSentinel
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFileSearchToolCall,
    ResponseInputContentParam,
    ResponseInputTextParam,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseReasoningItem,
)
from openai.types.responses.response_content_part_added_event import (
    ResponseContentPartAddedEvent,
)
from openai.types.responses.response_file_search_tool_call import Result
from openai.types.responses.response_input_item_param import Message
from openai.types.responses.response_output_text import (
    AnnotationContainerFileCitation as ResponsesAnnotationContainerFileCitation,
)
from openai.types.responses.response_output_text import (
    AnnotationFileCitation as ResponsesAnnotationFileCitation,
)
from openai.types.responses.response_output_text import (
    AnnotationFilePath as ResponsesAnnotationFilePath,
)
from openai.types.responses.response_output_text import (
    AnnotationURLCitation as ResponsesAnnotationURLCitation,
)
from openai.types.responses.response_output_text import (
    ResponseOutputText,
)
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
from openai.types.responses.response_text_done_event import ResponseTextDoneEvent

from chatkit.agents import (
    AgentContext,
    ResponseStreamConverter,
    ThreadItemConverter,
    accumulate_text,
    simple_to_agent_input,
    stream_agent_response,
)
from chatkit.types import (
    Annotation,
    AssistantMessageContent,
    AssistantMessageContentPartAdded,
    AssistantMessageContentPartAnnotationAdded,
    AssistantMessageContentPartDone,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    Attachment,
    ClientToolCallItem,
    CustomSummary,
    CustomTask,
    DurationSummary,
    FileSource,
    GeneratedImage,
    GeneratedImageItem,
    GeneratedImageUpdated,
    HiddenContextItem,
    InferenceOptions,
    Page,
    TaskItem,
    ThoughtTask,
    Thread,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdatedEvent,
    ThreadStreamEvent,
    URLSource,
    UserMessageItem,
    UserMessageTagContent,
    UserMessageTextContent,
    WidgetItem,
    Workflow,
    WorkflowItem,
    WorkflowTaskAdded,
    WorkflowTaskUpdated,
)
from chatkit.widgets import Card, Text

thread = Thread(id="123", title="Test", created_at=datetime.now(), items=Page())

mock_store = Mock()
mock_store.generate_item_id = lambda item_type, thread, context: f"{item_type}_id"
mock_store.load_thread_items = AsyncMock(return_value=Page())
mock_store.add_thread_item = AsyncMock()


class RunResult(RunResultStreaming):
    def add_event(self, event: StreamEvent):
        self._event_queue.put_nowait(event)

    def done(self):
        self.is_complete = True
        self._event_queue.put_nowait(QueueCompleteSentinel())

    def throw_input_guardrails(self):
        self._stored_exception = InputGuardrailTripwireTriggered(
            InputGuardrailResult(
                guardrail=Mock(spec=InputGuardrail),
                output=GuardrailFunctionOutput(
                    output_info=None,
                    tripwire_triggered=True,
                ),
            )
        )
        self.is_complete = True
        self._event_queue.put_nowait(QueueCompleteSentinel())

    def throw_output_guardrails(self):
        self._stored_exception = OutputGuardrailTripwireTriggered(
            OutputGuardrailResult(
                guardrail=Mock(spec=OutputGuardrail),
                output=GuardrailFunctionOutput(
                    output_info=None,
                    tripwire_triggered=True,
                ),
                agent=Mock(spec=Agent),
                agent_output=None,
            )
        )
        self.is_complete = True
        self._event_queue.put_nowait(QueueCompleteSentinel())


def make_result() -> RunResult:
    return RunResult(
        context_wrapper=Mock(spec=RunContextWrapper),
        input=[],
        tool_input_guardrail_results=[],
        tool_output_guardrail_results=[],
        new_items=[],
        raw_responses=[],
        final_output=None,
        current_agent=Agent(name="test"),
        current_turn=0,
        max_turns=10,
        _current_agent_output_schema=None,
        trace=None,
        is_complete=False,
        _event_queue=asyncio.Queue(),
        _input_guardrail_queue=asyncio.Queue(),
        _output_guardrails_task=None,
        _run_impl_task=None,
        _stored_exception=None,
        output_guardrail_results=[],
        input_guardrail_results=[],
    )


async def all_events(
    events: AsyncIterator[ThreadStreamEvent],
) -> list[ThreadStreamEvent]:
    return [event async for event in events]


async def test_returns_widget_item():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    result.add_event(
        RunItemStreamEvent(name="tool_called", item=Mock(spec=ToolCallItem))
    )
    await context.stream_widget(Card(children=[Text(value="Hello, world!")]))
    result.done()

    events = await all_events(
        stream_agent_response(
            context=context,
            result=result,
        )
    )

    assert len(events) == 1
    assert isinstance(events[0], ThreadItemDoneEvent)
    assert isinstance(events[0].item, WidgetItem)
    assert events[0].item.widget == Card(children=[Text(value="Hello, world!")])


async def test_returns_widget_item_generator():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    result.add_event(
        RunItemStreamEvent(name="tool_called", item=Mock(spec=ToolCallItem))
    )

    def render_widget(i: int) -> Card:
        return Card(children=[Text(id="text", value="Hello, world"[:i])])

    async def widget_generator():
        yield render_widget(0)
        yield render_widget(12)

    await context.stream_widget(widget_generator())
    result.done()

    events = await all_events(
        stream_agent_response(
            context=context,
            result=result,
        )
    )

    assert len(events) == 3
    assert isinstance(events[0], ThreadItemAddedEvent)
    assert isinstance(events[0].item, WidgetItem)
    assert events[0].item.widget == Card(children=[Text(id="text", value="")])

    assert isinstance(events[1], ThreadItemUpdatedEvent)
    assert events[1].update.type == "widget.streaming_text.value_delta"
    assert events[1].update.component_id == "text"
    assert events[1].update.delta == "Hello, world"

    assert isinstance(events[2], ThreadItemDoneEvent)
    assert isinstance(events[2].item, WidgetItem)
    assert events[2].item.widget == Card(
        children=[Text(id="text", value="Hello, world")]
    )


async def test_returns_widget_full_replace_generator():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    result.add_event(
        RunItemStreamEvent(name="tool_called", item=Mock(spec=ToolCallItem))
    )

    async def widget_generator():
        yield Card(children=[Text(id="text", value="Hello!")])
        yield Card(children=[Text(key="other text", value="World!", streaming=False)])

    await context.stream_widget(widget_generator())
    result.done()

    events = await all_events(
        stream_agent_response(
            context=context,
            result=result,
        )
    )

    assert len(events) == 3
    assert isinstance(events[0], ThreadItemAddedEvent)
    assert isinstance(events[0].item, WidgetItem)
    assert events[0].item.widget == Card(children=[Text(id="text", value="Hello!")])

    assert isinstance(events[1], ThreadItemUpdatedEvent)
    assert events[1].update.type == "widget.root.updated"
    assert events[1].update.widget == Card(
        children=[Text(key="other text", value="World!", streaming=False)]
    )

    assert isinstance(events[2], ThreadItemDoneEvent)
    assert isinstance(events[2].item, WidgetItem)
    assert events[2].item.widget == Card(
        children=[Text(key="other text", value="World!", streaming=False)]
    )


async def test_accumulate_text():
    def delta(text: str) -> RawResponsesStreamEvent:
        return RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta=text,
                content_index=0,
                item_id="123",
                logprobs=[],
                output_index=0,
                sequence_number=0,
            ),
        )

    result = Runner.run_streamed(
        Agent("Assistant", instructions="You are a helpful assistant."), "Say hello!"
    )
    result = make_result()
    result.add_event(delta("Hello, "))
    result.add_event(delta("world!"))

    result.done()

    events = [
        event
        async for event in accumulate_text(
            result.stream_events(), Text(key="text", value="", streaming=True)
        )
    ]
    assert events == [
        Text(key="text", value="", streaming=True),
        Text(key="text", value="Hello, ", streaming=True),
        Text(key="text", value="Hello, world!", streaming=True),
        Text(key="text", value="Hello, world!", streaming=False),
    ]


async def test_input_item_converter_quotes_last_user_message():
    items = [
        UserMessageItem(
            id="123",
            content=[UserMessageTextContent(text="Hello!")],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            quoted_text="Hi!",
            created_at=datetime.now(),
        ),
        UserMessageItem(
            id="123",
            content=[UserMessageTextContent(text="I'm well, thank you!")],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            quoted_text="How are you doing?",
            created_at=datetime.now(),
        ),
    ]

    async def throw_exception(
        _: Attachment,
    ) -> ResponseInputContentParam:
        raise Exception("Not implemented")

    input_items = await simple_to_agent_input(items)
    assert len(input_items) == 3
    assert input_items[0] == {
        "content": [
            {
                "text": "Hello!",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert input_items[1] == {
        "content": [
            {
                "text": "I'm well, thank you!",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert input_items[2] == {
        "content": [
            {
                "text": "The user is referring to this in particular: \nHow are you doing?",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }


async def test_input_item_converter_to_input_items_mixed():
    items = [
        UserMessageItem(
            id="123",
            content=[UserMessageTextContent(text="Hello!")],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            quoted_text="Hi!",
            created_at=datetime.now(),
        ),
        UserMessageItem(
            id="123",
            content=[UserMessageTextContent(text="I'm well, thank you!")],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            quoted_text="How are you doing?",
            created_at=datetime.now(),
        ),
        AssistantMessageItem(
            id="123",
            content=[
                AssistantMessageContent(text="How are you doing?"),
                AssistantMessageContent(text="Can't do that"),
            ],
            thread_id=thread.id,
            created_at=datetime.now(),
        ),
        WidgetItem(
            id="wd_123",
            widget=Card(children=[Text(value="Hello, world!")]),
            thread_id=thread.id,
            created_at=datetime.now(),
        ),
    ]

    input_items = await simple_to_agent_input(items)
    assert len(input_items) == 4
    assert input_items[0] == {
        "content": [
            {
                "text": "Hello!",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert input_items[1] == {
        "content": [
            {
                "text": "I'm well, thank you!",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert input_items[2] == {
        "content": [
            {
                "annotations": [],
                "text": "How are you doing?",
                "logprobs": None,
                "type": "output_text",
            },
            {
                "annotations": [],
                "text": "Can't do that",
                "logprobs": None,
                "type": "output_text",
            },
        ],
        "type": "message",
        "role": "assistant",
    }
    assert "type" in input_items[3]
    widget_item = cast(EasyInputMessageParam, input_items[3])
    assert widget_item.get("type") == "message"
    assert widget_item.get("role") == "user"
    text = widget_item.get("content")[0]["text"]  # type: ignore
    assert (
        "The following graphical UI widget (id: wd_123) was displayed to the user"
        in text
    )
    assert "Hello, world!" in text
    assert "created_at" not in text


async def test_input_item_converter_user_input_with_tags():
    class MyThreadItemConverter(ThreadItemConverter):
        async def tag_to_message_content(self, tag):
            return ResponseInputTextParam(
                type="input_text", text=tag.text + " " + tag.data["key"]
            )

    items = [
        UserMessageItem(
            id="123",
            content=[
                UserMessageTagContent(
                    text="Hello!", type="input_tag", id="hello", data={"key": "value"}
                )
            ],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            created_at=datetime.now(),
        )
    ]
    items = await MyThreadItemConverter().to_agent_input(items)

    assert len(items) == 2
    assert items[0] == {
        "content": [
            {
                "text": "@Hello!",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert items[1] == {
        "content": [
            {
                "text": "# User-provided context for @-mentions\n- When referencing resolved entities, use their canonical names **without** '@'.\n"
                + "- The '@' form appears only in user text and should not be echoed.",
                "type": "input_text",
            },
            {
                "text": "Hello! value",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }


async def test_input_item_converter_user_input_with_tags_throws_by_default():
    items = [
        UserMessageItem(
            id="123",
            content=[
                UserMessageTagContent(
                    text="Hello!", type="input_tag", id="hello", data={}
                )
            ],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            created_at=datetime.now(),
        )
    ]

    with pytest.raises(NotImplementedError):
        await simple_to_agent_input(items)


async def test_input_item_converter_generated_image_item():
    items = [
        GeneratedImageItem(
            id="img_item_1",
            thread_id=thread.id,
            created_at=datetime.now(),
            image=GeneratedImage(id="img_1", url="https://example.com/img.png"),
        )
    ]

    input_items = await simple_to_agent_input(items)
    assert len(input_items) == 1

    message = cast(dict, input_items[0])
    assert message.get("type") == "message"
    assert message.get("role") == "user"

    content = cast(list, message.get("content"))
    assert content[0].get("type") == "input_text"
    assert content[0].get("text") == "The following image was generated by the agent."
    assert content[1].get("type") == "input_image"
    assert content[1].get("file_id") is None
    assert content[1].get("image_url") == "https://example.com/img.png"
    assert content[1].get("detail") == "auto"


async def test_input_item_converter_generated_image_item_without_image():
    items = [
        GeneratedImageItem(
            id="img_item_1",
            thread_id=thread.id,
            created_at=datetime.now(),
        )
    ]

    input_items = await simple_to_agent_input(items)
    assert input_items == []


async def test_input_item_converter_for_hidden_context_with_string_content():
    items = [
        HiddenContextItem(
            id="123",
            content="User pressed the red button",
            thread_id=thread.id,
            created_at=datetime.now(),
        )
    ]

    # The default converter works for string content
    items = await simple_to_agent_input(items)
    assert len(items) == 1
    assert items[0] == {
        "content": [
            {
                "text": "Hidden context for the agent (not shown to the user):\n<HiddenContext>\nUser pressed the red button\n</HiddenContext>",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }


async def test_input_item_converter_for_hidden_context_with_non_string_content():
    items = [
        HiddenContextItem(
            id="123",
            content={"harry": "potter", "hermione": "granger"},
            thread_id=thread.id,
            created_at=datetime.now(),
        )
    ]

    # Default converter should throw
    with pytest.raises(NotImplementedError):
        await simple_to_agent_input(items)

    class MyThreadItemConverter(ThreadItemConverter):
        async def hidden_context_to_input(self, item: HiddenContextItem):
            content = ",".join(item.content.keys())
            return Message(
                type="message",
                content=[
                    ResponseInputTextParam(
                        type="input_text", text=f"<HIDDEN>{content}</HIDDEN>"
                    )
                ],
                role="user",
            )

    items = await MyThreadItemConverter().to_agent_input(items)
    assert len(items) == 1
    assert items[0] == {
        "content": [
            {
                "text": "<HIDDEN>harry,hermione</HIDDEN>",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }


async def test_input_item_converter_with_client_tool_call():
    items = [
        UserMessageItem(
            id="123",
            content=[UserMessageTextContent(text="Call a client tool call xyz")],
            attachments=[],
            inference_options=InferenceOptions(),
            thread_id=thread.id,
            quoted_text="Hi!",
            created_at=datetime.now(),
        ),
        TaskItem(
            id="tsk_123",
            created_at=datetime.now(),
            task=CustomTask(title="Called xyx"),
            thread_id=thread.id,
        ),
        ClientToolCallItem(
            id="ctc_123",
            thread_id=thread.id,
            created_at=datetime.now(),
            name="xyz",
            arguments={"foo": "bar"},
            call_id="ctc_123",
        ),
        ClientToolCallItem(
            id="ctc_123_done",
            thread_id=thread.id,
            created_at=datetime.now(),
            name="xyz",
            arguments={"foo": "bar"},
            call_id="ctc_123",
            status="completed",
            output={"success": True},
        ),
    ]

    input_items = await simple_to_agent_input(items)
    assert len(input_items) == 4
    assert input_items[0] == {
        "content": [
            {
                "text": "Call a client tool call xyz",
                "type": "input_text",
            },
        ],
        "role": "user",
        "type": "message",
    }
    assert input_items[1] == {
        "content": [
            {
                "text": "A message was displayed to the user that the following task was performed:\n<Task>\nCalled xyx\n</Task>",
                "type": "input_text",
            },
        ],
        "type": "message",
        "role": "user",
    }
    assert input_items[2] == {
        "type": "function_call",
        "name": "xyz",
        "arguments": json.dumps({"foo": "bar"}),
        "call_id": "ctc_123",
    }
    assert input_items[3] == {
        "type": "function_call_output",
        "call_id": "ctc_123",
        "output": json.dumps({"success": True}),
    }


async def test_stream_agent_response_yields_context_events_without_streaming_events():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    event = ThreadItemAddedEvent(
        item=WidgetItem(
            id="123",
            created_at=datetime.now(),
            thread_id=thread.id,
            widget=Card(children=[Text(id="text", value="Hello, world!")]),
        ),
    )

    await context.stream(event)

    response_streamer = stream_agent_response(context, result)
    event = await response_streamer.__anext__()

    assert event.type == "thread.item.added"

    future = asyncio.ensure_future(response_streamer.__anext__())
    assert future.done() is False

    result.done()

    try:
        await future
        assert False, "expected StopAsyncIteration"
    except StopAsyncIteration:
        pass

    assert future.done() is True


async def test_stream_agent_response_maps_events():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    event = ThreadItemAddedEvent(
        item=WidgetItem(
            id="123",
            created_at=datetime.now(),
            thread_id=thread.id,
            widget=Card(children=[Text(id="text", value="Hello, world!")]),
        ),
    )

    await context.stream(event)
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta="Hello, world!",
                content_index=0,
                item_id="123",
                logprobs=[],
                output_index=0,
                sequence_number=0,
            ),
        )
    )

    response_streamer = stream_agent_response(context, result)
    event1 = await response_streamer.__anext__()
    event2 = await response_streamer.__anext__()

    assert {event1.type, event2.type} == {
        "thread.item.added",
        "thread.item.updated",
    }

    future = asyncio.ensure_future(response_streamer.__anext__())
    assert future.done() is False

    result.done()

    try:
        await future
        assert False, "expected StopAsyncIteration"
    except StopAsyncIteration:
        pass

    assert future.done() is True


@pytest.mark.parametrize(
    "raw_event,expected_event",
    [
        (
            RawResponsesStreamEvent(
                type="raw_response_event",
                data=ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    delta="Hello, world!",
                    content_index=0,
                    item_id="123",
                    logprobs=[],
                    output_index=0,
                    sequence_number=0,
                ),
            ),
            ThreadItemUpdatedEvent(
                item_id="123",
                update=AssistantMessageContentPartTextDelta(
                    content_index=0,
                    delta="Hello, world!",
                ),
            ),
        ),
        (
            RawResponsesStreamEvent(
                type="raw_response_event",
                data=ResponseContentPartAddedEvent(
                    type="response.content_part.added",
                    part=ResponseOutputText(
                        type="output_text",
                        text="New content",
                        annotations=[],
                    ),
                    content_index=1,
                    item_id="123",
                    output_index=0,
                    sequence_number=1,
                ),
            ),
            ThreadItemUpdatedEvent(
                item_id="123",
                update=AssistantMessageContentPartAdded(
                    content_index=1,
                    content=AssistantMessageContent(text="New content", annotations=[]),
                ),
            ),
        ),
        (
            RawResponsesStreamEvent(
                type="raw_response_event",
                data=ResponseTextDoneEvent(
                    type="response.output_text.done",
                    text="Final text",
                    content_index=0,
                    item_id="123",
                    logprobs=[],
                    output_index=0,
                    sequence_number=2,
                ),
            ),
            ThreadItemUpdatedEvent(
                item_id="123",
                update=AssistantMessageContentPartDone(
                    content_index=0,
                    content=AssistantMessageContent(
                        text="Final text",
                        annotations=[],
                    ),
                ),
            ),
        ),
        (
            RawResponsesStreamEvent(
                type="raw_response_event",
                data=Mock(
                    type="response.output_text.annotation.added",
                    annotation=ResponsesAnnotationFileCitation(
                        type="file_citation",
                        file_id="file_123",
                        filename="file.txt",
                        index=5,
                    ),
                    content_index=0,
                    item_id="123",
                    annotation_index=0,
                    output_index=0,
                    sequence_number=3,
                ),
            ),
            ThreadItemUpdatedEvent(
                item_id="123",
                update=AssistantMessageContentPartAnnotationAdded(
                    content_index=0,
                    annotation_index=0,
                    annotation=Annotation(
                        source=FileSource(filename="file.txt", title="file.txt"),
                        index=5,
                    ),
                ),
            ),
        ),
    ],
)
async def test_event_mapping(raw_event, expected_event):
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    result.add_event(raw_event)
    result.done()

    events = await all_events(stream_agent_response(context, result))
    if expected_event:
        assert events == [expected_event]
    else:
        assert events == []


async def test_stream_agent_response_emits_annotation_added_events():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    item_id = "item_123"

    def add_annotation_event(annotation, sequence_number):
        result.add_event(
            RawResponsesStreamEvent(
                type="raw_response_event",
                data=Mock(
                    type="response.output_text.annotation.added",
                    annotation=annotation,
                    content_index=0,
                    item_id=item_id,
                    annotation_index=sequence_number,
                    output_index=0,
                    sequence_number=sequence_number,
                ),
            )
        )

    add_annotation_event(
        ResponsesAnnotationFileCitation(
            type="file_citation",
            file_id="file_invalid",
            filename="",
            index=0,
        ),
        sequence_number=0,
    )
    add_annotation_event(
        ResponsesAnnotationContainerFileCitation(
            type="container_file_citation",
            container_id="container_1",
            file_id="file_123",
            filename="container.txt",
            start_index=0,
            end_index=3,
        ),
        sequence_number=1,
    )
    add_annotation_event(
        ResponsesAnnotationURLCitation(
            type="url_citation",
            url="https://example.com",
            title="Example",
            start_index=1,
            end_index=5,
        ),
        sequence_number=2,
    )
    result.done()

    events = await all_events(stream_agent_response(context, result))
    assert events == [
        ThreadItemUpdatedEvent(
            item_id=item_id,
            update=AssistantMessageContentPartAnnotationAdded(
                content_index=0,
                annotation_index=0,
                annotation=Annotation(
                    source=FileSource(filename="container.txt", title="container.txt"),
                    index=3,
                ),
            ),
        ),
        ThreadItemUpdatedEvent(
            item_id=item_id,
            update=AssistantMessageContentPartAnnotationAdded(
                content_index=0,
                annotation_index=1,
                annotation=Annotation(
                    source=URLSource(
                        url="https://example.com",
                        title="Example",
                    ),
                    index=5,
                ),
            ),
        ),
    ]


@pytest.mark.parametrize("throw_guardrail", ["input", "output"])
async def test_stream_agent_response_yields_item_removed_event(throw_guardrail):
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=ResponseOutputMessage(
                    id="1",
                    content=[
                        ResponseOutputText(
                            annotations=[], type="output_text", text="Hello, world!"
                        )
                    ],
                    role="assistant",
                    status="completed",
                    type="message",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    await context.stream(
        ThreadItemAddedEvent(
            item=AssistantMessageItem(
                id="2",
                content=[AssistantMessageContent(text="Hello, world!")],
                thread_id=thread.id,
                created_at=datetime.now(),
            ),
        )
    )

    await context.stream(
        ThreadItemDoneEvent(
            item=WidgetItem(
                id="3",
                created_at=datetime.now(),
                thread_id=thread.id,
                widget=Card(children=[Text(id="text", value="Hello, world!")]),
            ),
        )
    )

    iterator = stream_agent_response(context, result)

    n = 3
    events = []
    # Grab first 3 events to
    async for event in iterator:
        n -= 1
        events.append(event)
        if n == 0:
            break

    if throw_guardrail == "input":
        result.throw_input_guardrails()
    else:
        result.throw_output_guardrails()

    try:
        async for event in iterator:
            events.append(event)
        assert False, "Guardrail should have been thrown from stream_agent_response"
    except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
        pass
    except Exception as e:
        assert False, f"Unexpected exception: {e}"

    deleted_item_ids = {
        event.item_id for event in events if event.type == "thread.item.removed"
    }
    assert deleted_item_ids == {"1", "2", "3"}


async def test_stream_agent_response_assistant_message_content_types():
    AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=ResponseFileSearchToolCall(
                    id="fs_0",
                    queries=["Hello, world!"],
                    status="completed",
                    type="file_search_call",
                    results=[
                        Result(
                            file_id="f_123",
                            filename="test.txt",
                            text="Hello, world!",
                            score=1.0,
                        ),
                        Result(
                            file_id="f_123",
                            filename="test.txt",
                            text="Hello, friends!",
                            score=0.5,
                        ),
                    ],
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=ResponseOutputMessage(
                    id="1",
                    content=[
                        ResponseOutputText(
                            annotations=[
                                ResponsesAnnotationFileCitation(
                                    type="file_citation",
                                    file_id="f_123",
                                    index=0,
                                    filename="test.txt",
                                ),
                                ResponsesAnnotationContainerFileCitation(
                                    type="container_file_citation",
                                    container_id="container_1",
                                    file_id="f_456",
                                    filename="container.txt",
                                    start_index=0,
                                    end_index=3,
                                ),
                                ResponsesAnnotationURLCitation(
                                    type="url_citation",
                                    url="https://www.google.com",
                                    title="Google",
                                    start_index=0,
                                    end_index=10,
                                ),
                                ResponsesAnnotationFilePath(
                                    type="file_path",
                                    file_id="123",
                                    index=0,
                                ),
                            ],
                            text="Hello, world!",
                            type="output_text",
                        ),
                        ResponseOutputText(
                            annotations=[],
                            text="Can't do that",
                            type="output_text",
                        ),
                    ],
                    role="assistant",
                    status="completed",
                    type="message",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )

    result.done()

    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    events = await all_events(stream_agent_response(context, result))
    assert len(events) == 1
    assert isinstance(events[0], ThreadItemDoneEvent)
    message = events[0].item
    assert isinstance(message, AssistantMessageItem)
    assert message.content == [
        AssistantMessageContent(
            annotations=[
                Annotation(
                    source=FileSource(
                        filename="test.txt",
                        title="test.txt",
                    ),
                    index=0,
                ),
                Annotation(
                    source=FileSource(
                        filename="container.txt",
                        title="container.txt",
                    ),
                    index=3,
                ),
                Annotation(
                    source=URLSource(
                        url="https://www.google.com",
                        title="Google",
                    ),
                    index=10,
                ),
            ],
            text="Hello, world!",
        ),
        AssistantMessageContent(text="Can't do that", annotations=[]),
    ]
    assert message.id == "1"


async def test_stream_agent_response_image_generation_events():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.added",
                item=Mock(type="image_generation_call", id="img_call_1"),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.done",
                item=Mock(
                    type="image_generation_call", id="img_call_1", result="dGVzdA=="
                ),
                output_index=0,
                sequence_number=1,
            ),
        )
    )
    result.done()

    stream = stream_agent_response(context, result)
    event1 = await stream.__anext__()
    assert isinstance(event1, ThreadItemAddedEvent)
    assert isinstance(event1.item, GeneratedImageItem)
    assert event1.item.type == "generated_image"
    assert event1.item.id == "message_id"
    assert event1.item.image is None

    event2 = await stream.__anext__()
    assert isinstance(event2, ThreadItemDoneEvent)
    assert isinstance(event2.item, GeneratedImageItem)
    assert event2.item.id == event1.item.id
    assert event2.item.image == GeneratedImage(
        id="img_call_1", url="data:image/png;base64,dGVzdA=="
    )

    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


async def test_stream_agent_response_image_generation_events_with_custom_converter():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.added",
                item=Mock(type="image_generation_call", id="img_call_1"),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.done",
                item=Mock(
                    type="image_generation_call", id="img_call_1", result="dGVzdA=="
                ),
                output_index=0,
                sequence_number=1,
            ),
        )
    )
    result.done()

    class CustomResponseStreamConverter(ResponseStreamConverter):
        def __init__(self):
            super().__init__()
            self.calls: list[tuple[str, str, int | None]] = []

        async def base64_image_to_url(
            self,
            image_id: str,
            base64_image: str,
            partial_image_index: int | None = None,
        ) -> str:
            self.calls.append((image_id, base64_image, partial_image_index))
            return f"https://example.com/{image_id}"

    converter = CustomResponseStreamConverter()
    stream = stream_agent_response(context, result, converter=converter)
    event1 = await stream.__anext__()
    assert isinstance(event1, ThreadItemAddedEvent)
    assert isinstance(event1.item, GeneratedImageItem)
    assert event1.item.image is None

    event2 = await stream.__anext__()
    assert isinstance(event2, ThreadItemDoneEvent)
    assert isinstance(event2.item, GeneratedImageItem)
    assert converter.calls == [("img_call_1", "dGVzdA==", None)]
    assert event2.item.image == GeneratedImage(
        id="img_call_1", url="https://example.com/img_call_1"
    )
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


async def test_stream_agent_response_image_generation_partial_progress():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.added",
                item=Mock(type="image_generation_call", id="img_call_1"),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.image_generation_call.partial_image",
                partial_image_b64="dGVzdA==",
                partial_image_index=1,
                item_id="img_call_1",
                output_index=0,
                sequence_number=1,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.output_item.done",
                item=Mock(
                    type="image_generation_call", id="img_call_1", result="dGVzdA=="
                ),
                output_index=0,
                sequence_number=2,
            ),
        )
    )
    result.done()

    converter = ResponseStreamConverter(partial_images=3)
    events = await all_events(
        stream_agent_response(context, result, converter=converter)
    )

    assert len(events) == 3
    added_event, partial_event, done_event = events

    assert isinstance(added_event, ThreadItemAddedEvent)
    assert isinstance(added_event.item, GeneratedImageItem)

    assert isinstance(partial_event, ThreadItemUpdatedEvent)
    assert isinstance(partial_event.update, GeneratedImageUpdated)
    assert partial_event.update.progress == pytest.approx(1 / 3)
    assert partial_event.update.image == GeneratedImage(
        id="img_call_1", url="data:image/png;base64,dGVzdA=="
    )

    assert isinstance(done_event, ThreadItemDoneEvent)
    assert isinstance(done_event.item, GeneratedImageItem)
    assert done_event.item.image == GeneratedImage(
        id="img_call_1", url="data:image/png;base64,dGVzdA=="
    )


async def test_workflow_streams_first_thought():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    # first thought
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=ResponseReasoningItem(
                    id="resp_1",
                    summary=[],
                    type="reasoning",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.delta",
                item_id="resp_1",
                summary_index=0,
                delta="Think",
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.delta",
                item_id="resp_1",
                summary_index=0,
                delta="ing 1",
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.done",
                item_id="resp_1",
                summary_index=0,
                text="Thinking 1",
            ),
        )
    )

    # second thought
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.delta",
                item_id="resp_1",
                summary_index=1,
                delta="Think",
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.delta",
                item_id="resp_1",
                summary_index=1,
                delta="ing 2",
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.done",
                item_id="resp_1",
                summary_index=1,
                text="Thinking 2",
            ),
        )
    )

    result.done()
    stream = stream_agent_response(context, result)

    # Workflow added
    event = await anext(stream)
    assert isinstance(event, ThreadItemAddedEvent)
    assert context.workflow_item is not None
    assert context.workflow_item.workflow.type == "reasoning"
    assert len(context.workflow_item.workflow.tasks) == 0
    assert event == ThreadItemAddedEvent(item=context.workflow_item)

    # First thought added
    event = await anext(stream)
    assert context.workflow_item is not None
    assert len(context.workflow_item.workflow.tasks) == 1
    assert isinstance(event, ThreadItemUpdatedEvent)
    assert event == ThreadItemUpdatedEvent(
        item_id=context.workflow_item.id,
        update=WorkflowTaskAdded(
            task=ThoughtTask(content="Think"),
            task_index=0,
        ),
    )

    # First thought delta
    event = await anext(stream)
    assert context.workflow_item is not None
    assert len(context.workflow_item.workflow.tasks) == 1
    assert isinstance(event, ThreadItemUpdatedEvent)
    assert event == ThreadItemUpdatedEvent(
        item_id=context.workflow_item.id,
        update=WorkflowTaskUpdated(
            task=ThoughtTask(content="Thinking 1"),
            task_index=0,
        ),
    )

    # First thought done
    event = await anext(stream)
    assert context.workflow_item is not None
    assert len(context.workflow_item.workflow.tasks) == 1
    assert isinstance(event, ThreadItemUpdatedEvent)
    assert event == ThreadItemUpdatedEvent(
        item_id=context.workflow_item.id,
        update=WorkflowTaskUpdated(
            task=ThoughtTask(content="Thinking 1"),
            task_index=0,
        ),
    )

    # Second thought added (not streamed)
    event = await anext(stream)
    assert context.workflow_item is not None
    assert len(context.workflow_item.workflow.tasks) == 2
    assert isinstance(event, ThreadItemUpdatedEvent)
    assert event == ThreadItemUpdatedEvent(
        item_id=context.workflow_item.id,
        update=WorkflowTaskAdded(
            task=ThoughtTask(content="Thinking 2"),
            task_index=1,
        ),
    )

    try:
        while True:
            await anext(stream)
    except StopAsyncIteration:
        pass


async def test_workflow_ends_on_message():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()

    # first thought
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=ResponseReasoningItem(
                    id="resp_1",
                    summary=[],
                    type="reasoning",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=Mock(
                type="response.reasoning_summary_text.done",
                item_id="resp_1",
                summary_index=0,
                text="Thinking 1",
            ),
        )
    )

    # not reasoning
    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=ResponseOutputMessage(
                    id="m_1",
                    content=[],
                    role="assistant",
                    status="in_progress",
                    type="message",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )

    result.done()
    stream = stream_agent_response(context, result)

    # Workflow added
    event = await anext(stream)
    assert isinstance(event, ThreadItemAddedEvent)
    assert context.workflow_item is not None
    assert context.workflow_item.workflow.type == "reasoning"
    assert len(context.workflow_item.workflow.tasks) == 0
    assert event == ThreadItemAddedEvent(item=context.workflow_item)

    # First thought done
    event = await anext(stream)
    assert context.workflow_item is not None
    assert len(context.workflow_item.workflow.tasks) == 1
    assert isinstance(event, ThreadItemUpdatedEvent)
    assert event == ThreadItemUpdatedEvent(
        item_id=context.workflow_item.id,
        update=WorkflowTaskAdded(
            task=ThoughtTask(content="Thinking 1"),
            task_index=0,
        ),
    )

    # Workflow ended
    event = await anext(stream)
    assert isinstance(event, ThreadItemDoneEvent)
    assert event.item.type == "workflow"
    assert context.workflow_item is None
    # Summary and expanded are handled by the end_workflow method
    assert isinstance(event.item.workflow.summary, DurationSummary)
    assert event.item.workflow.expanded is False

    try:
        while True:
            await anext(stream)
    except StopAsyncIteration:
        pass


async def test_existing_workflow_summary_not_overwritten_on_automatic_end():
    context = AgentContext(
        previous_response_id=None, thread=thread, store=mock_store, request_context=None
    )
    result = make_result()
    context.workflow_item = WorkflowItem(
        id="wf_1",
        created_at=datetime.now(),
        workflow=Workflow(type="custom", tasks=[], summary=CustomSummary(title="Test")),
        thread_id=thread.id,
    )

    result.add_event(
        RawResponsesStreamEvent(
            type="raw_response_event",
            data=ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=ResponseOutputMessage(
                    id="m_1",
                    content=[],
                    role="assistant",
                    status="in_progress",
                    type="message",
                ),
                output_index=0,
                sequence_number=0,
            ),
        )
    )

    result.done()
    stream = stream_agent_response(context, result)

    event = await anext(stream)

    assert isinstance(event, ThreadItemDoneEvent)
    assert context.workflow_item is None
    assert event.item.type == "workflow"
    assert event.item.workflow.summary == CustomSummary(title="Test")

    try:
        while True:
            await anext(stream)
    except StopAsyncIteration:
        pass
