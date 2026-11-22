# Sources

Pages read on 2026-11-21 when this skill was written. Book contents are cited through the pages that describe them.

## Gang of Four and the pattern catalogue

- [Wikipedia, Design Patterns (book)](https://en.wikipedia.org/wiki/Design_Patterns): the book's structure, its two principles (program to an interface; favour composition over inheritance) and the 23 patterns in three groups.
- [Refactoring.Guru, Design patterns catalogue](https://refactoring.guru/design-patterns/catalog): the 23 patterns grouped as creational, structural and behavioral.
- [Refactoring.Guru, Strategy](https://refactoring.guru/design-patterns/strategy): replaces a conditional choosing algorithm variants; overkill for a couple of stable algorithms; lambdas can replace it.
- [Refactoring.Guru, State](https://refactoring.guru/design-patterns/state): for many states with conditionals on fields; overkill for a few rarely changing states.
- [Refactoring.Guru, Template Method](https://refactoring.guru/design-patterns/template-method): a skeleton with overridable steps; LSP risk; inheritance versus Strategy's composition.
- [Refactoring.Guru, Visitor](https://refactoring.guru/design-patterns/visitor): operations over a class hierarchy; every visitor changes when the hierarchy changes.
- [Refactoring.Guru, Singleton](https://refactoring.guru/design-patterns/singleton): one instance with global access; violates SRP, hides design problems, hard to test.
- [Refactoring.Guru, Builder](https://refactoring.guru/design-patterns/builder): cures the telescoping constructor; adds classes, worth it only for complex products.
- [Refactoring.Guru, Decorator](https://refactoring.guru/design-patterns/decorator): wraps an object to add behaviour at runtime; its relation to Proxy.
- [Refactoring.Guru, Observer](https://refactoring.guru/design-patterns/observer): a subscription mechanism for an open set of subscribers; no ordering guarantee.
- [Refactoring.Guru, Facade](https://refactoring.guru/design-patterns/facade): a simple interface to a subsystem; can grow into a god object.
- [Refactoring.Guru, Adapter](https://refactoring.guru/design-patterns/adapter): makes an incompatible interface usable; sometimes simpler to change the service class.
- [Refactoring.Guru, Criticism of patterns](https://refactoring.guru/design-patterns/criticism): patterns as workarounds for weak languages, applied rigidly, or used without need.

## Refactoring and code smells

- [Martin Fowler, Refactoring catalog](https://refactoring.com/catalog/): the 66 refactorings of the second edition, including Replace Conditional with Polymorphism, Replace Primitive with Object and Introduce Special Case.
- [Martin Fowler, Replace Conditional with Polymorphism](https://refactoring.com/catalog/replaceConditionalWithPolymorphism.html): moving each branch of a type switch into its own class.
- [Martin Fowler, Definition of Refactoring](https://martinfowler.com/bliki/DefinitionOfRefactoring.html): a change to internal structure that keeps observable behaviour.
- [Refactoring.Guru, Code smells](https://refactoring.guru/refactoring/smells): bloaters, OO abusers, change preventers, dispensables and couplers.
- [Refactoring.Guru, Switch Statements](https://refactoring.guru/smells/switch-statements): treatments, and when to ignore (simple actions, factory selection).
- [Refactoring.Guru, Primitive Obsession](https://refactoring.guru/smells/primitive-obsession): replace data values and type codes with objects.
- [Refactoring.Guru, Feature Envy](https://refactoring.guru/smells/feature-envy): move the method to its data, except deliberate Strategy or Visitor separation.
- [Refactoring.Guru, Speculative Generality](https://refactoring.guru/smells/speculative-generality): collapse, inline and remove unused abstractions; check frameworks and tests first.
- [Wikipedia, Characterization test](https://en.wikipedia.org/wiki/Characterization_test): Feathers's tests that pin current behaviour before refactoring legacy code.

## Refactoring to Patterns (Kerievsky)

- [Industrial Logic, Refactoring to Patterns catalog](https://www.industriallogic.com/xp/refactoring/catalog.html): the book's 27 refactorings, such as Replace Conditional Logic with Strategy and Replace State-Altering Conditionals with State.
- [Joshua Kerievsky, Refactoring to Patterns, draft preface and introduction](https://courses.cs.duke.edu/compsci307d/fall21/readings/kerievsky_preface.pdf): over-engineering and under-engineering, and refactoring to patterns instead of up-front pattern design.

## Enterprise patterns (Fowler, PoEAA)

- [Martin Fowler, Catalog of Patterns of Enterprise Application Architecture](https://martinfowler.com/eaaCatalog/): the PoEAA patterns by category with one-line definitions.
- [Martin Fowler, Repository](https://martinfowler.com/eaaCatalog/repository.html): collection-like access to domain objects over a data mapper.
- [Randy Stafford, Service Layer](https://martinfowler.com/eaaCatalog/serviceLayer.html): the application's boundary of operations, coordinating transactions.
- [Martin Fowler, Unit of Work](https://martinfowler.com/eaaCatalog/unitOfWork.html): tracks a business transaction's changes and writes them out.
- [Martin Fowler, Special Case](https://martinfowler.com/eaaCatalog/specialCase.html): a subclass for special values instead of null checks.
- [Martin Fowler, Gateway](https://martinfowler.com/articles/gateway-pattern.html): wrapping an external system in your own vocabulary; versus Adapter, Facade, Mediator and ACL; testing through it.

## Domain-Driven Design (Evans)

- [Domain Language, DDD Reference](https://www.domainlanguage.com/ddd/reference/): Evans's summary of every pattern and definition in his book.
- [Microsoft, Designing a microservice domain model](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-domain-model): entities, value objects, aggregates and roots; rich versus anemic models, and when anemic CRUD is fine.
- [Martin Fowler, DDD Aggregate](https://martinfowler.com/bliki/DDD_Aggregate.html): a cluster treated as one unit through its root; transactions don't cross aggregates.
- [Martin Fowler, Value Object](https://martinfowler.com/bliki/ValueObject.html): equality by value, immutability, aliasing bugs, replacing primitives.
- [Martin Fowler, Anemic Domain Model](https://martinfowler.com/bliki/AnemicDomainModel.html): data-only domain objects with logic in services; keep the service layer thin.
- [Microsoft, Anti-Corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer): translation between subsystems with different semantics; keep business rules out of it.

## Principles

- [Robert C. Martin, Solid Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html): his current one-line statements of SRP, OCP, LSP, ISP and DIP.
- [Wikipedia, GRASP](https://en.wikipedia.org/wiki/GRASP_(object-oriented_design)): Larman's nine responsibility-assignment principles.
- [Effective Java, 3rd edition, item list](https://gist.github.com/ff230b8ad708ebde9eec88bf11a7fcbb): Bloch's 90 item titles, used for the item numbers cited.
- [Head First Design Patterns, notes on the OO principles](https://physicsworks2.com/coding/2017/04/02/head-first-design.html): encapsulate what varies, program to interfaces, favour composition, loose coupling, and the rest of the book's principles.
- [Head First Design Patterns, study repository](https://github.com/josephjwilson/head-first-design-patterns): the same principles as listed in the book's OO toolbox.

## Modern Java and Spring

- [Brian Goetz, Data Oriented Programming in Java](https://www.infoq.com/articles/data-oriented-programming-java/): records, sealed classes and pattern matching; more concise than visitors; OO for boundaries.
- [Nicolai Parlog, Java 21 pattern matching](https://nipafx.dev/java-21-pattern-matching/): sealed types, record patterns, exhaustive switches, avoiding `default`; pattern matching versus methods on types.
- [Oracle, ServiceLoader (Java 21)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/ServiceLoader.html): provider loading in place of hand-written plugin factories.
- [Oracle, Optional (Java 21)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Optional.html): intended as a return type for "no result"; never null itself.
- [Spring, Dependency injection](https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html): constructor injection for required dependencies; many constructor arguments signal too many responsibilities.
- [Spring, Proxying mechanisms](https://docs.spring.io/spring-framework/reference/core/aop/proxying.html): JDK and CGLIB proxies; self-invocation bypasses advice.
- [Spring, Additional capabilities of the ApplicationContext](https://docs.spring.io/spring-framework/reference/core/beans/context-introduction.html): application events as the Observer pattern; synchronous by default, in the publisher's transaction.

## Anti-patterns and over-engineering

- [Martin Fowler, Yagni](https://martinfowler.com/bliki/Yagni.html): the build, delay, carry and repair costs of presumptive features; YAGNI needs malleable code.
- [Martin Fowler, Is Design Dead?](https://martinfowler.com/articles/designDead.html): patterns are often over-used; evolve into them from a simple design; Beck's simple design rules.
- [Wikipedia, God object](https://en.wikipedia.org/wiki/God_object): symptoms and splitting by responsibility.
- [Mark Seemann, Service Locator is an Anti-Pattern](https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/): hidden dependencies and runtime failures; constructor injection instead.
- [Martin Fowler, Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html): constructor versus setter injection, service locator versus injection, separating configuration from use.
