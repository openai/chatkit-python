# Handle feedback

## Enable feedback actions on the client

Collect thumbs up/down feedback so you can flag broken answers, retrain on good ones, or alert humans. Enable the message actions in the client by setting [`threadItemActions.feedback`](https://openai.github.io/chatkit-js/api/openai/chatkit/type-aliases/threaditemactionsoption/); ChatKit.js renders the controls and sends an `items.feedback` request when a user clicks them.

```tsx
const chatkit = useChatKit({
    // ...
    threadItemActions: {
        feedback: true,
    },
})
```

## Implement `add_feedback` on your server

Override the `add_feedback` method on your server to persist the signal anywhere you like.

```python
from chatkit.server import ChatKitServer
from chatkit.types import FeedbackKind

class MyChatKitServer(ChatKitServer[RequestContext]):
    async def add_feedback(
        self,
        thread_id: str,
        item_ids: list[str],
        feedback: FeedbackKind,
        context: RequestContext,
    ) -> None:
        # Example: write to your analytics/QA store
        await record_feedback(
            thread_id=thread_id,
            item_ids=item_ids,
            sentiment=feedback,
            user_id=context.user_id,
        )
```

`item_ids` can include assistant messages, tool calls, or widgets. If you need to ignore certain items (for example, hidden system prompts), filter them here before recording.
