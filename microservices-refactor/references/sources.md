# Sources

Pages read on 2026-11-21 when this skill was written.

## Decomposition and migration

- [Martin Fowler, Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html): replace a legacy system gradually through seams, gaining value early at the cost of transitional architecture.
- [Martin Fowler, Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html): an abstraction in front of a supplier, a new implementation behind it, switch callers in stages, delete the old one.
- [Zhamak Dehghani, How to break a Monolith into Microservices](https://martinfowler.com/articles/break-monolith-into-microservices.html): start with an edge service, minimise calls back to the monolith, split sticky capabilities, move data with the logic, macro before micro, atomic steps.
- [Martin Fowler, MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html): boundaries are hard to get right upfront; don't start a new system with microservices.
- [Martin Fowler, Microservice Trade-Offs](https://martinfowler.com/articles/microservice-trade-offs.html): strong boundaries, independent deployment and technology diversity against distribution, eventual consistency and operational complexity.
- [Sam Newman, Monolith to Microservices](https://samnewman.io/books/monolith-to-microservices/): when not to migrate, where to start, Strangler Fig, UI composition, branch by abstraction, splitting the database, sagas.
- [Chris Richardson, Decompose by business capability](https://microservices.io/patterns/decomposition/decompose-by-business-capability.html): services around stable business capabilities, found through the organisation and domain model.
- [Chris Richardson, Decompose by subdomain](https://microservices.io/patterns/decomposition/decompose-by-subdomain.html): services per DDD subdomain; core, supporting and generic subdomains.
- [Chris Richardson, Potholes in the road from monolithic hell](https://microservices.io/microservices/general/2018/11/04/potholes-in-road-from-monolithic-hell.html): adoption anti-patterns, including microservices as the goal, "more the merrier" and flying before walking.
- [Microsoft, Identify microservice boundaries](https://learn.microsoft.com/en-us/azure/architecture/microservices/model/microservice-boundaries): from bounded contexts and aggregates to services; validate against chattiness, independent deployment and consistency; start coarse.
- [Microsoft, Anti-Corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer): a translation layer between new and legacy models; its latency, operation and retirement.

## Data and consistency

- [Chris Richardson, Database per service](https://microservices.io/patterns/data/database-per-service.html): private data per service (tables, schema or server), API composition and CQRS for queries, sagas for transactions.
- [AWS Prescriptive Guidance, Shared-database-per-service pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-data-persistence/shared-database.html): when a shared database is tolerable, no hot tables, backward-compatible schema changes, the coupling it keeps.
- [Chris Richardson, Saga](https://microservices.io/patterns/data/saga.html): local transactions with compensations, orchestration vs choreography, lack of isolation and countermeasures.
- [Chris Richardson, Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html): the outbox table in the business transaction, a relay, ordering, and idempotent consumers for duplicates.

## Contracts, testing and observability

- [Google AIP-180, Backwards compatibility](https://google.aip.dev/180): what is a breaking change within a major version (removals, renames, type and semantic changes).
- [Martin Fowler, Contract Test](https://martinfowler.com/bliki/ContractTest.html): tests that keep test doubles of an external service honest.
- [Pact documentation](https://docs.pact.io/): consumer-driven, code-first contracts by example.
- [Spring Cloud Contract, Introduction](https://docs.spring.io/spring-cloud-contract/reference/getting-started/introducing-spring-cloud-contract.html): producer tests generated from contracts and WireMock stubs for consumers.
- [Chris Richardson, Distributed tracing](https://microservices.io/patterns/observability/distributed-tracing.html): a request ID propagated to every service and logged.
- [OpenTelemetry, Context propagation](https://opentelemetry.io/docs/concepts/context-propagation/): W3C Trace Context `traceparent`; baggage must not carry credentials or PII.

## Security

- [OWASP Microservices Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html): mTLS or tokens between services, authorization in every service not only at the edge, verifiable user identity, central logging with correlation IDs.

## Resilience

- The `resiliency` skill in this repo (`../../resiliency/SKILL.md`) covers timeouts, retries with backoff and jitter, and request limits; this skill uses it rather than repeating it.
