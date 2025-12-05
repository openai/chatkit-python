# Create custom forms

Wrap widgets that collect user input in a `Form` to have their values automatically injected into every action triggered inside that form. The form values arrive in the action payload, keyed by each field’s `name`.

- `<Select name="title" />` → `action.payload["title"]`
- `<Select name="todo.title" />` → `action.payload["todo"]["title"]`

```jsx
<Form
  direction="col"
  onSubmitAction={{
    type: "update_todo",
    payload: { id: todo.id },
  }}
>
  <Title value="Edit Todo" />
  <Text value="Title" color="secondary" size="sm" />
  <Text
    value={todo.title}
    editable={{ name: "title", required: true }}
  />
  <Text value="Description" color="secondary" size="sm" />
  <Text
    value={todo.description}
    editable={{ name: "description" }}
  />
  <Button label="Save" submit />
</Form>
```

On the server, read the form values from the action payload. Any action originating from inside the form will include the latest field values.

```python
from collections.abc import AsyncIterator
from chatkit.server import ChatKitServer
from chatkit.types import Action, ThreadMetadata, ThreadStreamEvent, WidgetItem


class MyChatKitServer(ChatKitServer[RequestContext]):
    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: RequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        if action.type == "update_todo":
            todo_id = action.payload["id"]
            # Any action that originates from within the Form will
            # include title and description
            title = action.payload["title"]
            description = action.payload["description"]

            # ...
```

### Validation

`Form` uses basic native form validation; it enforces `required` and `pattern` on configured fields and blocks submission when any field is invalid.

We may add new validation modes with better UX, more expressive validation, and custom error display. Until then, widgets are not a great medium for complex forms with tricky validation. If you need this, a better pattern is to use client-side action handling to trigger a modal, show a custom form there, then pass the result back into ChatKit with `sendCustomAction`.

### Treating `Card` as a `Form`

You can pass `asForm=True` to `Card` and it will behave as a `Form`, running validation and passing collected fields to the Card’s `confirm` action.

### Payload key collisions

If there is a naming collision with some other existing pre-defined key on your payload, the form value will be ignored. This is probably a bug, so we’ll emit an `error` event when we see this.
