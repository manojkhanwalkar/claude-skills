# Anti-patterns and overuse

A design review that only ever adds patterns makes code worse. Kerievsky's point in *Refactoring to Patterns* is that over-engineering (more flexibility or sophistication than needed, built on guesses about the future) and under-engineering (adding behaviour without improving design) are both failures, and the cure for both is to refactor **to, towards or away from** a pattern as the code's present needs show. Fowler: patterns are often over-used; evolve into a pattern from a simple implementation, and take it out again when it no longer pays.

## Signs of pattern overuse ("patternitis")

Flag these as Low (Medium if the indirection hides a defect or blocks a needed change), and recommend the simplification.

| Sign | Simplify by |
|---|---|
| An interface with exactly one implementation, no test double and no second implementation planned for a concrete reason | Inline the interface; depend on the class. Keep it only at a real seam: an external system, a module boundary, a test double |
| A factory that only ever creates one class | Inline the factory (call the constructor or a static factory) |
| A Strategy with one strategy, or strategies chosen by a constant | Inline the strategy; a `switch` or a plain method is clearer |
| An abstract base class with one subclass | Collapse Hierarchy |
| A Visitor over a hierarchy the project owns | Seal the hierarchy; exhaustive pattern-matching `switch` |
| Hand-written Singleton or Service Locator in an application with a DI container | Inline Singleton; constructor injection |
| A Builder for a class with two or three required fields | A record or constructor |
| Decorators or proxies that are always applied, in one fixed order | Fold the behaviour into the class, or use the framework's annotation |
| Layers that only forward calls (controller → service → manager → repository, each a one-line pass-through) | Remove Middle Man; skip the empty layer |
| Generic type parameters, hooks, plugin points or config switches nothing uses | Remove them (speculative generality) |
| Event-driven indirection for one listener that must always run, synchronously, in order | Call it directly |
| Patterns named in class names (`OrderStrategyFactoryImpl`) more than domain words | Rename by role in the domain; remove the layers the name lists |

## YAGNI and speculative generality

- YAGNI (Fowler): don't build capability for a presumed future need. Its costs are building it, delaying other work, carrying the complexity, and repairing it when the guess was wrong.
- YAGNI does not excuse poor structure: it relies on code that is easy to change (refactoring, tests). Making code easier to change is never speculative.
- Speculative generality (unused abstract classes, unused parameters, unnecessary delegation) is fixed by Collapse Hierarchy, Inline Class, Inline Function, Remove Parameter, and deleting dead fields. Check tests and framework users before removing something that looks unused.
- A useful test from Fowler: imagine the refactoring you would do when the need arrives. If adding the capability later costs about the same, don't add it now.

## God object

- **Signs:** one class holds most of the data and methods; other classes ask it for everything instead of talking to each other; any change risks unrelated behaviour.
- **Fix:** split by responsibility (SRP): Extract Class per concern, Move Function to the data's owner (Information Expert). A Facade that keeps growing is the usual way a god object is born; split it into focused facades.

## Anemic domain model

- **Signs:** domain-named classes with getters and setters only; services hold every rule and push results back into the objects.
- **Fix:** move rules onto entities and aggregate roots; keep the service layer thin (coordination, transactions).
- **Not anemic:** CRUD services, DTOs, events and read models are meant to be data. Data-oriented programming (records, sealed types, functions over them) is a valid style for data flowing through a service; judge by whether rules are duplicated or bypassed, not by the absence of methods.

## Service Locator

- **Signs:** classes call a registry, `ApplicationContext.getBean`, or a static `Locator.get(...)` to obtain their dependencies.
- **Why it hurts:** dependencies are hidden from the constructor, so a missing registration fails at runtime instead of compile time, and a class's needs can only be learned by reading its body.
- **Fix:** constructor injection; keep the container in the composition root (configuration classes). For objects created per call, inject a factory (`ObjectProvider<T>`, a `Supplier<T>` or an Abstract Factory).
- Fowler's framing: either can separate configuration from use, which is the principle that matters; prefer injection for components used across applications.

## Other anti-patterns to name

- **Golden hammer:** one pattern applied everywhere because the team knows it.
- **Inheritance for reuse:** subclassing to borrow code (a subclass that refuses or overrides most of its parent: refused bequest); replace with delegation (Replace Superclass with Delegate, Replace Subclass with Delegate).
- **Constant interface or `Constants` god class:** use enums or constants on the class that owns them (Effective Java item 22).
- **Tagged class:** a class with a `type` field and fields used only for some types; replace with a hierarchy or sealed records (item 23).
- **Boolean flag arguments:** Remove Flag Argument; one method per case.
- **Over-wrapping the platform:** gateways around the JDK or the framework add nothing.

## When the right answer is "no pattern"

- The code is small, readable and rarely changes.
- The variation is hypothetical.
- The language feature (a lambda, a record, an enum, a sealed `switch`) does the job without new types.
- The framework already provides it (DI, AOP, events, transactions).
- The pattern would add more types than the duplication it removes.
