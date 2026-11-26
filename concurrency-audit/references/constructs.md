# Choosing a construct

Simplest correct option first. Release numbers are the JDK in which the construct is final.

| Job | Use | Avoid |
|---|---|---|
| Count events from many threads | `LongAdder` (8) for write-heavy, rarely read; `AtomicLong` when read often or compared | `synchronized` counter; `volatile` with `++` |
| Map of lazily built values | `ConcurrentHashMap.computeIfAbsent` with a short, side-effect-free function; a bounded cache (Caffeine) when it must be bounded | `containsKey` then `put`; `synchronized` around a `HashMap` |
| Swap a whole configuration or snapshot | Immutable object in an `AtomicReference` or `volatile` field | Mutating a shared object in place |
| Hand work between threads | `BlockingQueue` (bounded `ArrayBlockingQueue`/`LinkedBlockingQueue(capacity)`) | `wait`/`notify`, busy loops |
| Wait for N things to finish | `CountDownLatch`, `ExecutorService.invokeAll`, `CompletableFuture.allOf` | `Thread.sleep` loops, `join` on raw threads |
| Limit concurrent calls to a downstream | `Semaphore` (with `tryAcquire(timeout)`) | A small fixed pool used only as a limiter (with virtual threads, pools of them are wrong) |
| Many blocking I/O tasks | `Executors.newVirtualThreadPerTaskExecutor()` in try-with-resources (21) | Large platform pools; pooling virtual threads |
| CPU-bound parallel work | A `ForkJoinPool` or fixed pool sized to cores; parallel streams on pure functions over large data | Virtual threads; parallel streams with I/O or shared mutation |
| Async composition | `CompletableFuture` with an explicit executor, `thenCompose` for dependent calls, `orTimeout`/`completeOnTimeout` (9), `exceptionally`/`handle` | `get()`/`join()` inside a stage; the common pool for I/O |
| Fan out and fail together | Virtual-thread executor plus `invokeAll` or `allOf` with cancellation on first failure; `StructuredTaskScope` only where the build already enables preview (still a preview through JDK 26) | Ad hoc threads with lost exceptions |
| Pass request context down a call tree | Scoped value (25) for immutable, bound-once values; method parameters | `InheritableThreadLocal` with pools; `ThreadLocal` without `remove` |
| Per-thread scratch objects | Per-use allocation (usually cheap); `ThreadLocal` only on platform-thread pools with `remove` | `ThreadLocal` caches on virtual threads (one per task, no reuse) |
| Mutual exclusion around a short critical section | `synchronized` (from JDK 24 it no longer pins virtual threads) | Locks held across I/O |
| Exclusion around blocking I/O on virtual threads, JDK 21-23 | `ReentrantLock` | `synchronized` (pins the carrier) |
| Read-mostly with rare writes | Immutable snapshot plus `AtomicReference`; `CopyOnWriteArrayList` for small listener lists; `StampedLock` only with measured contention | `ReadWriteLock` by default (often slower than a plain lock) |
| One-time initialisation | Eager `static final`; holder-class idiom; lazy constants are still a preview through 26 | Hand-rolled double-checked locking |
| Cross-instance exclusion | DB conditional update, unique constraint, optimistic version, a lease (ShedLock), DynamoDB conditional write | In-process locks |

## Virtual threads (JDK 21+)

- One virtual thread per task; never pool them. Limit downstream concurrency with a `Semaphore`.
- Good for blocking I/O; no gain for CPU-bound work, which should stay on a pool sized to cores.
- Pinning: on JDK 21-23 a virtual thread blocking inside `synchronized` or a native frame holds its carrier; from JDK 24 (JEP 491) `synchronized` no longer pins, native frames and class initializers still do. Detect with JFR `jdk.VirtualThreadPinned`.
- `ThreadLocal` works but costs memory per task; prefer scoped values (25) or parameters.
- Spring Boot: `spring.threads.virtual.enabled=true` (3.2+) runs request handling, `@Async` and schedulers on virtual threads; check the connection pool, since thousands of threads now compete for a pool of 10 connections (a `Semaphore` or the pool's timeout keeps it bounded).

## Executors

- Prefer injected, framework-managed executors with names, bounded queues and a rejection policy; shut them down on stop.
- `ExecutorService` is `AutoCloseable` from JDK 19; `close()` waits for submitted tasks.
- Size platform pools for I/O with Little's Law (threads = rate × latency); for CPU, about the core count.
