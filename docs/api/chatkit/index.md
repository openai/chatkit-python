# Chatkit Python API Reference

What you'll find here:

- **Core server API**: [`chatkit.server`](server.md) – `ChatKitServer` and related helpers for receiving messages, streaming responses, and wiring up tools and widgets.
- **Store integration**: [`chatkit.store`](store.md) – interfaces and utilities for persisting threads, items, and metadata.
- **Agents integration helpers**: [`chatkit.agents`](agents.md) – helpers and utilities for using ChatKit together with the Agents SDK.
- **Data models and types**: [`chatkit.types`](types.md) – Pydantic models for threads, items, events, and other shared types.
- **Errors**: [`chatkit.errors`](errors.md) – structured error types your ChatKit integration can raise so ChatKit can emit consistent `ErrorEvent`s to the client.
- **Widgets**: [`chatkit.widgets`](widgets.md) – models and helpers such as `WidgetTemplate`, `DynamicWidgetRoot`, and `BasicRoot` for building rich UI responses.
