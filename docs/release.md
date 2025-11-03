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

### 1.1.0

- `CustomSummary`, `CustomTask`, and `EntitySource` types have been updated to restrict `icon` to `IconName`.
- All `_to_input` methods on `ThreadItemConverter` have been updated to be asynchronous.
