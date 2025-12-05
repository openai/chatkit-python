# Prepare your app for production

This guide covers the operational work you should do before rolling out a ChatKit‑powered experience in production:

- Set up **localization** so prompts, system messages, and tool output match the user’s locale.
- Configure **monitoring and logging** so you can debug issues and correlate ChatKit traffic with your backend traces.
- Review **security and authentication** for your ChatKit endpoint.
- Register and use **domain keys** to lock ChatKit down to your approved hostnames.

Use it as a checklist alongside your own product’s launch process.

## Localize prompts, UI copy, and tool output

By the time you go live, you should have a clear story for which locales you support and how locale flows from the client into your backend and model prompts.

ChatKit always picks a **single active locale** and:

- Uses the **browser locale by default**.
- Lets you **override the locale on the client** (for example, from your own locale picker) by passing the `locale` option when you initialize ChatKit.

For every request to your ChatKit backend, the client sends an `Accept-Language` header with that single locale value. You can rely on this header to drive your own localization logic on the server.

At a minimum:

- **Decide which locales you support** (for example `["en", "fr", "de"]`) and what the default/fallback is.
- **Localize tool output and error messages** so the assistant’s replies feel consistent with the rest of your product.

For example, you might include locale in your per‑request context:

```python
from dataclasses import dataclass


@dataclass
class RequestContext:
    user_id: str
    locale: str
```

Then, when you build prompts or tool output, read `context.locale` and render language‑appropriate text using your localization system. For example, with `gettext`:

```python
from pathlib import Path
import gettext

from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext


LOCALE_DIR = Path(__file__).with_suffix("").parent / "locales"
_translations: dict[str, gettext.NullTranslations] = {}


def get_translations(locale: str) -> gettext.NullTranslations:
    """Return a gettext translation object for the given locale."""
    if locale not in _translations:
        _translations[locale] = gettext.translation(
            "messages",  # your .po/.mo domain
            localedir=LOCALE_DIR,
            languages=[locale],
            fallback=True,
        )
    return _translations[locale]


@function_tool()
async def load_document(
    ctx: RunContextWrapper[AgentContext],
    document_id: str,
):
    locale = ctx.context.request_context.locale
    _ = get_translations(locale).gettext
    await ctx.context.stream_progress(
        icon="document",
        text=_("Loading document…"),
    )
    doc = await get_document_by_id(document_id)
    if not doc:
        raise ValueError(_("We couldn’t find that document."))
    return doc
```

When you call the model (for example via the OpenAI Responses API), include the user’s locale either directly in the prompt or as part of a system message so the model responds in the right language.

## Monitor logs and errors

You should be able to answer questions like “what went wrong for this user at this time?” and “are ChatKit requests healthy right now?” before you roll out broadly.

### Capture client logs

On the **client side**, subscribe to ChatKit’s log and error events and forward them into your own telemetry system, tagged with:

- User identifier (or stable anonymous id).
- Session or request id.
- The current thread id.

In React, use the `onLog` and `onError` options (mirroring the patterns in the ChatKit JS [Monitor logs](https://openai.github.io/chatkit-js/guides/monitor-logs/) guide):

```tsx
import { ChatKit, useChatKit } from "@openai/chatkit-react";

export function SupportChat({
  clientToken,
  userId,
}: {
  clientToken: string;
  userId: string;
}) {
  const { control } = useChatKit({
    api: { clientToken },
    onLog: ({ name, data }) =>
      sendToTelemetry({
        name,
        // Avoid forwarding raw message text or tool arguments directly.
        data: scrubSensitiveFields(data),
        userId,
      }),
    onError: ({ error }) =>
      sendToTelemetry({
        name: "chatkit.error",
        error: scrubSensitiveFields(error),
        userId,
      }),
  });

  return <ChatKit control={control} className="h-[600px]" />;
}
```

With the web component, listen for `chatkit.log` and `chatkit.error` events:

```ts
const chatkit = document.getElementById("my-chat") as OpenAIChatKit;

chatkit.addEventListener("chatkit.log", ({ detail }) => {
  sendToTelemetry({
    name: detail.name,
    data: scrubSensitiveFields(detail.data),
    userId,
  });
});

chatkit.addEventListener("chatkit.error", (event) => {
  sendToTelemetry({
    name: "chatkit.error",
    error: scrubSensitiveFields(event.detail.error),
    userId,
  });
});
```

These events can include **PII and message contents**, so avoid blanket-forwarding entire payloads; instead, extract and forward only the fields you need (for example, error codes, item ids, thread ids, and high‑level event names) and/or scrub sensitive fields before sending them to your logging provider.

Separately from your own telemetry, the ChatKit iframe sends **its own outbound telemetry** to OpenAI‑controlled endpoints (Datadog and `chatgpt.com`) for monitoring and debugging. These internal logs **do not contain PII or message input/output content** and are used only to monitor the health of the ChatKit experience.

### Monitor your ChatKit endpoint

On the **backend**, you should still capture basic logs around your ChatKit endpoint so you can correlate client telemetry with server behavior:

- Incoming HTTP request (path, method, user id, thread id).
- Calls to `ChatKitServer.process` and your `Store` implementation.
- Outbound calls to OpenAI or other model providers.
- Any errors raised from tools or your own business logic.


## Security and authentication

Production deployments should treat your ChatKit endpoint as a privileged backend:

- **Authenticate every request** to your `/chatkit` endpoint (for example, with your existing session cookies, bearer tokens, or signed JWTs).
- **Authorize access to threads and attachments** based on your own user and tenant model.
- **Protect secrets** such as OpenAI API keys and internal service credentials in environment variables or a secret manager—never in source control.
- **Validate inputs** before calling tools or downstream systems.

You should also be explicit about how you handle **prompt injection**:

- Treat all user text, attachments, and tool output as untrusted input.
- Avoid building any `role="system"` model inputs from values that might come from the user (including fields like subject lines, titles, or descriptions).
- Keep system messages static or derived only from trusted configuration so users cannot silently change your instructions to the model.

### Authenticate your ChatKit endpoint

The Python SDK expects your own app to handle authentication; `ChatKitServer` works with whatever `RequestContext` you choose. A common pattern is to:

1. Authenticate the incoming HTTP request using your web framework (session middleware, OAuth bearer tokens, etc.).
2. Build a `RequestContext` that includes the authenticated user id, org/tenant, and any roles or scopes.
3. Pass that context into `server.process`.

For example:

```python
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from chatkit.server import ChatKitServer, StreamingResult


def get_current_user(request: Request) -> str:
    # Replace this with your real auth: session cookies, JWTs, etc.
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


app = FastAPI()
store = MyStore(...)
server = MyChatKitServer(store)


@app.post("/chatkit")
async def chatkit_endpoint(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    context = RequestContext(user_id=user_id, locale="en")
    result = await server.process(await request.body(), context)
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")
```

Inside your `Store` and tools, enforce per‑user or per‑tenant access by checking `context.user_id` (and any other identifiers you include) before returning or mutating data.

### Handle PII and data retention

Because ChatKit threads and items can contain user text, attachments, and tool output:

- **Decide what you persist** and for how long. Implement retention policies in your `Store` (for example, delete threads older than N days).
- **Avoid storing unnecessary PII** in thread metadata or tool return values.
- **Encrypt data at rest** using your database’s built‑in features or application‑level encryption where needed.

## Domain keys

Domain keys lock ChatKit down to the hostnames you control. When you embed ChatKit in a web app, the client and iframe can use a domain key to prove that the page is allowed to load ChatKit.

1. Visit the OpenAI domain allowlist page at `https://platform.openai.com/settings/organization/security/domain-allowlist`.
2. Register each hostname that will host your ChatKit UI (for example, `app.example.com`, `support.example.com`).
3. Copy the generated **domain key** for each entry.

Your client configuration should include that `domainKey` alongside the URL to your ChatKit Python backend.

```ts
const options = {
  api: {
    url: "https://your-domain.com/api/chatkit",
    // Copy this value from the domain allowlist entry.
    domainKey: "your-domain-key",
  },
};
```

The ChatKit iframe will make an outbound request to `https://api.openai.com` to verify the domain key on load. If the key is missing or invalid, ChatKit will refuse to load, preventing unauthorized hostnames from embedding your ChatKit experience.

When you go live, make sure all of your production hostnames are registered in the domain allowlist.
