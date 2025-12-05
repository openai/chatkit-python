# Entities

Entities are structured pieces of information your system can recognize during a conversation, such as names, dates, IDs, or product-specific objects.

They represent meaningful objects in your app’s domain. For example:

- In a notes app, entities might be documents.
- In a news site, they might be articles.
- In an online store, they might be products.

When referenced, entities can link messages to real data and power richer actions and previews.

## Entity sources for assistant messages

Entities can be used as cited sources in assistant responses.

**References:**

- The [EntitySource](../../api/chatkit/types/#chatkit.types.EntitySource) Pydantic model definition
- [Add annotations in assistant messages](../guides/add-annotations.md#annotating-with-custom-entities).

## Entity tags as @-mentions in user messages

Users can tag your entities in the composer using @-mentions.

**References**:

- The [Entity](https://openai.github.io/chatkit-js/api/openai/chatkit-react/type-aliases/entity/) TypeScript type definition
- The [UserMessageTagContent](../../api/chatkit/types/#chatkit.types.UserMessageTagContent) Pydantic model definition
- [Accept rich user input](../guides/accept-rich-user-input.md#-mentions-tag-entities-in-user-messages).
