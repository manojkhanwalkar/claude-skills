# Smells to patterns

For each design smell: how to find it, what confirms it is worth fixing, the fix (principle, refactoring and pattern), the modern-Java form, and when to leave it alone. Refactoring names are from Fowler's *Refactoring* (2nd ed., refactoring.com) unless marked **[K]** for Kerievsky's *Refactoring to Patterns*. Examples use Java 21+ and Spring Boot.

## Contents

1. Type switches and if-chains
2. Duplicated algorithm skeletons
3. Telescoping constructors
4. Hard-wired dependencies
5. God class, feature envy, divergent change, shotgun surgery
6. Primitive obsession and data clumps
7. Anemic domain model
8. A leaking external API
9. Copied cross-cutting concerns
10. Hard-coded notification fan-out
11. Flag-soup state machines
12. Nulls
13. Mutable shared state
14. Unclear module boundaries
15. Missing test seams
16. Mechanics

## 1. Type switches and if-chains

- **Find:** `switch (x.getType())`, `if (type == ...) else if`, `instanceof` chains, the same enum switched on in several files. `grep -rn "switch (" --include=*.java` then group by the expression switched on.
- **Confirm:** the same switch appears in two or more places, or a new case has had to be added to several switches in one commit (`git log -p -S "case NEW_THING"`), or a `default` hides a missing case.
- **Fix:** OCP, GRASP Polymorphism, Effective Java item 23 ("Prefer class hierarchies to tagged classes"). Replace Conditional with Polymorphism; Replace Type Code with Subclasses; Replace Conditional Logic with Strategy **[K]**; Replace Conditional Dispatcher with Command **[K]**.
- **Modern Java:**
  - Behaviour that belongs to the type (part of its contract) → a method on each type: an enum with a method per constant, or an interface with one implementation per case.
  - Operations that don't belong on the type (formatting, mapping, reporting), or a closed set of data variants → a `sealed interface` of records and an exhaustive `switch` with record patterns and no `default`, so a new variant fails compilation at every switch.
  - The variant is a pluggable algorithm chosen at runtime → Strategy as a functional interface; small strategies are lambdas or method references (items 42–44).
- **Leave it:** one switch, in one place, over a small stable set; a switch that only picks which class to create (it is a factory); parsing at the system boundary.

```java
sealed interface BureauReport permits Equifax, Experian, TransUnion {}
record Equifax(String raw) implements BureauReport {}
// ... one switch, compiler-checked:
String bureauName(BureauReport r) {
  return switch (r) {
    case Equifax e -> "Equifax";
    case Experian x -> "Experian";
    case TransUnion t -> "TransUnion";
  };
}
```

## 2. Duplicated algorithm skeletons

- **Find:** two or more methods with the same steps in the same order and a few lines differing (fetch, validate, transform, save; open, loop, close).
- **Confirm:** the copies have drifted (a fix applied to one only), or a change to the flow touched all copies.
- **Fix:** Form Template Method **[K]** (Template Method: a final skeleton in a base class, abstract steps in subclasses); or, preferred in modern Java, composition: one method that takes the varying step as a parameter (`Function`, `Supplier`, a small interface). Effective Java item 18 favours composition over inheritance.
- **Leave it:** two short copies that may diverge for real reasons; the "rule of three" (extract on the third copy) is a fair default.

## 3. Telescoping constructors

- **Find:** several overloaded constructors calling each other; constructors with more than about four parameters, especially several of the same type; `null` or `0` passed as placeholders.
- **Fix:** Effective Java items 1 and 2. Replace Constructors with Creation Methods **[K]**, Chain Constructors **[K]**, Replace Constructor with Factory Function, Introduce Parameter Object.
- **Modern Java:** a record (with a compact constructor for validation) when all fields are required; a static factory with a descriptive name (`Money.of`, `Period.ofDays`) for alternative ways to build; a Builder only when there are many optional fields. A large constructor on a Spring bean is a different smell: too many collaborators (see 5).
- **Leave it:** framework-required constructors (JPA's no-args), generated code.

## 4. Hard-wired dependencies

- **Find:** `new SomeClient(...)`, `new RestTemplate()`, `HttpClient.newHttpClient()`, `Clock.systemUTC()`, `LocalDateTime.now()`, static utility calls with side effects, `getInstance()`, inside business logic.
- **Confirm:** the class can't be unit tested without the real dependency, or the implementation has to vary (per environment, per tenant, in tests).
- **Fix:** DIP; Effective Java item 5 ("Prefer dependency injection to hardwiring resources"); constructor injection (Spring's recommended style: dependencies final, non-null, fully initialised). A Factory (or a `Supplier<T>` / factory bean) only when the object must be created per call with runtime arguments. Move Creation Knowledge to Factory **[K]**.
- **Leave it:** value objects, collections and other pure types are fine to `new`.

## 5. God class, feature envy, divergent change, shotgun surgery

- **Find:** classes over about 500 lines or with more than about seven injected collaborators; a name ending in `Manager`, `Helper`, `Util`, `Processor` with unrelated methods; methods that mostly call getters of another object (feature envy); one file touched by many unrelated commits (divergent change); one change touching many files (shotgun surgery).
- **Fix:** SRP ("gather together the things that change for the same reasons"); GRASP Information Expert and High Cohesion. Extract Class, Move Function, Move Field, Combine Functions into Class; split a service by use case.
- **Leave it:** a cohesive class that is long because its domain is (a parser, a protocol); a Strategy or Visitor deliberately keeps behaviour apart from data, which looks like feature envy.

## 6. Primitive obsession and data clumps

- **Find:** money as `double`/`float`/`long cents` passed around unnamed; IDs, emails, SSNs, currency codes, ranges as `String` or `int`; the same three parameters travelling together; validation of the same string format in several places.
- **Confirm:** a mix-up is possible (two `String` IDs in one signature), or validation is duplicated or missing.
- **Fix:** Value Object (equality by value, immutable); Replace Primitive with Object; Replace Type Code with Class **[K]**; Introduce Parameter Object; Effective Java items 34 (enums instead of int constants), 60 (avoid `float`/`double` for exact answers) and 62 (avoid strings where other types fit).
- **Modern Java:** a record with a compact constructor that validates (`record CustomerId(String value) { CustomerId { Objects.requireNonNull(value); ... } }`), `BigDecimal` with an explicit scale and rounding for money, JPA `@Embeddable` or an `AttributeConverter` to persist it.
- **Severity:** money in floating point, or mixable IDs on a path that writes data, is Medium (bug risk).

## 7. Anemic domain model

- **Find:** entities that are only fields, getters and setters, and services that read those fields, decide, and set them back; invariants checked in several services.
- **Confirm:** the domain has real rules (not CRUD), and a rule is duplicated or was missed in one path.
- **Fix:** move the behaviour onto the entity or aggregate root (GRASP Information Expert); remove public setters in favour of intention-revealing methods (`subscription.cancel(at)`); let the aggregate root guard its invariants; keep the service layer thin (it coordinates transactions and calls, it doesn't decide).
- **Leave it:** CRUD services and plain data carriers (DTOs, events, read models) are meant to be data-only; data-oriented code with records and functions over them is a deliberate style, not anemia.

## 8. A leaking external API

- **Find:** a provider SDK's or another service's types (request and response classes, exceptions, status codes) imported outside one package; the same HTTP call, headers or error mapping written in several places.
- **Confirm:** changing or adding a provider would touch more than one package, or tests need the real provider.
- **Fix:** Gateway (PoEAA: an interface in your own vocabulary, translation only, no business rules); Adapter (Extract Adapter, Unify Interfaces with Adapter **[K]**) when an existing interface must be matched; an anti-corruption layer when the other side's model differs in meaning (a legacy system, another bounded context). One gateway interface per capability, one implementation per provider; Strategy (or a `Map<ProviderId, Gateway>` from DI) to pick a provider.
- **Leave it:** don't wrap platform facilities (the JDK, the framework itself) or a vocabulary everyone already knows.

## 9. Copied cross-cutting concerns

- **Find:** the same try/catch-log, timing, metrics, retry, authorisation check, audit write or transaction handling repeated across many methods.
- **Fix:** Decorator (Move Embellishment to Decorator **[K]**) or Proxy around an interface. In Spring: `@Transactional`, `@PreAuthorize`, Micrometer's `@Timed`/`@Observed`, Spring Retry or Resilience4j annotations, servlet filters and `HandlerInterceptor`s, or an aspect for a project-specific concern.
- **Watch:** Spring AOP is proxy-based: a call from one method to another on `this` skips the advice, and `final` or `private` methods can't be advised. A finding that relies on advice reaching a self-call is a correctness bug.

## 10. Hard-coded notification fan-out

- **Find:** one method that, after doing its job, calls the email sender, the audit log, the metrics, the cache evictor and the search indexer in turn; every new interested party edits that method.
- **Fix:** Observer (Replace Hard-Coded Notifications with Observer **[K]**); in Spring, publish a domain event with `ApplicationEventPublisher` and handle it with `@EventListener`, or `@TransactionalEventListener(phase = AFTER_COMMIT)` when the reaction must only follow a committed change. Across services, a transactional outbox.
- **Watch:** Spring events are synchronous by default and run in the publisher's transaction; an exception in a listener fails the publisher. Order is not guaranteed without `@Order`.
- **Leave it:** two reactions that must happen together and in order belong in one explicit method.

## 11. Flag-soup state machines

- **Find:** several booleans (`active`, `cancelled`, `pending`, `expired`) or a status string with checks like `if (active && !cancelled)` spread across methods; impossible combinations that the code still has to guard against.
- **Fix:** Replace State-Altering Conditionals with State **[K]**. Modern Java: one `enum Status` with the allowed transitions (`EnumSet` or a method per transition that throws on an illegal one), or a sealed interface of state records when states carry different data, so illegal states can't be represented.
- **Leave it:** two states with one transition; the State pattern is overkill for a machine that rarely changes.

## 12. Nulls

- **Find:** methods that return `null` for "not found" or "none", callers that check `!= null` in many places, `null` collections, `Optional` fields or parameters.
- **Fix:** Introduce Special Case (PoEAA Special Case, Introduce Null Object **[K]**) when the absent case has default behaviour that callers repeat; `Optional<T>` as a return type when "no result" must be handled (Effective Java item 55; never a `null` `Optional`, not for fields or parameters); empty collections instead of `null` (item 54).
- **Leave it:** a single null check at a boundary is fine.

## 13. Mutable shared state

- **Find:** setters on objects stored in caches, singletons or static fields; mutable fields in Spring singleton beans that change per request; collections returned without copying; `static` non-final fields.
- **Confirm:** the object is reachable from more than one thread or request, or a caller can change another's data through an alias.
- **Fix:** Effective Java item 17 (minimise mutability), item 50 (defensive copies); records with `List.copyOf` in the compact constructor; `final` fields; per-request state in locals or request-scoped objects. If sharing is required, a concurrency utility, not ad hoc `synchronized`.
- **Severity:** reachable from concurrent code → Medium at least; a demonstrated data mix-up between users → High (a correctness or security defect).

## 14. Unclear module boundaries

- **Find:** callers importing a subsystem's internals from many packages; cyclic package dependencies; everything `public`.
- **Fix:** Facade (one entry point per module or layer, PoEAA Service Layer for application operations), package-private internals (Effective Java item 15), Java modules or an ArchUnit test that enforces the boundary; Hide Delegate for message chains. Keep each facade focused; a facade that grows to touch everything has become a god object.
- **Leave it:** small codebases where one package is the module.

## 15. Missing test seams

- **Find:** a class whose unit test needs a database, network, file system, current time or random number; tests that use `Thread.sleep`; static calls to infrastructure; hand-written Singletons (`getInstance()`).
- **Fix:** an interface at the boundary plus constructor injection; inject `java.time.Clock` and a random source; Inline Singleton **[K]** and let the DI container manage the single instance. In legacy code without tests, add a characterisation test first, then introduce the seam by Branch by Abstraction.

## 16. Mechanics

Each fix is a sequence of small steps; run the changed module's tests after every step.

- **Replace Conditional with Polymorphism:** create the type hierarchy (or sealed interface and records) beside the switch; add a factory or the selection point; move one branch into its type; test; repeat per branch; replace the switch with the call; remove the type code if nothing else reads it.
- **Replace Conditional Logic with Strategy [K]:** extract the varying calculation into a method; create the strategy interface; move each branch into an implementation (or lambda); inject or select the strategy; delete the conditional.
- **Form Template Method [K]:** make the copies' steps identical in shape (Extract Function on each differing part); pull the identical method up to a common parent or into one function taking the differing part as a parameter; remove the copies.
- **Extract Class:** create the new class; move fields one at a time, then the methods that use them, testing after each; decide whether the old class keeps a reference or callers use the new one directly.
- **Replace Primitive with Object:** create the record with validation; change one field or parameter at a time to use it, converting at the edges; then move the behaviour that operated on the primitive into the record.
- **Introduce a seam (Branch by Abstraction):** extract an interface from the concrete dependency; change the consumer to depend on the interface, wired by constructor injection; test with a fake; only then add or swap an implementation.
- **Move Embellishment to Decorator [K]:** make the core class implement an interface; create a decorator implementing it that delegates and adds the concern; wire the decorator in configuration; remove the concern from the core class.
- **Replace Hard-Coded Notifications with Observer [K]:** define the event (a record); publish it where the calls were; move each call into a listener, one at a time, with a test that the listener runs; remove the direct calls.
- **Characterisation test first** (Feathers): when the code to change has no tests that would catch a mistake, record its current output for representative and edge inputs and assert it, before step one.
