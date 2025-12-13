# Threads and items

In ChatKit, a **thread** represents a single conversation. It is the unit that ties together everything that happens in that conversation: messages, widgets, actions, system signals, and metadata. A thread is stored as an ordered history of **thread items**, which ChatKit loads, paginates, and renders as needed.

## What is a thread?

A thread is an ordered timeline that contains:

- Conversation history (user and assistant messages)
- Structured content such as widgets and workflows
- Internal signals that guide processing or model behavior
- Metadata like titles or status flags

Threads are persisted by your store implementation and can be updated, continued, or made read-only according to your application’s needs.

## What are thread items?

Thread items are the individual records that make up a thread. Each item represents one meaningful unit in the conversation history, such as:

- A user message
- An assistant response
- A widget rendered by the assistant
- A non-visible signal used only for model input

ChatKit maintains the order of items, streams new ones as they are produced, and paginates them when history is loaded.

## How threads are created and updated

A typical thread lifecycle looks like this:

- **Thread creation**: When a user submits a message and no thread exists yet, ChatKitServer creates one and persists it by calling your store’s `save_thread`.
- **Appending items**: As the server streams a response, ChatKit persists thread items automatically as each item completes. Streaming events directly drive what gets stored.
- **Updating metadata**: During respond, you can freely mutate the thread object (for example, to set or refine the title). ChatKit automatically persists these updates when the response completes. You can also call store.save_thread explicitly if needed.
- **Loading history**: When history is enabled client-side, ChatKit retrieves past threads and their items. Users can continue an existing thread by default.
- **Closing or archiving**: Threads can be marked read-only (for example, by disabling new messages) or deleted entirely if they should no longer be discoverable.


## How thread items are used

Thread items serve two primary purposes in ChatKit:

### Model input

Your server's [`respond`](../api/chatkit/server.md#chatkit.server.ChatKitServer.respond) logic reads thread items to construct input for the model input. This ensures the model sees the full conversational context both during an active response and when a user resumes a past thread. 

See [Respond to a user message](../guides/respond-to-user-message.md) for a full walkthrough.

### UI rendering

On the client, ChatKit.js renders items incrementally as they stream in for the active thread. When a past thread is loaded, the same persisted items are re-rendered to reconstruct the conversation UI.

## Core item types

### User messages

[`UserMessageItem`](../api/chatkit/types.md#chatkit.types.UserMessageItem)s represent end-user input. They may include:

- Plain text entered by the user
- Optional `quoted_text` for reply-style UIs
- Attachment metadata


User text is not Markdown-rendered, but it may contain [@-mentions](../guides/accept-rich-user-input.md#-mentions-tag-entities-in-user-messages) if your integration enables them.


### Assistant messages

[`AssistantMessageItem`](../api/chatkit/types.md#chatkit.types.AssistantMessageItem)s represent assistant output. Their content can include:

- Markdown-rendered text
- Tool call outputs
- Widgets and structured UI elements
- [Inline annotations](../guides/add-annotations.md)

Assistant text supports rich Markdown and is rendered progressively as it streams.

#### Markdown support

Assistant messages support:

- GitHub-flavored Markdown (headings, lists, code blocks, links, blockquotes)
- Stable list rendering during streaming (Safari-safe, no reflow)
- Optional single-newline line breaks
- Syntax-highlighted, copyable code blocks
- LaTeX math (inline and block)
- Tables with automatic sizing and horizontal scrolling
- Inline annotations that create interactive affordances in the UI

### Hidden context items

Hidden context items are included in model input but are not rendered in the chat UI. They allow the model to react to what happened in the interface, not just what the user typed.

Typical use cases include recording widget actions, selection state, or system signals.

- **[`HiddenContextItem`](../api/chatkit/types.md#chatkit.types.HiddenContextItem)**: Integration-defined hidden context. You control its schema and how it is converted for the model.

- **[`SDKHiddenContextItem`](../api/chatkit/types.md#chatkit.types.SDKHiddenContextItem)**: Hidden context inserted by the ChatKit Python SDK for its own internal operations. Most applications do not need to modify this unless overriding conversion behavior.

## Thread item actions

Thread item actions are quick action buttons associated with an assistant turn. They let users act on the output—such as retrying a response, copying content, or submitting feedback.

Actions are configured client-side using the [threadItemActions option](https://openai.github.io/chatkit-js/api/openai/chatkit-react/type-aliases/threaditemactionsoption/).

## Converting items to model input

[`ThreadItemConverter`](../api/chatkit/agents.md#chatkit.agents.ThreadItemConverter) translates stored thread items into model-ready input items. The default converter understands common ChatKit item types such as messages, widgets, workflows, and tasks.

You can override the converter when you need custom behavior. For example:

- Formatting attachments for the model
- Translating tags or mentions into structured input
- Summarizing rich widgets into text the model can consume

Custom conversion is typically paired with prompting so the model receives a coherent representation of the conversation.

## Related guides
- [Respond to a user message](../guides/respond-to-user-message.md)
- [Pass extra app context to your model](../guides/pass-extra-app-context-to-your-model.md)
- [Add annotations in assistant messages](../guides/add-annotations.md)
- [Accept rich user input](../guides/accept-rich-user-input.md#-mentions-tag-entities-in-user-messages)
- [Handle feedback](../guides/handle-feedback.md)
- [Let users browse past threads](../guides/browse-past-threads.md)
