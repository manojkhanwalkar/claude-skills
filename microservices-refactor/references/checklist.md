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
- [ ] CI builds, tests, measures coverage and builds the image for the new service; workflow lists kept in sync (for example artifact-cleanup).
- [ ] Service-to-service auth (mTLS or short-lived signed tokens), authorization in the service, user identity propagated verifiably, least privilege.
- [ ] Timeouts, retries (backoff and jitter, safe-to-repeat only, one layer) and limits per the `resiliency` skill.
- [ ] Trace context and correlation IDs propagated; structured logs; per-call metrics.
- [ ] Contract tests on both sides in CI.
- [ ] Callers switched through the interface's remote implementation behind a flag, off by default.
- [ ] Failure behaviour tested: callee down, slow, 5xx, 429.
- [ ] ADR note (context, decision, alternatives, consequences, rollback); README run and config docs.
- [ ] Design doc and system diagram updated (the user's rules).

## Verify

- [ ] Changed modules build and their tests pass locally; CI green on the full suite and the coverage gate.
- [ ] Contract tests pass, and a deliberate contract break makes them fail (then reverted).
- [ ] Local run: new service healthy; main flow works end to end with the flag on and with it off.
- [ ] New service stopped: the caller fails or degrades as planned, without hanging.
- [ ] From the cut-over PR on, no shared writes: grep the monolith for the moved tables and repositories; no write path left outside the new service; DB grants enforce it once the data has moved.
- [ ] One request traced across both services; its correlation ID found in both logs.
- [ ] Security checks run on the PR (security-review, plus compliance-check if the moved data is personal, payment or financial).

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
