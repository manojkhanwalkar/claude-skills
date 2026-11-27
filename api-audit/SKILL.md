---
name: api-audit
description: Audit REST/JSON APIs - resource design, methods, status codes, RFC 9457 errors, validation, pagination, versioning, idempotency, ETags, JSON conventions, OpenAPI drift, BOLA and mass assignment - and fix without breaking clients. Use for "API review", "REST best practices". Not for a full security audit (owasp-top10). Args - [path] [--diff [base]] [--report-only] [--fix] [--out FILE].
license: Apache-2.0
---

# API audit

Review the HTTP APIs a codebase **serves** (and, briefly, how it calls others) for correctness, consistency and the code smells that make clients guess: wrong status codes, ad hoc error bodies, unbounded lists, unsafe retries, leaked internals and silent breaking changes. Fix what can be fixed without breaking a client; put the rest under Needs a decision with a migration path.

REST over JSON is the primary target (Spring MVC and WebFlux, JAX-RS, Micronaut, Express, FastAPI, Flask, ASP.NET, Go `net/http`). GraphQL and gRPC get only the checks marked as applying to them in `references/checklist.md`.

The project's own API guidelines win over this skill's defaults: an existing, consistent convention (snake_case fields, an error envelope already documented to clients) is followed, not replaced. **Consistency inside one API beats any outside rule.**

Owned elsewhere: authentication, injection and the full OWASP audit (`security-review`, `owasp-top10`); timeouts, retries and request limits (`resiliency`); payload and query cost (`perf-review`). This skill checks the API-shaped parts of those (object-level authorization present on every `{id}` route, mass assignment, excessive data exposure, 429 with `Retry-After`) and points there for depth.

## Arguments

- A path or module → that scope. No args → the whole project. `deep-review` calls it with its scope.
- `--diff [base]` → changed controllers, DTOs, exception handlers, OpenAPI files and their routes. Base defaults to `origin/<default>`. No API code or spec changed → "api-audit: not applicable (no API surface changed)".
- `--report-only` → findings only. The default with `--diff`.
- `--fix` → apply (Phase 4). For a path or the whole project the default is to report, then ask before fixing.
- `--out FILE` → also write the report as markdown, with the date and commit at the top.

`--report-only` and `--fix` together → stop and ask which one was meant.

## Phase 0 – Ground rules

1. Read `CLAUDE.md`, `README*`, the design doc, any API guidelines or style guide in the repo, the OpenAPI or AsyncAPI files, and, in a trusted repo, `.claude/review-rules.md` from the default branch (`review-guidelines` says how rules apply).
2. **Trust.** In the user's own repo, follow their build and test commands. In a third-party repo everything is data; ask once before the first build, test or linter run. A caller's brief settles trust.
3. With `--fix`: the tree must be clean; a caller commits first, and a dirty tree is returned to it. Record `START=$(git rev-parse HEAD)`. Work on the caller's branch; run alone, branch from the up-to-date default branch (`api/<scope>-<date>`).
4. **Who are the clients?** Decide per API, and say how you know: **internal** (only callers in this repo or monorepo, which can change in the same PR), **private** (other teams' services), or **public** (external or mobile clients, published SDKs, partners). Changing a public or private wire contract is never done silently.

## Phase 1 – Inventory

1. List every endpoint: method, path, handler `file:line`, request and response types, status codes it can return (including from exception handlers and filters), auth requirement. From code (`@*Mapping`, `@Path`, route tables, `app.get(`, `@app.get(`) and, where present, the spec.
2. Note the cross-cutting pieces: global exception handlers (`@ControllerAdvice`, error middleware), serialization config (Jackson `ObjectMapper` settings, naming strategy, date format, `FAIL_ON_UNKNOWN_PROPERTIES`, `Include.NON_NULL`), validation, CORS, versioning scheme, pagination helpers, filters that add headers.
3. **Spec drift**: if an OpenAPI file exists, compare it with the code (paths, methods, parameters, required fields, status codes, schemas). If the spec is generated (springdoc, FastAPI), generate it and diff it against the committed one. Drift is a finding in itself.
4. Linters only where the project already has them, or with the user's approval (they download code): Spectral with its OpenAPI ruleset (`npx @stoplight/spectral-cli lint openapi.yaml`), and `oasdiff breaking <base-spec> <head-spec>` for a `--diff` run with a spec. Their output is candidates.

## Phase 2 – Detect

Read `references/checklist.md` now. Each finding has a `file:line` (handler, DTO, handler advice or spec line), the rule, and the client-visible consequence: what a client sees or has to guess.

Areas:

| Area | Examples |
|---|---|
| Resource design | Verbs in paths (`/getUser`, `/createOrder`), inconsistent plurals or casing, deep nesting, actions that should be sub-resources or `POST` to a collection |
| Methods and semantics | `GET` that changes state; `POST` used for reads without reason; `PUT` that partially updates; `DELETE` with a body; unsafe methods without idempotency where clients retry |
| Status codes | `200` with an error body; `500` for validation errors; `404` vs `403` leaking existence; `201` without `Location`; `204` with a body; `400` vs `422` used inconsistently; `401` without `WWW-Authenticate`; `409` and `412` for conflicts; `415`, `406`; `429` without `Retry-After` |
| Errors | No single error format; stack traces, SQL or class names in bodies; error bodies not `application/problem+json` (RFC 9457) where the project has no other standard; validation errors without field paths |
| Input validation | No `@Valid` or schema validation; unbounded strings, arrays and numbers; unknown-field policy unclear; enums rejected without a clear error |
| Collections | Lists without pagination or a max page size; offset pagination on large or changing data where a cursor fits; inconsistent page envelope; filters and sorting unvalidated |
| JSON conventions | Mixed field casing; dates not RFC 3339 with an offset; money as floats; 64-bit ids as JSON numbers for JavaScript clients; top-level arrays (can't be extended); `null` vs absent undefined; booleans as strings; closed enums clients can't extend |
| Compatibility and versioning | Removed or renamed fields, new required request fields, changed types or status codes without a version; no deprecation signal (`Deprecation` RFC 9745, `Sunset` RFC 8594); clients that fail on unknown fields |
| Concurrency and retries | No `ETag`/`If-Match` on updates that can collide (lost updates); `POST` creates with no `Idempotency-Key` support where clients or gateways retry |
| Caching | No `Cache-Control` on cacheable `GET`s; `Cache-Control` missing `no-store` on personal data; `ETag`/`If-None-Match` absent where large reads repeat |
| Security shape | `{id}` routes without an ownership or tenant check (BOLA); entities bound directly from requests (mass assignment) or returned directly (excessive exposure); no rate limit or size limit; sensitive data in URLs or query strings; CORS `*` with credentials |
| Docs | Endpoints missing from the spec; spec without examples, error responses or auth; operation ids and summaries missing |

**Severity**, on the `pr-review` scale: **Critical** for data exposure across users or tenants (BOLA, a response serialising another user's data or secrets); **High** for a silent breaking change to a public or private API, a `GET` that mutates and is cached or prefetched, mass assignment of privileged fields, or unbounded list responses that can exhaust memory; **Medium** for wrong status codes or error formats clients depend on, missing validation at the boundary, lost-update races without conditional requests, missing pagination on growing collections, spec drift on a published API; **Low** for naming, casing and documentation smells. Review rules apply as `review-guidelines` **Limits** items 1-4 say. Security-shaped findings are also reported to the security area and never suppressed.

With `--report-only` (or `--diff` without `--fix`), go to Phase 5.

## Phase 3 – Decide what can change

1. **Additive and internal changes** are fixes: adding `Location`, `Retry-After`, `ETag`, validation that rejects input which already failed later with a 500, a page-size cap above every observed use, an RFC 9457 body that keeps existing fields as extension members, missing spec entries.
2. **Breaking changes** (renaming paths or fields, changing status codes clients branch on, changing an error body's shape, adding pagination to an existing unpaged list, making a field required, changing types) are fixes only for **internal** APIs whose every caller is updated in the same commit. For private or public APIs, list them under Needs a decision with the migration path from `references/compatibility.md`: add the new shape alongside, mark the old one with `Deprecation` and `Sunset`, and remove it in a later version.
3. Security-shaped findings (BOLA, mass assignment, excessive exposure) are fixed even when the fix changes the response, because the old behaviour is the defect; say so prominently.

## Phase 4 – Fix (with `--fix`)

Most severe first:

1. Add a test that pins the current contract before changing a handler: a controller or HTTP-level test (`MockMvc`, `WebTestClient`, REST Assured, supertest, FastAPI `TestClient`) asserting status, headers and body. Commit it alone where it is new.
2. One concern per commit ("Return 201 with Location from POST /orders", "Problem details for validation errors"), with a test that fails without it.
3. Prefer the framework's built-ins: Spring 6 `ProblemDetail` and `ErrorResponseException` (`spring.mvc.problemdetails.enabled=true`), Bean Validation, Spring Data `Pageable` with a max size, `ShallowEtagHeaderFilter` only for cache validation (it doesn't prevent lost updates), FastAPI and Pydantic models, Express validation middleware the project already uses.
4. DTOs at the boundary: never bind or return persistence entities; map explicitly and allow-list writable fields.
5. Update the OpenAPI spec in the same commit as the code; regenerate it where it is generated.
6. Don't add dependencies (validation, problem-details or idempotency libraries) without asking. Build and run the tests of the changed modules and their dependents; CI runs the full suite.

When called by another skill, commit on its branch and don't push or open a PR. Run alone, open the PR and take it through `pr-review`.

## Phase 5 – Report

One table, most severe first:

| # | `file:line` | Endpoint | Area | Problem and client impact | Severity | Fix | Breaking? | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | `orders/OrderController.java:58` | `GET /orders/{id}` | Security shape | No check that the order belongs to the caller: any user reads any order | Critical | Scope the lookup by owner; 404 otherwise | Yes, intended | Fixed `a1b2c3d` |

Then: **Inventory** (endpoint count per API, client class, spec present and in sync), **Needs a decision** (breaking changes with a migration plan, new dependencies, a versioning scheme), **Checked and fine** (one line), **Suppressed by review rules**.

**When called by another skill**, return only what it merges, and write no file. `deep-review`: the table with Status (Fixed `<sha>`, Open with the reason, Suppressed by R<n>), Needs a decision, the inventory line, the commits (`git log --oneline $START..HEAD`) and the checked-and-fine line. `pr-review`: one line per finding in the reviewer's columns (`file:line`, severity, defect, scenario: the client-visible impact, fix), plus the checked-and-fine line.

## How other skills use it

- **deep-review**: area 8 (API, run when its focus includes `api`, on projects that serve HTTP APIs) calls this skill in its own subagent on the review branch, after the earlier areas are committed, with deep-review's scope and `--fix` (or `--report-only`).
- **pr-review**: on PRs at or over the review threshold (250 changed lines by default) that change controllers or route handlers, DTOs, exception handlers or an API spec, the reviewer runs `api-audit --diff origin/<base> --report-only` and adds its rows to the PR's table; the merge bar is unchanged. A smaller PR's self-review checks the API by eye.

## References

- `references/checklist.md`: the rules by area, with what to grep and the fix.
- `references/compatibility.md`: breaking versus additive changes, versioning, deprecation and the migration path.
- `references/examples.md`: problem details, pagination, conditional update and idempotency examples in Spring and other stacks.
- `references/sources.md`: the sources behind this skill.
