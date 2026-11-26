# API checklist

Rules are defaults: a documented, consistent house convention wins. "GQL" and "gRPC" mark the checks that also apply there.

## Resource design

- Paths are nouns for resources and collections (`/orders`, `/orders/{id}`, `/orders/{id}/items`); actions that aren't CRUD are sub-resources (`POST /orders/{id}/cancellation`) or a documented `:action` suffix, used consistently.
- One casing for path segments (kebab-case is common) and one for query parameters; plural collections throughout.
- Nesting at most two levels; beyond that, link by id.
- No file extensions or verbs in paths (`/getOrders`, `/orders/list`); grep `@(Get|Post|Put|Delete|Patch|Request)Mapping\(.*"/(get|create|update|delete|list|do)`.
- Trailing-slash and case handling consistent (Spring 6 no longer matches a trailing slash by default).

## Methods

| Method | Safe | Idempotent | Rules |
|---|---|---|---|
| GET, HEAD | Yes | Yes | Never change state (caches, prefetchers and crawlers call them); no request body |
| PUT | No | Yes | Full replacement; a partial update is PATCH |
| PATCH | No | No (unless designed) | JSON Merge Patch (RFC 7396) or JSON Patch (RFC 6902), stated by media type |
| DELETE | No | Yes | Second delete returns 404 or 204 consistently; no body required |
| POST | No | No | Creation or actions; support `Idempotency-Key` where clients retry |

- Grep for state changes in GET handlers: repository `save`/`delete`, counters, emails.
- `OPTIONS` and `HEAD` work (frameworks usually provide them; check custom filters).

## Status codes

| Situation | Code | Notes |
|---|---|---|
| Read OK | 200 | |
| Created | 201 | `Location` header with the new resource's URL; body optional |
| Accepted for async work | 202 | `Location` of a status resource |
| Success, no body | 204 | Never with a body |
| Not modified | 304 | With `ETag`/`If-None-Match` |
| Malformed request, bad syntax or type | 400 | |
| Well-formed but fails validation or business rules | 400 or 422 | Pick one and use it everywhere |
| Not authenticated | 401 | With `WWW-Authenticate` |
| Authenticated but not allowed | 403, or 404 to hide existence | Pick per resource; don't leak which ids exist to users without access |
| Not found | 404 | |
| Method not allowed | 405 | With `Allow` |
| Not acceptable / unsupported media type | 406 / 415 | |
| Conflict (state, duplicate, idempotency key reused with a different body) | 409 (or 422 for key reuse per the draft) | |
| Precondition failed (`If-Match` mismatch) | 412 | Precondition required: 428 |
| Payload too large | 413 | Limits set in the server and the gateway |
| Too many requests | 429 | `Retry-After`; optionally `RateLimit`/`RateLimit-Policy` (IETF draft) |
| Server error | 500 | Never for a client mistake; grep exception handlers that map everything to 500 |
| Dependency down or overloaded | 502/503/504 | 503 with `Retry-After` when shedding load |

Smells: `ResponseEntity.ok(errorBody)`, `return 200` with `{"success": false}`, `catch (Exception e) { return 500 }` around validation, `@ResponseStatus` missing on custom exceptions.

## Errors (also GQL `extensions`, gRPC `google.rpc.Status` details)

- One error format for the whole API. Default: RFC 9457 problem details, `Content-Type: application/problem+json`, members `type` (an absolute URI identifying the problem type, documented), `title`, `status`, `detail`, `instance`, plus extension members (`errors` with a JSON pointer or field path per validation problem, an `errorCode` clients can branch on).
- RFC 9457 obsoletes RFC 7807; when several problems occur, return the most relevant, or one problem type that lists them.
- No stack traces, exception class names, SQL, internal hostnames or file paths in bodies (Spring: `server.error.include-stacktrace=never`, `include-message` off, a `@ControllerAdvice` that maps known exceptions and logs the rest with a correlation id).
- Errors from filters, security and the framework itself (404 for unknown routes, 405, 415, JSON parse errors) use the same format; check them, they bypass most controller advice.
- A correlation or trace id returned in a header and logged.

## Validation

- Validate at the boundary: Bean Validation (`@Valid`, `@NotNull`, `@Size`, `@Pattern`, `@Positive`) on request DTOs, path and query parameters (`@Validated` on the controller); Pydantic or JSON Schema elsewhere.
- Bounds on every string, array and number; maximum request body size.
- Unknown fields: tolerant readers (ignore unknown fields) are the default for compatibility; strict rejection only where the API documents it. Either way, consistent.
- Enum values unknown to the server give a clear 400/422, not a 500 from deserialisation.
- Dates parsed strictly (RFC 3339 with an offset).

## Collections and queries

- Every list endpoint over a growing collection is paged, with a default and a maximum page size enforced by the server.
- Prefer cursor (keyset) pagination for large or changing data: an opaque `cursor`/`next` token; offset pagination only for small, stable sets. Return `next` as a link or token; don't compute total counts on hot paths unless needed.
- One page envelope for the whole API (`{"items": [...], "next": "..."}` or `Link` headers, RFC 8288), never a top-level array.
- Sort and filter fields allow-listed (no arbitrary field names passed to queries); stable sort order with a tiebreaker.
- Sparse fieldsets or projections where payloads are large (`fields=`), if the API offers them.

## JSON conventions

- One field-name casing across the API (camelCase or snake_case); check the `ObjectMapper` naming strategy and every `@JsonProperty`.
- Dates and times: RFC 3339 / ISO 8601 strings with an offset or `Z` (`WRITE_DATES_AS_TIMESTAMPS` off); dates without time as `YYYY-MM-DD`; durations ISO 8601.
- Money: a decimal string or integer minor units plus an ISO 4217 currency code; never binary floating point.
- 64-bit integer ids for JavaScript clients as strings (JavaScript loses precision above 2^53).
- Booleans as booleans; numbers as numbers; no stringly-typed values.
- `null` versus absent: one documented rule (`Include.NON_NULL` or explicit nulls); PATCH semantics depend on it.
- Enums as strings, documented as extensible so adding a value is not a breaking change for tolerant clients.
- Top-level response is an object, so it can gain fields.
- No internal or persistence-only fields (database ids of other tenants, password hashes, internal flags, `@Version` columns unless used for `ETag`).

## Compatibility and versioning

See `compatibility.md`. Check: a version scheme exists and is used consistently (URI `/v1`, header, or media type); deprecated endpoints return `Deprecation` (RFC 9745) and `Sunset` (RFC 8594) with a `Link` to the docs; the spec carries `deprecated: true`.

## Concurrency, retries and caching

- Updates that can collide: return `ETag` on reads (from a version column, not a body hash), require `If-Match` on `PUT`/`PATCH`/`DELETE` (412 on mismatch, 428 when missing if required). Otherwise the last writer silently wins.
- POST creates or charges that clients or gateways retry: accept an `Idempotency-Key` header (IETF httpapi draft, `draft-ietf-httpapi-idempotency-key-header`; Stripe's convention), store key plus request fingerprint plus outcome for a documented window, return the first outcome on replay, 409 while the first is in flight, and an error when the same key arrives with a different body. Keep the key when the outcome is unknown.
- `Cache-Control` on cacheable `GET`s (`max-age`, `ETag`); `no-store` on responses with personal or sensitive data; `Vary` when the response depends on headers (`Authorization`, `Accept-Language`).

## Security shape (report to the security area too)

OWASP API Security Top 10 (2023), the API-shaped items:

- API1 BOLA: every route taking an object id checks that the caller may access that object (scoped query `findByIdAndOwnerId`, or a policy check), not just that they are logged in.
- API2 Broken authentication: auth on every non-public route; tokens never in query strings.
- API3 Broken object property level authorization: request DTOs allow-list writable fields (no binding of `role`, `owner`, `price`, `status` from the client); response DTOs allow-list readable fields.
- API4 Unrestricted resource consumption: page-size caps, body-size limits, rate limits (`resiliency`), timeouts, upload limits.
- API5 BFLA: admin functions on separate routes with role checks, not hidden by obscurity.
- API6 Sensitive business flows: purchase, sign-up and similar flows have abuse limits.
- API7 SSRF: URLs accepted from clients are allow-listed before the server fetches them.
- API8 Misconfiguration: CORS allow-list (never `*` with credentials), TLS only, security headers, verbose errors off.
- API9 Inventory: every route is in the spec; old versions and debug endpoints (`/actuator` beyond health, Swagger UI in production) are known and protected.
- API10 Unsafe consumption of APIs: responses from third-party APIs validated and bounded like client input.

## Documentation

- An OpenAPI 3.x spec exists for every served API, matches the code, and lists error responses, auth schemes, examples and `operationId`s.
- Spectral's `spectral:oas` ruleset passes, or its exceptions are recorded.

## Calling other APIs (client side)

- Clients tolerate unknown fields and new enum values.
- Retries only on idempotent methods or with an idempotency key; honour `Retry-After`.
- Timeouts on every call (`resiliency`).
