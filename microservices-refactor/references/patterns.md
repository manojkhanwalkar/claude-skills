# Patterns for moving to microservices

Each pattern says what it is, when to use it, and what it costs. Sources are in `sources.md`.

## When not to split

Recommend **don't split** (or a modular monolith) when any of these holds, and say which:

- **Nothing to gain.** No part needs to deploy, scale or be secured separately; one team owns everything. Services add remote failures, eventual consistency and operations work for no return.
- **Small or new system.** Boundaries are still being learned. Monolith first: refactoring across services is much harder than inside one codebase.
- **The boundary is unclear.** The candidate shares vocabulary, entities and tables with its neighbours, or its responsibilities shift every few months.
- **It needs ACID with its neighbours.** Every request updates its tables and another module's in one transaction, and the business can't accept a compensating step.
- **Chatty.** It would call, or be called by, another candidate several times per request. Those belong in one service.
- **Not ready to run services.** No CI/CD that can build and deploy a second unit, no centralised logs, metrics and tracing, no on-call. Build those first ("fly before you can walk").
- **Split by layer.** UI, logic and data split into separate services is a distributed monolith: every feature changes all of them.
- **Nano-services.** One service per entity or per CRUD table ("more the merrier"). Start coarse, one service per bounded context; split further only with a reason.
- **Microservices as the goal.** The count of services is not a measure of success; the gain each one buys is.

A **modular monolith** is often the right first step: enforce the boundary inside one deployable (separate modules, package-private internals, an ArchUnit or import-linter test that fails on cross-boundary access, a schema per module). It keeps most of the design benefit and none of the network cost, and makes a later split cheap.

## Choosing boundaries

- **Business capability.** What the business does (orders, billing, notifications). Stable over time, so services stay stable. Find capabilities through the organisation and a high-level domain model.
- **DDD subdomain and bounded context.** A bounded context is where one model and its vocabulary hold. A service should not span more than one bounded context. Core subdomains (the differentiator) are worth building well; generic ones may be better bought.
- **Aggregates and domain services.** An aggregate is a persistence and consistency boundary and often a good service; a stateless workflow across aggregates (a scheduler) can be a service.
- **Non-functional needs** can split or merge candidates: different scaling, availability, security or technology needs.
- **Validate the boundary**: single responsibility; no chatty calls; deployable without redeploying another service; buildable by one small team; no data-consistency trap. When in doubt, coarser.
- **Change frequency** from git history: decouple what changes often and matters to the business first; leave stable code alone.

## Extraction patterns

### Strangler Fig

Grow the new system around the old one and move behaviour across a piece at a time, until the old part can be removed. Value arrives early and each step is small. The cost is transitional code (routing, adapters, flags) that is thrown away later; plan its removal.

How: intercept calls at a seam (a facade or router in front of the capability, an HTTP proxy or gateway route for external calls, a message router for events), send them to the new service when ready, then remove the old path.

### Branch by abstraction

For a capability called from inside the monolith:

1. Add an abstraction (interface) in front of the capability; move one caller to it, then every caller, with tests.
2. Build the new implementation (the remote client of the new service) behind it.
3. Select the implementation by config or feature flag; run the new one in test first; compare.
4. Switch callers over in stages; delete the old implementation; delete the abstraction if no longer useful.

The system builds and ships at every step; the flag is the rollback.

### Order of extraction

- **Warm up on an edge capability** with few dependencies back to the monolith, to build the pipeline, runbook and observability.
- **Minimise calls back into the monolith.** If the new service must call the monolith, give the monolith a well-defined API and call it through an anti-corruption layer.
- **Split sticky capabilities** (one concept that bundles several, like a "session" that holds preferences, history and a wish list) into domain concepts before moving them; moving the bundle moves the coupling.
- **Decouple vertically and release the data early**: move the capability with its data. A service that still reads and writes the monolith's tables is not independent.
- **Macro first, then micro.**
- **Atomic steps**: each step builds the new piece, moves every consumer of it, and retires the old path, so nothing is left running both ways indefinitely.

### Anti-corruption layer

A translation layer between a new service and a legacy system (or any system with a different model), so the legacy model doesn't leak into the new one. Put translation only in it, not business rules. It adds latency and something to run and scale; validate input at it when trust levels differ; add correlation IDs. Decide upfront whether it is permanent or retired when the migration ends.

## Data

### Database per service

Each service's data is private and reachable only through its API. Options, lightest first: private tables in a shared server (separate DB user with grants), a schema per service, a server per service. Joins across services become API composition or a read model (CQRS) fed by events.

A **shared database** is acceptable only as a transition: no table written by two services ("hot tables"), every schema change backward compatible with the current and previous version of every service, and a dated plan to separate. It keeps build-time and run-time coupling (schema changes, lock contention).

### Moving data out

1. Create the new store and schema; the new service owns it.
2. Backfill from the monolith's tables (idempotent, resumable, verified by counts and checksums).
3. Keep them in step during the transition: the monolith publishes changes through a transactional outbox or change data capture, or the new service becomes the writer and the monolith reads through its API. Avoid ad-hoc dual writes from application code: one of the two writes will fail some day.
4. Move readers to the new service's API or events.
5. Stop the monolith writing; revoke its access; drop or archive the old tables after a retention period.

Watch for lost foreign keys and joins (replace with IDs plus API lookups or local read models), reports that joined across the data (feed them from events), and identifiers that must stay stable.

### Saga

A business transaction across services as a sequence of local transactions. If a step fails, compensating transactions undo the earlier steps. **Orchestration** (one coordinator tells each participant what to do) is easier to follow and test; **choreography** (each step's event triggers the next) has no coordinator but is harder to see whole. Sagas lack isolation: design countermeasures (semantic locks such as a `PENDING` state, commutative updates, re-reading values) for concurrent sagas.

### Transactional outbox

Write the business change and the outgoing message to an outbox table in the same local transaction; a relay (polling or log tailing) publishes it. Solves the dual-write problem. The relay may publish a message twice, so **consumers must be idempotent** (record processed message IDs); keep per-aggregate order.

## API contracts

- Write the contract down (OpenAPI, protobuf, AsyncAPI) in the repo, next to the code that serves it.
- **Additive changes only within a major version**: new optional fields and new operations are fine; removing or renaming a field, changing its type, making an optional field required, or changing its meaning or default is breaking.
- Clients ignore unknown fields (tolerant reader).
- A major version in the path (`/v1`); run old and new major versions side by side for a transition period, and track who still calls the old one before removing it.
- Idempotency keys on operations that are not safe to repeat, so retries can't duplicate effects.
- Errors in one documented shape (RFC 9457 problem details), with a `type` per business outcome so a caller can tell a business "no" from a missing or misconfigured route; map them, don't leak stack traces.

## Between services

- **Resilience**: use the `resiliency` skill: timeouts on every call, retries with exponential backoff and jitter on recoverable errors only and only when safe to repeat (one layer only), token bucket plus concurrency cap per service, 429/503 with `Retry-After`. Decide per call what the caller does when the callee is down (fail fast with a clear error, serve a cached or degraded answer, queue the work).
- **Prefer async** where the caller doesn't need the answer now (notifications, projections): an event through the outbox removes the run-time dependency.
- **Security**:
  - authenticate every service-to-service call: mTLS, or signed short-lived tokens (OAuth2 client credentials, workload identity); validate issuer, audience, expiry and signature; reject when validation can't be completed;
  - authorize in each service, not only at the gateway; a gateway check doesn't authorize a downstream operation;
  - propagate the end user's identity in a verifiable form, separately from the calling service's identity;
  - least privilege: each service gets its own credentials, its own DB user, only the network paths it needs, and secrets from a secret store;
  - no credentials or PII in trace baggage or logs.
- **Observability**: W3C Trace Context (`traceparent`) propagated on every call (OpenTelemetry), a correlation ID in every log line, structured logs centralised, RED metrics (rate, errors, duration) per service and per call, health and readiness endpoints.

## Testing

- **Contract tests**: consumer-driven contracts (Pact; Spring Cloud Contract for Spring producers, which generates provider tests and WireMock stubs for consumers) or schema checks against the OpenAPI/protobuf. A breaking change fails the provider's CI before it ships.
- **Test doubles** for the other service in unit tests, kept honest by the contract tests.
- **Integration tests** per service against its real store (Testcontainers or the project's emulator).
- **A few end-to-end tests** through the main flows on the composed system; most coverage stays in faster tests.
- **Failure tests**: callee down, slow, returning 5xx or 429; the caller behaves as planned.
