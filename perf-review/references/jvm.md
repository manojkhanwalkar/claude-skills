# JVM and Spring Boot

Measure first (`measurement.md`); the JIT removes many costs that look expensive in source, and adds some that don't.

## GC and heap

- Let the JVM choose first; G1 is the default on most hardware. Choose G1 or ZGC when response time matters more than throughput; ZGC keeps pauses under a millisecond, independent of heap size, at some throughput cost (`-XX:+UseZGC`; on JDK 21 add `-XX:+ZGenerational`; later JDKs make generational ZGC the default). Parallel GC for batch throughput when pauses of a second are acceptable.
- In containers, size the heap from the container limit (`-XX:MaxRAMPercentage`), leaving room for metaspace, thread stacks, direct buffers and the code cache. Heaps up to about 32 GB keep compressed oops; going just past it can cost memory.
- GC flags are deployment changes: report them under "Needs a decision" with a JFR or GC log showing the problem (pause times, allocation rate, heap after GC).
- **Allocation rate** is usually the lever, not GC flags: JFR's allocation events or async-profiler `-e alloc` show who allocates. Cut allocation in hot loops; leave the rest.

## Allocation and the JIT

- **Escape analysis**: HotSpot's C2 removes allocations of objects that don't escape a compiled method (scalar replacement) and elides locks on them. Small temporary objects in hot, inlined code are often free; don't hand-optimise them away without a benchmark. It does not help objects stored in fields, returned, or passed to non-inlined calls.
- **Boxing**: `List<Integer>`, `Map<Long, ...>` and `Stream<Integer>` in hot numeric loops allocate per element (outside the small `Integer` cache). Use primitives, `IntStream`, or primitive arrays where measured.
- **Strings**: `+` in a loop builds a new string each time (use `StringBuilder` sized if known); `String.format` is slow on hot paths; compile-time constant concatenation is free; `String.join` and `Collectors.joining` are fine.
- **Collections**: presize when the size is known (`new ArrayList<>(n)`, `HashMap.newHashMap(n)` on 19+); `ArrayList` over `LinkedList`; `HashSet` for membership over `List.contains`; `EnumMap` and `EnumSet` for enum keys; `List.copyOf` for immutable results.
- **Streams versus loops**: streams are fine almost everywhere; a plain loop wins only in very hot code over small collections, or where boxing appears. Don't rewrite streams without a JMH result. `parallelStream()` uses the shared common pool; avoid it on request paths.
- **Expensive objects to build once**: `ObjectMapper` (and reuse `ObjectReader`/`ObjectWriter`, thread-safe), `Pattern`, `DateTimeFormatter` (thread-safe; `SimpleDateFormat` is not), HTTP and AWS SDK clients (thread-safe, one pool each), `JAXBContext`, `Validator`, template engines. `MessageDigest`, `Cipher`, `Mac` and `Signature` are not thread-safe: create per use (the provider lookup is cheap after warm-up) or keep one per thread; never share one instance across threads.
- **Exceptions for control flow** on hot paths: building a stack trace is costly; use return values, or a preallocated exception without a stack trace only if measured.
- **Reflection** in hot loops (custom mappers): cache `Method` and `Field` lookups, or use `MethodHandle`.

## Concurrency

- **Virtual threads** (JDK 21+): for many concurrent tasks that mostly wait on I/O; they raise throughput, not single-request speed. Never pool them; use `Executors.newVirtualThreadPerTaskExecutor()` and limit concurrency with a `Semaphore` (a connection pool already acts as one). Not for long CPU-bound work. Don't cache expensive objects in `ThreadLocal`s with millions of threads.
- **Pinning**: on JDK 21 to 23, blocking inside `synchronized` or a native frame pins the carrier thread; replace long-held `synchronized` around I/O with `ReentrantLock`, and find pinning with `-Djdk.tracePinnedThreads=full` or the JFR event `jdk.VirtualThreadPinned` (20 ms threshold, on by default). From JDK 24 (JEP 491) `synchronized` no longer pins; native methods and foreign functions still do.
- **Fan-out**: independent calls on one request run in parallel with a bound and a deadline. For example, a login that also fetches offers, alerts and subscriptions submits the three to a `newVirtualThreadPerTaskExecutor()` in a try-with-resources block, so it waits for the slowest, not the sum, and each optional extra fails soft (logged, returned empty). Check new fan-outs for the same: bounded, a timeout per call (`resiliency`), failures isolated, and no shared mutable state.
- **Thread pools**: CPU-bound work sized near the core count; I/O-bound pools sized by Little's Law; always a bounded queue and a rejection policy. `Executors.newCachedThreadPool()` is unbounded threads; `newFixedThreadPool` is an unbounded queue.
- **Locks**: narrow them; don't hold one across I/O; prefer `ConcurrentHashMap.computeIfAbsent` (keep the function fast and non-recursive), `LongAdder` for hot counters, immutable snapshots for read-mostly data.

## Connection pools

- JDBC (HikariCP): smaller than people expect. Start from `connections = (cores × 2) + effective spindles` and test under load; a big pool adds contention, not throughput. Deadlock floor when a thread holds several connections: `threads × (connections per thread − 1) + 1`.
- HTTP: one `HttpClient`, `RestClient`/`WebClient` or SDK client per target, shared; connection pools aren't shared between `HttpClient` instances, so a client per call means a new TCP and TLS handshake per call. Fully read or close response streams, or the connection can't be reused and the pool drains.
- AWS SDK v2: clients are thread-safe; build once, close on shutdown; set `apiCallAttemptTimeout` and `apiCallTimeout` (no default) — timeouts themselves are `resiliency`'s check.

## Spring Boot

- **Start-up**: `spring.main.lazy-initialization=true` defers bean creation (faster start; misconfiguration surfaces later; first requests slower). Exclude unused auto-configurations. CDS, AOT and native images are deployment decisions.
- **Jackson**: inject the Boot-managed `ObjectMapper`; never `new ObjectMapper()` per call. Read from `byte[]` or `InputStream`, not a `String`; write to the response stream; `writeValueAsString` is the least efficient path. Serialise a response once. Afterburner or Blackbird modules only with a measured gain.
- **Logging**: SLF4J parameterised messages (`log.debug("x {}", obj)`) skip formatting and `toString()` when the level is off (at least 30× faster than concatenation for disabled statements); guard with `isDebugEnabled()` only when computing an argument is itself expensive. More than two arguments allocate a varargs array. No per-item logging in hot loops; log a summary. Synchronous file or console appenders under load can block request threads; async appenders are a deployment choice.
- **N+1 across services**: a controller that calls a client per item; a `@Transactional` method that lazy-loads in a loop (see `data-access.md`). Request-scoped memoisation removes repeats inside one request.
- **Filters and interceptors** run on every request: no remote calls, no per-request `Pattern` compiles or client builds there.
- **`@Cacheable`** with the default `ConcurrentMapCacheManager` is unbounded; use Caffeine with `maximumSize` and an expiry.

## Caching (any stack)

- Cache only what is read far more than written, expensive to compute, and tolerant of the staleness you choose. Personal data cached across users is a security finding, not an optimisation.
- Bounded always: Caffeine `maximumSize` or `maximumWeight` plus `expireAfterWrite`; avoid `softValues` (unpredictable). `refreshAfterWrite` serves the old value while one reload runs, and a failed refresh keeps the old value.
- Stampede: when a hot key expires, many callers recompute it at once. Use a loading cache (one load per key in flight), refresh-ahead, or probabilistic early expiry; for distributed caches, a per-key lock or a stale-while-revalidate.
- Invalidation: say how entries become stale and who evicts them; multi-instance services need a shared cache or short TTLs.
