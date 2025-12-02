# Allow @-mentions in user messages

Mentions travel through ChatKit as structured tags so the model can resolve entities instead of guessing from free text. Send `input_tag` parts from the client and translate them into model-readable context on the server.

## Enable as-you-type entity lookup in the composer

To enable entity tagging as @-mentions in the composer, configure [`entities.onTagSearch`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#ontagsearch) as a ChatKit.js option.

It should return a list of [Entity](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entity/) objects that match the query string.


```ts
const chatkit = useChatKit({
  // ...
  entities: {
    onTagSearch: async (query: string) => {
      return [
        {
          id: "article_123",
          title: "The Future of AI",
          group: "Trending",
          icon: "globe",
          data: { type: "article" }
        },
        {
          id: "article_124",
          title: "One weird trick to improve your sleep",
          group: "Trending",
          icon: "globe",
          data: { type: "article" }
        },
      ]
    },
  },
})
```

## Convert tags into model input in your server

Override `ThreadItemConverter.tag_to_message_content` to describe what each tag refers to.

Example converter method that wraps the tagged entity details in custom markup:

```python
from chatkit.agents import ThreadItemConverter
from chatkit.types import UserMessageTagContent
from openai.types.responses import ResponseInputTextParam

class MyThreadItemConverter(ThreadItemConverter):
    async def tag_to_message_content(
        self, tag: UserMessageTagContent
    ) -> ResponseInputTextParam:
        if tag.type == "article":
          # Load or unpack the entity the tag refers to
          summary = await fetch_article_summary(tag.id)
          return ResponseInputTextParam(
              type="input_text",
              text=(
                "<ARTICLE_TAG>\n"
                f"ID: {tag.id}\n"
                f"Title: {tag.text}\n"
                f"Summary: {summary}\n"
                "</ARTICLE_TAG>"
              ),
          )
```


## Pair mentions with retrieval tool calls

When the referenced content is too large to inline, keep the tag lean (id + short summary) and let the model fetch details via a tool. In your system prompt, tell the assistant to call the retrieval tool when it sees an `ARTICLE_TAG`.

Example tool paired with the converter above:

```python
from agents import Agent, StopAtTools, RunContextWrapper, function_tool
from chatkit.agents import AgentContext

@function_tool(description_override="Fetch full article content by id.")
async def fetch_article(ctx: RunContextWrapper[AgentContext], article_id: str):
    article = await load_article_content(article_id)
    return {
        "title": article.title,
        "content": article.body,
        "url": article.url,
    }

assistant = Agent[AgentContext](
    ...,
    tools=[fetch_article],
)
```

In `tag_to_message_content`, include the id the tool expects (for example, `tag.id` or `tag.data["article_id"]`). The model can then decide to call `fetch_article` to pull the full text instead of relying solely on the brief summary in the tag.

## Prompt the model about mentions

Add short system guidance to help the assistant understand the input item that adds details about the @-mention.

For example:

```
- <ARTICLE_TAG>...</ARTICLE_TAG> is a summary of an article the user referenced.
- Use it as trusted context when answering questions about that article.
- Do not restate the summary verbatim; answer the user’s question concisely.
- Call the `fetch_article` tool with the article id from the tag when more
  detail is needed or the user asks for specifics not in the summary.
```

Combined with the converter above, the model receives explicit, disambiguated entity context while users keep a rich mention UI.


## Handle clicks and previews

Clicks and hover previews apply to the tagged entities shown in past user messages. Mark an entity as interactive when you return it from `onTagSearch` so the client knows to wire these callbacks:

```ts
{
  id: "article_123",
  title: "The Future of AI",
  group: "Trending",
  icon: "globe",
  interactive: true, // clickable/previewable
  data: { type: "article" }
}
```

- `entities.onClick` fires when a user clicks a tag in the transcript. Handle navigation or open a detail view. See the [onClick option](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onclick).
- `entities.onRequestPreview` runs when the user hovers or taps a tag that has `interactive: true`. Return a `BasicRoot` widget; you can build one with `WidgetTemplate.build_basic(...)` if you are building the preview widgets server-side. See the [onRequestPreview option](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/entitiesoption/#onrequestpreview).
