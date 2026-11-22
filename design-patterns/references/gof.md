# Gang of Four quick reference, with modern Java

*Design Patterns* (Gamma, Helm, Johnson, Vlissides, 1994) opens with two chapters on the strengths and pitfalls of object-oriented design, then catalogues 23 patterns in three groups: creational (5), structural (7) and behavioral (11). Its two governing principles: **program to an interface, not an implementation**, and **favour object composition over class inheritance**.

Many patterns exist to supply something a language lacked. In Java 21+ with Spring, several are now a language feature or a framework service: use those, and hand-write the pattern only when they don't fit. The "Overuse sign" column is what to flag under `anti-patterns.md`.

## Creational

| Pattern | Intent | Use when | Modern Java / Spring | Overuse sign |
|---|---|---|---|---|
| Abstract Factory | Create families of related objects without naming concrete classes | Several products must vary together (a UI theme, a cloud provider's set of clients) | A configuration class that defines the family's beans; a `@Profile` or `@ConditionalOnProperty` per family | One family, or products that never vary together |
| Builder | Construct a complex object step by step | Many optional parts, or several representations from one process | A record for all-required data; static factories; a builder only for many optional fields (Effective Java item 2) | A builder for a class with two or three required fields |
| Factory Method | Let subclasses or a method decide which class to instantiate | Creation varies by type or configuration and callers shouldn't know the concrete class | A static factory (item 1), `Supplier<T>`, an injected factory; `ServiceLoader` for plugins | A factory that only ever builds one class |
| Prototype | Create objects by copying a prototype | Creation is expensive and copies differ slightly | Records with `with`-style copy methods; copy constructors or static copy factories (item 13: override `clone` judiciously) | Rare in modern Java; `clone()` use is itself a smell |
| Singleton | One instance with a global access point | Exactly one instance is a domain fact | A Spring bean (singleton scope by default) injected where needed; an enum singleton (item 3) outside DI | Hand-written `getInstance()` in a DI application; hides dependencies and blocks tests |

## Structural

| Pattern | Intent | Use when | Modern Java / Spring | Overuse sign |
|---|---|---|---|---|
| Adapter | Let incompatible interfaces work together | Reusing a class or SDK whose interface doesn't match yours | A class implementing your interface over the SDK; a Gateway (PoEAA) when you design the interface | Adapting your own code that you could just change |
| Bridge | Separate an abstraction from its implementation so both vary | Two independent dimensions of variation (shape × renderer) | Composition: an interface field injected by DI | Only one dimension varies |
| Composite | Treat individual objects and groups uniformly | Tree structures (rules made of rules, menus, expressions) | A sealed interface with a leaf record and a group record holding `List<Node>` | A flat list dressed as a tree |
| Decorator | Add behaviour to an object by wrapping it | Optional, stackable additions (caching, metrics, retries) around an interface | Wrapper implementing the same interface; Spring AOP, interceptors and annotations (`@Transactional`, `@Cacheable`, `@Retryable`) | A decorator applied once, always, that could be the class itself |
| Facade | A simple interface to a complex subsystem | A module needs one entry point; callers reach into internals | A service class per module with package-private internals; PoEAA Service Layer | A facade that grows to wrap the whole app (god object) |
| Flyweight | Share fine-grained objects to save memory | Very many similar objects with shared intrinsic state | Interned values, cached value objects (`Integer.valueOf`, enum constants) | Without a measured memory problem |
| Proxy | Control access to an object through a stand-in | Lazy loading, access control, remote calls, caching | Spring AOP and JDK dynamic proxies; JPA lazy proxies; HTTP interface clients (`@HttpExchange`) | Hand-written proxies where the framework provides one |

## Behavioral

| Pattern | Intent | Use when | Modern Java / Spring | Overuse sign |
|---|---|---|---|---|
| Chain of Responsibility | Pass a request along handlers until one handles it | A pipeline of independent checks or handlers | Servlet filters, Spring Security filter chain, a `List<Handler>` injected in `@Order` | A chain of one or two fixed steps |
| Command | Encapsulate a request as an object | Queueing, undo, logging, retrying or scheduling operations | A record per command plus a handler; a lambda (`Runnable`, `Callable`) when no data or undo is needed | Command classes that are just method calls |
| Interpreter | Represent and evaluate a small language's grammar | A simple, stable DSL (rules, filters) | Sealed interface of records (the AST) plus a pattern-matching `switch` to evaluate | A real language; use a parser generator |
| Iterator | Traverse a collection without exposing its structure | Custom collections | `Iterable`, `Stream`, `Spliterator` | Hand-written iterators over standard collections |
| Mediator | Centralise communication among objects | Many objects talking to many others | An orchestrating service; application events | A mediator that becomes a god object |
| Memento | Capture and restore an object's state | Undo, snapshots, rollback | Immutable records are their own mementos | Mutable objects copied by hand |
| Observer | Notify dependents of changes | Fan-out to an open set of interested parties | `ApplicationEventPublisher` and `@EventListener` / `@TransactionalEventListener`; reactive streams; an outbox across services | One listener that always runs; then call it directly |
| State | Change behaviour when internal state changes | Many states, behaviour differs per state, transitions change often | An enum with transition methods; a sealed interface of state records | Two or three states with one transition |
| Strategy | Interchangeable algorithms | A conditional choosing between variants of one algorithm; algorithms vary at runtime | A functional interface; lambdas or method references (items 42–44); beans selected from a `Map<String, Strategy>` | One strategy, or variants that never change |
| Template Method | A fixed skeleton with overridable steps | Near-identical algorithms differing in steps | Composition: a method taking the steps as functions (item 18); `JdbcTemplate`-style callbacks | Deep inheritance for one varying line |
| Visitor | Add operations to a structure without changing its classes | Many operations over a stable hierarchy you can't change | A sealed hierarchy and an exhaustive pattern-matching `switch` with record patterns (no `accept` methods needed) | Visitor over a hierarchy you own and can seal |

## Polymorphism or pattern matching?

From Brian Goetz on data-oriented programming and the Java 21 pattern-matching guides:

- An operation that is **part of the type's contract** (its domain behaviour, used by the public API) → a method on the type.
- An operation that **doesn't belong on the type** (formatting, reporting, mapping to another model), or a **closed set of data variants** → sealed interface plus records plus exhaustive `switch`. Avoid `default` in such switches; it swallows new variants.
- OO is at its best defending boundaries (versioning, security, maintenance); data-oriented code suits ad-hoc data passing through a service. Mixing them by granularity is normal.

## Enterprise and DDD patterns used in findings

| Pattern | Source | One line | Spring / Java form |
|---|---|---|---|
| Repository | PoEAA, DDD | Collection-like access to aggregates; queries live here | Spring Data repository per aggregate root |
| Service Layer | PoEAA | The application's operations; coordinates transactions, stays thin | `@Service` with `@Transactional` methods per use case |
| Gateway | PoEAA | Wraps an external system behind an interface in your own vocabulary | An interface plus an HTTP-client implementation; stub it in tests |
| Data Mapper | PoEAA | Moves data between objects and the database, each unaware of the other | JPA/Hibernate, jOOQ mappers |
| Unit of Work | PoEAA | Tracks changes in a business transaction and writes them once | JPA persistence context within `@Transactional` |
| Special Case | PoEAA | A subclass with the behaviour for a special value, instead of `null` | A Null Object implementing the interface; `Optional` for returns |
| Value Object | PoEAA, DDD | Small immutable object equal by value | A record with a validating compact constructor; `@Embeddable` |
| Entity | DDD | Defined by identity; carries behaviour and guards its invariants | JPA `@Entity` with intention-revealing methods, no public setters |
| Aggregate | DDD | A consistency boundary changed through its root; one per transaction | Root entity owns children; other aggregates referenced by ID |
| Domain service | DDD | Domain logic that belongs to no single entity | A stateless `@Service` in the domain package |
| Factory | DDD | Creates complex aggregates in a valid state | A static factory on the root, or a factory class |
| Domain event | DDD | Something that happened in the domain, published for others | A record published via `ApplicationEventPublisher` or an outbox |
| Anti-corruption layer | DDD | Translates between two models with different meanings | A gateway plus translators at the boundary; no business rules inside |

## Principles behind the patterns

- **SOLID** (Robert Martin): SRP, gather what changes for the same reasons; OCP, extend without modifying; LSP, an implementation must not confuse users of its interface; ISP, keep interfaces small; DIP, depend in the direction of abstraction.
- **GRASP** (Larman): Information Expert, Creator, Controller, Indirection, Low Coupling, High Cohesion, Polymorphism, Protected Variations, Pure Fabrication.
- **Head First Design Patterns**: encapsulate what varies; program to interfaces; favour composition over inheritance; strive for loosely coupled designs; open for extension, closed for modification; depend on abstractions; least knowledge; the Hollywood principle; one reason to change.
- **Effective Java** (Bloch, 3rd ed.): items 1 (static factories), 2 (builders), 3 (singletons via enum), 5 (dependency injection), 15 (minimise accessibility), 17 (minimise mutability), 18 (composition over inheritance), 20 (interfaces over abstract classes), 23 (class hierarchies over tagged classes), 34 (enums over int constants), 42–44 (lambdas, method references, standard functional interfaces), 54–55 (empty collections, optionals), 62 (avoid strings where other types fit), 64 (refer to objects by their interfaces).
