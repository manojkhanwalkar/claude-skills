# Deep review checklists

Leads for the areas this skill reviews itself, not findings. Confirm each one by reading the code and tracing the real path. The "usually fine" notes list common false positives.

## Security recheck

- **Entry points.** Every route, handler, tool or consumer has the authentication and authorization the docs claim. Path normalisation can't bypass filters (encoded paths, `;params`, case). Admin or debug endpoints are off by default.
- **Input at trust boundaries.**
  - Sizes are capped: bodies, uploads, arrays, strings.
  - Parsers are bounded: images (pixel count and decode memory), archives (zip bombs), XML (XXE, entity expansion), JSON (depth).
  - Types are checked by content, not by name or declared type.
- **Sinks.** SQL and NoSQL queries are parameterized. Shell commands get no user input. File paths are resolved and confined, with no symlink following. HTML is encoded. Redirects are allow-listed. Outbound URLs from user input are checked against SSRF.
- **Secrets.** No secret is in the source, and test-looking keys are built at run time. Required secrets have no defaults. Secrets are redacted in `toString` and logs.
- **Crypto.** Standard algorithms only. Comparisons that need constant time use it. JWTs pin the algorithm and check expiry, issuer and audience. Random values used for security come from a CSPRNG.
- **PII.** No PII in logs, exception messages, URLs or caches. Error responses don't echo input.
- **Dependencies.** Versions are pinned. Look for known-vulnerable versions, and run the ecosystem's audit tool if one is present.
- **Docs drift.** Every control in the security docs is still enforced in the code.
- Usually fine: internal-only services on a private network that the docs say are unauthenticated (report the risk, don't "fix" it with a large redesign); test fixtures with fake data.

## Correctness

- **Null and missing values.** Dereferences of values that can be null, None or undefined: map lookups, optional fields, the result of a find, parsed input.
- **Comparisons and arithmetic.** Off-by-one bounds, `==` vs `.equals` (Java), `is` vs `==` (Python), integer overflow and truncating division, float equality, and locale- or case-sensitive string comparisons that should not be.
- **Error handling.** Swallowed exceptions, catch blocks that are too broad, the wrong exception type for the caller's contract, and error paths that leave half-updated state.
- **Shared state.** Races, unsafe publication, check-then-act, lazy initialization and executor misuse belong to the Concurrency area (`concurrency-audit`); file each race under one area only.
- **Intent drift.** Code that contradicts its name, its comments, its docs or its tests. Decide which side is right before fixing either.
- Usually fine: defensive null checks the type system already rules out (remove them only as readability, not as a bug); behaviour that looks odd but is pinned by a test or a documented compatibility rule (for example, matching another implementation byte for byte).

## Resilience

- **Timeouts.** Every outbound call (HTTP, DB, cache, queue, LLM, DNS) has a connect and a read timeout. The library defaults are often infinite.
- **Retries.** Only for idempotent operations. Retries are bounded, back off with jitter, and never wrap an operation that already retries (multiplying retries). Error codes that will never succeed (4xx) are not retried.
- **Fail fast and degrade.** A slow dependency can't exhaust the thread or connection pool. A circuit breaker or bulkhead is used where the framework offers one. A clear user-facing error is returned instead of a 500 with a stack trace.
- **Limits.**
  - Pools have a size.
  - Queues and caches are bounded and evict.
  - Recursion depth and batch sizes are bounded.
  - Scheduled jobs can't overlap or pile up.
- **Cleanup.** Resources are closed on every path (try-with-resources, `with`, `defer`). Partial writes are rolled back or made idempotent, and a multi-step write either uses a transaction or is designed so a re-run finishes it.
- **In-flight work.** A request that is in flight during a delete or logout can't resurrect what was deleted. (Races on shared state are the Concurrency area's, through `concurrency-audit`.)
- **Lifecycle.**
  - Services start in any order (lazy connections, reconnect after failure).
  - Health and readiness reflect real dependencies where it matters.
  - Shutdown is graceful: in-flight work drains and executors stop.
- **Bad responses.** Null or empty bodies, a malformed payload, an unknown enum value or a missing field from a dependency is handled, never a crash.
- **Tests.** Each failure mode that matters has a test that simulates it: a mock server returning 5xx or a delay, a thrown IOException, a full queue.
- Usually fine: demo or CLI tools where a crash is acceptable (say so); retries skipped deliberately for non-idempotent calls.

## Concurrency, performance, DynamoDB, API, modernization, design and doc comments

Owned by `concurrency-audit`, `perf-review`, `dynamodb-optimizer`, `api-audit`, `java-modernizer`, `design-patterns` and `documenter`, which carry their own checklists. Don't repeat their checks here.

## Duplication

- The same validation, mapping, error handling or client set-up copied across modules → one shared helper in the shared library the project already has.
- Constants, limits, paths and messages repeated in code, config and UI → a single source, or at least a test that pins them together.
- Near-identical classes or tests that differ by one parameter → parameterize.
- Two implementations of the same rule that drifted apart (for example, client-side and server-side validation) → align them, and note which one is authoritative.
- Usually fine: deliberate duplication across a trust or deployment boundary, for example a client and a server each validating, or services that must not share a library. Keep it, but make sure the copies agree.

## Readability and maintenance

- Dead code: unused imports, methods, classes, config keys, feature flags and commented-out code.
- Functions over about 50 lines or nested more than 3 deep → early returns and extracted helpers with names that explain intent.
- Names that lie, comments that are out of date, and TODOs that are already done.
- Inconsistent error handling: mixed exception types and HTTP error shapes for the same kind of failure.
- Reinventing standard-library or framework utilities.
- Magic numbers → named constants with units in the name (`TIMEOUT_MS`, `MAX_BYTES`).
- README, architecture docs, config tables and diagrams that disagree with the code. Fix the docs, or fix the code if the docs are the spec.
- Usually fine: style preferences that the project's existing conventions contradict. Follow the project.
