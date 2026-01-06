# Release process/changelog

The project follows a slightly modified version of [semantic versioning](https://semver.org/spec/v2.0.0.html). The SDK is still evolving and certain backwards-incompatible changes may be released as minor versions.

## Minor versions

We will increase minor versions for **breaking changes** to any public interfaces. For example, going from `1.0.x` to `1.1.x` might include breaking changes.

If you don't want breaking changes, we recommend pinning to `1.0.x` versions in your project.

## Patch versions

We will increment patch versions for non-breaking changes:

- Bug fixes
- New features
- Changes to private interfaces

## Breaking change changelog

### 1.5.0

Two-phase uploads:

- `upload_url` was removed from `FileAttachment` and `ImageAttachment`; use `upload_descriptor` instead.
- `ChatKitServer` now saves the created attachment metadata in the store when handling the `attachments.create` request; remove the store-write step in `AttachmentStore.create_attachment`.


### 1.4.0

- Widget and action classes are still usable but marked as deprecated in favor of using `WidgetTemplate` to build widgets from `.widget` files.
- Added `jinja2` as a required dependency for widget template rendering.
- A stop button is now shown by default during streaming, allowing users to cancel the stream mid-response. Integrations can override `ChatKitServer.get_stream_options` to change this behavior.

### 1.3.0

- Fixed the type for the `defaultChecked` property of `Checkbox` widgets, updating it from `string` to `bool`.

### 1.2.0

- Updated `agents.stream_agent_response` to add annotation parts as they are received rather than adding all the annotations at the end after the response is completed.
- Added support for rendering `container_file_citation`.

### 1.1.0

- `CustomSummary`, `CustomTask`, and `EntitySource` types have been updated to restrict `icon` to `IconName`.
- All `ThreadItemConverter` methods have been updated to be asynchronous.
