# Thread items

Thread items are the individual records that make up a thread. This include user and assistant messages, widgets, workflows, and internal markers that guide processing. ChatKit orders and paginates them through your store implementation.

They drive two core experiences:

- **Model input**: Your server's [`respond`](../../api/chatkit/server/#chatkit.server.ChatKitServer.respond) logic will read items to build model input so the model sees the full conversation during an active turn and when resuming past threads. See [Compose model input](../guides/compose-model-input.md).
- **UI rendering**: ChatKit.js renders items incrementally for the active thread during streaming, and re-renders the persisted items when past threads are loaded.

## User messages

[`UserMessageItem`](../../api/chatkit/types/#chatkit.types.UserMessageItem)s represent end-user input. A user message can include the entered text, optional `quoted_text` for reply-style UI, and attachment metadata. User text is plain (no Markdown rendering) but can include @-mentions/tags; see [Allow @-mentions in user messages](../guides/add-features/allow-mentions.md).

## Assistant messages

[`AssistantMessageItem`](../../api/chatkit/types/#chatkit.types.AssistantMessageItem)s represent assistant responses. Content can include text, tool call outputs, widgets, and annotations. Text is Markdown-rendered and can carry inline annotations; see [Add annotations in assistant messages](../guides/add-features/add-annotations.md).

### Markdown support

Markdown in assistant messages supports:

- GitHub-flavored Markdown: Lists, headings, code fences, inline code, blockquotes, links—all with streaming-friendly layout.
- Lists: Ordered/unordered lists stay stable while streaming (Safari-safe markers, no reflow glitches).
- Line breaks: Single newlines render as `<br>` when `breakNewLines` is enabled.
- Code blocks: Syntax-highlighted, copyable, and streamed smoothly; copy buttons are always present.
- Math: LaTeX via remark/rehype math plugins for inline and block equations.
- Tables: Automatic sizing with horizontal scroll for wide outputs.
- Inline annotations: Markdown directives spawn interactive annotations wired into ChatKit handlers.

## Hidden context items

Hidden context items serve as model input but are not rendered in the chat UI. Use them to pass non-visible signals (for example, widget actions or system context) so the model can respond to what the user did, not just what they typed.

- [`HiddenContextItem`](../../api/chatkit/types/#chatkit.types.HiddenContextItem): Your integration’s hidden context; you control the schema and how it is converted for the model.
- [`SDKHiddenContextItem`](../../api/chatkit/types/#chatkit.types.SDKHiddenContextItem): Hidden context inserted by the ChatKit Python SDK for its own operations; you normally leave it alone unless you override conversion behavior.


## ThreadItemConverter

[`ThreadItemConverter`](../../api/chatkit/agents/#chatkit.agents.ThreadItemConverter) maps stored thread items into model-ready input items. Defaults cover messages, widgets, workflows, and tasks; override it to handle attachments, tags, or hidden context in the format your model expects. Combine converter tweaks with prompting so the model sees a coherent view of rich items (for example, summarizing widgets or tasks into text the model can consume).

## Thread item actions

Thread item actions are quick action buttons attached to an assistant turn that let users act on the output, such as retrying, copying, or submitting feedback.

They can be configured client-side with the [threadItemActions option](https://openai.github.io/chatkit-js/api/openai/chatkit-react/type-aliases/threaditemactionsoption/).


## Related guides
- [Persist ChatKit threads and messages](../guides/persist-chatkit-data.md)
- [Compose model inputs](../guides/compose-model-input.md)
- [Add annotations in assistant messages](../guides/add-features/add-annotations.md)
- [Allow @-mentions in user messages](../guides/add-features/allow-mentions.md)
- [Handle feedback](../guides/add-features/handle-feedback.md)