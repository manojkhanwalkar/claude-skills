# Compatibility, versioning and deprecation

## Additive (safe for tolerant clients)

- A new endpoint, a new optional request field or query parameter, a new response field, a new header.
- A new enum value, only if the API documents enums as extensible and clients tolerate unknown values.
- A new error type within the existing error format.
- Relaxing validation (accepting more inputs).

## Breaking

- Removing or renaming a path, field, parameter or header; changing a field's type, format or meaning.
- Making an optional request field required; tightening validation that clients' current requests fail.
- Changing a status code clients branch on, the error body's shape, or the success body's shape (including wrapping a top-level array or adding pagination to an unpaged list).
- Changing default sort order, page size or filtering when clients rely on them.
- Changing authentication or required scopes.
- Changing `null` versus absent handling.

Detect with `oasdiff breaking old.yaml new.yaml` when specs exist (ask before downloading it), and with contract or consumer-driven tests (Pact, Spring Cloud Contract) when the project has them.

## Versioning

- Choose one scheme per API and use it everywhere: a URI prefix (`/v1/`, simplest and most common), a header, or a media-type parameter. A new major version only for breaking changes; additive changes ship in place.
- Run old and new versions side by side through the deprecation window; share the implementation behind version-specific DTOs and mappers.

## Migration path for a breaking fix

1. Add the new shape alongside the old (a new field, endpoint or version); old clients keep working.
2. Mark the old one: `deprecated: true` in the spec, `Deprecation` header (RFC 9745: a structured-field date, `Deprecation: @<epoch-seconds>`, not an HTTP-date or `true`, which were earlier draft forms), `Sunset` header (RFC 8594, an HTTP-date) with the removal date, and `Link: <docs-url>; rel="deprecation"`.
3. Measure use of the old shape (logs or metrics per client) and tell its consumers.
4. Remove it after the sunset date, in its own PR.

For **internal** APIs whose every caller is in this repository, skip the window: change the API and every caller in one commit, with tests on both sides.
