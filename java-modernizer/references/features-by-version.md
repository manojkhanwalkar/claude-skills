# Java features by release

Only **final** features are listed for use. Preview and incubator features are listed separately and are never introduced. LTS releases: 8, 11, 17, 21, 25.

For a release newer than 26, read `https://openjdk.org/projects/jdk/<N>/` (the JEP list) and Oracle's "Significant Changes in JDK <N>" migration page before relying on this table, and add what you find to the report.

## Final features, by the release they arrived in

| JDK | Language | Library and platform |
|---|---|---|
| 7 | try-with-resources, diamond `<>`, multi-catch, `switch` on `String`, binary literals and `_` in numbers | `java.nio.file` (`Files`, `Path`), `Objects` (`equals`, `hash`, `requireNonNull`), `StandardCharsets` |
| 8 | Lambdas, method references, default and static interface methods | Streams, `Optional`, `java.time`, `CompletableFuture`, `Map.computeIfAbsent`/`merge`/`getOrDefault`/`forEach`, `StringJoiner`, `String.join`, `Base64`, `LongAdder` |
| 9 | Private interface methods, try-with-resources on effectively final variables, `@SafeVarargs` on private methods | `List.of`, `Set.of`, `Map.of`/`ofEntries`, `Optional.ifPresentOrElse`/`or`/`stream`, `Stream.takeWhile`/`dropWhile`/`ofNullable`/`iterate` with predicate, `InputStream.transferTo`/`readAllBytes`, `Objects.requireNonNullElse`, `ProcessHandle`, `VarHandle` |
| 10 | `var` for locals | `List.copyOf`/`Set.copyOf`/`Map.copyOf`, `Collectors.toUnmodifiableList`, `Optional.orElseThrow()` |
| 11 | `var` in lambda parameters | `String.isBlank`/`strip`/`lines`/`repeat`, `Files.readString`/`writeString`, `java.net.http.HttpClient`, `Predicate.not`, `Collection.toArray(IntFunction)`, `Optional.isEmpty` |
| 12 | | `Collectors.teeing`, `String.indent`/`transform`, `CompactNumberFormat` |
| 14 | Switch expressions (`->`, `yield`) | Helpful `NullPointerException` messages |
| 15 | Text blocks | `String.formatted`, `String.stripIndent` |
| 16 | Records, pattern matching for `instanceof` | `Stream.toList()` (unmodifiable), `Stream.mapMulti` |
| 17 | Sealed classes and interfaces | `RandomGenerator`, `HexFormat`; JDK internals strongly encapsulated (JEP 403) |
| 18 | | UTF-8 is the default charset (JEP 400); `@snippet` in Javadoc; simple web server (`jwebserver`) |
| 19 | | `Locale.of`, `HashMap.newHashMap(n)`, `Thread.threadId()` |
| 21 | Record patterns, pattern matching for `switch` | Virtual threads (JEP 444), sequenced collections (`getFirst`, `getLast`, `reversed`, `addFirst`), `Math.clamp`, `StringBuilder.repeat`, `String.splitWithDelimiters`; generational ZGC |
| 22 | Unnamed variables and patterns `_` (JEP 456) | Foreign Function and Memory API (JEP 454); multi-file source launch |
| 23 | Markdown doc comments `///` (JEP 467) | Generational mode is ZGC's default |
| 24 | | Stream gatherers (JEP 485), Class-File API (JEP 484), `synchronized` no longer pins virtual threads (JEP 491), ML-KEM and ML-DSA (JEPs 496, 497) |
| 25 | Module import declarations (JEP 511), compact source files and instance `main` (JEP 512), flexible constructor bodies: statements before `super(…)` (JEP 513) | Scoped values (JEP 506), Key Derivation Function API (JEP 510), compact object headers as a product option (JEP 519), AOT ergonomics and method profiling (JEPs 514, 515) |
| 26 | | HTTP/3 in `HttpClient` (JEP 517), AOT object caching with any GC (JEP 516) |

## Preview or incubator (never introduced; flag existing use)

As of JDK 26: structured concurrency (`StructuredTaskScope`, sixth preview, JEP 525), lazy (formerly stable) values, primitive types in patterns, PEM encodings, the Vector API (incubator). Code using them needs `--enable-preview` and breaks between releases; list it with the release it was written for.

## Deprecated and removed: what breaks on upgrade

| API or behaviour | Status | Replacement |
|---|---|---|
| `new Integer(…)`, `new Long(…)`, other boxed constructors | Deprecated for removal (16) | `Integer.valueOf`, autoboxing |
| `Object.finalize`, `Runtime.runFinalization` | Deprecated for removal (18, JEP 421) | try-with-resources, `Cleaner` |
| `Thread.stop`, `suspend`, `resume`; `ThreadGroup` destroy and daemon | `stop` throws `UnsupportedOperationException` (20) | Interruption and cooperative cancellation |
| `Thread.getId` | Deprecated (19) | `Thread.threadId()` |
| `new Locale(…)` | Deprecated (19) | `Locale.of`, `Locale.forLanguageTag` |
| `new URL(String)` and other `URL` constructors | Deprecated (20) | `URI.create(s).toURL()`; never `URL.equals`/`hashCode` (they resolve DNS) |
| `SecurityManager`, `System.setSecurityManager`, `AccessController` | Permanently disabled (24, JEP 486) | Remove; container and OS isolation |
| `sun.misc.Unsafe` memory access | Deprecated for removal (23, JEP 471), warns at run time (24, JEP 498) | `VarHandle`, FFM `MemorySegment` |
| Deep reflection that mutates `final` fields | Warns (26, JEP 500), to be denied later | Constructors, builders; serialization frameworks' own support |
| Applet API | Removed (26, JEP 504) | none |
| Nashorn JavaScript engine | Removed (15) | GraalJS dependency |
| `javax.xml.bind`, `javax.activation`, `javax.annotation`, CORBA, `javax.xml.ws` (Java EE modules) | Removed (11) | Jakarta dependencies (a framework migration: Needs a decision) |
| Access to JDK internals via `--illegal-access` | Removed (17) | Public APIs; `--add-opens` only as a stop-gap |
| Default charset depends on the platform | UTF-8 by default (18) | Pass a `Charset` wherever bytes and text meet; check `file.encoding` assumptions |
| Dynamic agent loading | Warns (21, JEP 451) | `-XX:+EnableDynamicAgentLoading` or a `-javaagent` at start |
| 32-bit x86 port | Removed (25) | 64-bit images |
