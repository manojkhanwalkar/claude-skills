# Checklists

Tick every item, or say in the report why it doesn't apply.

## Assess

- [ ] Every build module and top-level package listed, with its dependencies on the others; cycles marked.
- [ ] Every entry point listed per module (routes, handlers, consumers, schedulers, CLIs).
- [ ] Every data store, table or collection listed with **who reads and who writes it**; tables written by more than one module marked.
- [ ] Every transaction that touches more than one module's tables listed.
- [ ] Cross-boundary call counts per request on the main flows; chatty pairs marked.
- [ ] Outbound calls to other services and third parties listed (feed `resiliency`).
- [ ] Deploy units today, and what deploys together.
- [ ] Change frequency per package from 12 months of git history; files that always change together.
- [ ] Scaling, availability, security and compliance needs per candidate (PII, card data, admin surfaces).
- [ ] Ownership per candidate (CODEOWNERS, authors).
- [ ] Every candidate has a recommendation (now, later, never) **with reasons**; every "later" names its blocker; every "never" names the "when not to split" case.
- [ ] A modular monolith considered as the alternative for each candidate.

## Plan

- [ ] Candidates ordered by value ÷ risk; the first is an edge capability with few calls back into the monolith.
- [ ] Contract written (OpenAPI, protobuf or AsyncAPI), versioned, with errors and idempotency keys.
- [ ] Data ownership: tables moving, the transition sync (outbox or CDC, not ad-hoc dual writes), how other modules will read.
- [ ] Each former cross-module transaction: saga with named compensations, or accepted eventual consistency.
- [ ] Migration steps as branch by abstraction, each shippable, each with its rollback.
- [ ] The step after which rollback needs a data migration, marked for sign-off; the user approves it explicitly before that PR.
- [ ] The new service has its data (through the monolith, or backfilled and synced) before it takes any traffic.
- [ ] Prerequisites listed (CI for a second deployable, registry, secrets, observability).

## Extract (one service per PR)

- [ ] Interface in the monolith; every caller goes through it; behaviour unchanged, tests green.
- [ ] New service module or repo, following the project's layout and style.
- [ ] Own config; secrets from env or a secret store, never committed.
- [ ] Own store or schema, migrations, least-privilege DB user.
- [ ] Contract implemented; input validated at the boundary; errors mapped to the contract shape.
- [ ] Health and readiness endpoints; graceful shutdown; start-up tolerates dependencies not ready yet.
- [ ] Dockerfile (non-root, pinned base image) and compose entry; the whole system starts locally.
- [ ] CI builds, tests, measures coverage and builds the image for the new service; workflow lists kept in sync (for example artifact-cleanup); Dependabot covers any new directory or ecosystem.
- [ ] Service-to-service auth (mTLS or short-lived signed tokens), authorization in the service, user identity propagated verifiably, least privilege.
- [ ] Timeouts, retries (backoff and jitter, safe-to-repeat only, one layer) and limits per the `resiliency` skill.
- [ ] Trace context and correlation IDs propagated; structured logs; per-call metrics.
- [ ] Contract tests on both sides in CI.
- [ ] Callers switched through the interface's remote implementation behind a flag, off by default.
- [ ] Failure behaviour tested: callee down, slow, 5xx, 429; the worst-case wait (connect timeouts × attempts + backoff + one read timeout) stated and inside the caller's budget.
- [ ] ADR note (context, decision, alternatives, consequences, rollback); README run and config docs.
- [ ] Design doc and system diagram updated (where the project keeps them).

## Verify

- [ ] Changed modules build and their tests pass locally; CI green on the full suite and the coverage gate.
- [ ] Contract tests pass, and a deliberate contract break makes them fail (then reverted).
- [ ] Local run: new service healthy; main flow works end to end with the flag on and with it off.
- [ ] New service stopped: the caller fails or degrades as planned, without hanging.
- [ ] From the cut-over PR on, no shared writes: grep the monolith for the moved tables and repositories; no write path left outside the new service; DB grants enforce it once the data has moved.
- [ ] One request traced across both services; its correlation ID found in both logs.
- [ ] Security checks run on the PR through pr-review: security-review plus every check that applies (compliance-check for personal, payment or financial data; owasp-llm-top10, digital-regulation-check, ada-compatibility as their triggers say).

## Usual mistakes

- **Distributed monolith**: services that must be deployed together, share tables, or call each other on every request. If one change needs several services redeployed, the boundary is wrong.
- **Data left behind**: the logic moved but the new service still reads and writes the monolith's tables.
- **Dual writes from application code** during data migration: they drift on the first partial failure. Use an outbox or CDC.
- **Big bang**: several services, or the whole cut-over, in one PR with no flag. Nothing can be rolled back.
- **Retries everywhere**: each layer retries, and an outage multiplies calls. Retry at one layer, only when safe to repeat.
- **No timeouts**: a slow callee holds every caller's threads.
- **Gateway-only auth**: internal calls trusted because they are internal.
- **Breaking the contract**: a renamed field or a new required field shipped without a new version; contract tests would have caught it.
- **Transitional code that never leaves**: flags, adapters and the old implementation kept after cut-over. Plan and do the removal PR.
- **Too fine-grained**: a service per entity; merge them back into the bounded context.

## Usual mistakes in the code

Reviews of real extractions kept finding these. Check each on the service and its clients before the PR.

- **Idempotency key freed on an unknown outcome.** A timeout, 5xx or throttle may have delivered; freeing the key lets the retry send twice. Free a key only on a clear refusal; keep it as uncertain otherwise, and answer repeats from it.
- **Stacked retries.** Client, HTTP library and service each retry, and attempts multiply. Pick one layer (usually the service, next to the provider); the client retries only what never reached the callee, such as a failed connect, with the same key.
- **Connect timeout as long as the whole budget.** A connect should fail in a second or two; give it its own short timeout, separate from the read timeout, and add up the worst case across retries.
- **Secrets over plain HTTP.** A configurable service URL that carries a token must be `https`, except for localhost or a compose service name; refuse to start otherwise.
- **One setting read two ways.** An empty enum or mode variable is "unset" in one place and an error or a different default in another. Parse each setting once, at start-up, and treat blank as unset everywhere.
- **Ambiguous answers driving a saga.** A bare 404 can mean "no such user" or "endpoint not deployed"; a 401 or 403 is a config error. Compensate (refund, cancel) only on a typed business answer (an RFC 9457 problem `type`); retry and alert on the rest.
- **Missing audit actor for service calls.** Audit entries written for a service call record the service (`service:<name>`), not a user or nobody, and only when something changed.
- **Flaky absence checks.** "The raw value doesn't appear in the stored hash" fails by chance when the value is short and the hash is random hex. Assert the stored value equals the expected keyed hash, or check a whole field.
