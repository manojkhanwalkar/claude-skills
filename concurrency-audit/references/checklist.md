# Concurrency bug checklist (Java)

Each pattern: what to grep, how to confirm, and the fix. A hit is a finding only once you have written the interleaving and checked that it is reachable.

## Shared mutable state

| Pattern | Grep | Confirm | Fix |
|---|---|---|---|
| Mutable field on a singleton bean | Non-`final`, non-injected fields in `@Service`, `@Component`, `@RestController`, `@Repository`, servlets | Written outside the constructor or `@PostConstruct` | Local variable or parameter; request-scoped object; concurrent type |
| Mutable `static` | `static (?!final)` fields; `static final` `Map`/`List`/arrays that are mutated | Written after class init | Immutable constant; `ConcurrentHashMap`; an injected bean |
| Plain collection written by several threads | `new HashMap\|new ArrayList\|new HashSet` held in a field | Two writers, or a writer plus readers without a lock | `ConcurrentHashMap`, `CopyOnWriteArrayList` (read-mostly only), or confine it |
| `volatile` compound update | `volatile` plus `++`, `+=`, or read then write | Any two writers | `AtomicLong`, `LongAdder` (counters with rare reads), `AtomicReference.updateAndGet` |
| Non-thread-safe helper shared | `static (final )?(SimpleDateFormat\|DecimalFormat\|MessageDigest\|Cipher\|Mac\|Random)` | Used by more than one thread | `DateTimeFormatter` (immutable); per-use `MessageDigest`/`Cipher`; `ThreadLocalRandom` |
| `ObjectMapper` configured after first use | `mapper\.(configure\|registerModule\|setSerializationInclusion)` outside setup | Called on a shared instance at run time | Configure once at start; `ObjectReader`/`ObjectWriter` per variant |

## Check-then-act and atomicity

| Pattern | Grep | Fix |
|---|---|---|
| `containsKey`/`get` then `put` on a concurrent map | `containsKey\(` or `get\(.*\) == null` then `put\(` | `computeIfAbsent`, `putIfAbsent`, `merge`; keep the mapping function short, without I/O or other map updates (it holds the bin lock; recursive updates of the same map throw or deadlock) |
| Lazy init without a lock | `if \(\w+ == null\) \{?\s*\w+ = new` | Eager init; holder-class idiom; `volatile` plus double-checked locking only if needed |
| Double-checked locking without `volatile` | `synchronized` inside `if (x == null)` | Add `volatile`, or the holder idiom |
| Iterating a synchronized wrapper | `Collections\.synchronized` then a `for` loop | Hold the wrapper's lock while iterating, or use a concurrent collection |
| Two updates that must be one | Two collections or fields updated in sequence by different threads | One lock covering both, or one immutable snapshot swapped by `AtomicReference` |
| Read-modify-write on an external store | Repository `find` then `save` of a counter, balance, status | Conditional or atomic update (`UPDATE … WHERE version = ?`, DynamoDB `ConditionExpression`, `@Version`), unique constraints, `SELECT … FOR UPDATE` |
| Overlapping scheduled jobs across instances | `@Scheduled` on a multi-instance service | A lease or lock (ShedLock or a DB row), or idempotent work |

## Publication and visibility

| Pattern | Grep | Fix |
|---|---|---|
| `this` escapes a constructor | Constructors calling `addListener(this)`, `register(this)`, `new Thread(…).start()`, overridable methods | Factory method or a `start()` after construction |
| Stop flag not `volatile` | `boolean running` read in a loop on another thread | `volatile` or `AtomicBoolean`; better, interruption |
| Non-final fields of an object handed to another thread | Fields set after `executor.submit(obj)` | Set everything before handing over; make fields `final` |

## Liveness

| Pattern | Grep | Fix |
|---|---|---|
| Lock-order inversion | Nested `synchronized` or `lock()` on two monitors in different orders | One global order, or one lock; `tryLock` with a timeout as a last resort |
| Lock held across I/O or callbacks | `synchronized` blocks that call clients, repositories, listeners or `Future.get` | Copy state under the lock, call out after releasing |
| Pool self-deadlock | A task in a bounded pool `get()`s or `join()`s another task submitted to the same pool | Separate pools, or compose with `thenCompose` instead of blocking |
| `wait()` without a loop, `notify` with several conditions | `\.wait\(\)` not inside `while`; `\.notify\(\)` | Replace with `BlockingQueue`, `CountDownLatch`, `Condition`; at least `while (!cond) wait()` and `notifyAll` |
| Busy-wait | `while \(.*\) \{\s*\}` or `Thread\.sleep` polling loops | `BlockingQueue.take`, `CountDownLatch.await`, a scheduled executor |

## Interrupts, cancellation and lost errors

| Pattern | Grep | Fix |
|---|---|---|
| Swallowed `InterruptedException` | `catch \(InterruptedException` without `Thread.currentThread().interrupt()` or a rethrow | Restore the flag and stop the work, or propagate |
| Submitted task's exception lost | `executor\.submit\(` with the `Future` ignored; `execute` without an `UncaughtExceptionHandler`; `CompletableFuture` chains without `exceptionally`/`handle`/`whenComplete` | Keep and check the future, log in the task, or handle at the end of the chain |
| `Future.get()` with no timeout on a request path | `\.get\(\)` on futures; `\.join\(\)` | `get(timeout, unit)` per the `resiliency` checklist |

## Executors and threads

| Pattern | Grep | Fix |
|---|---|---|
| Executor per call | `Executors\.new` inside a method body | One shared executor bean, or try-with-resources (`ExecutorService` is `AutoCloseable` from 19) |
| Never shut down | Executor fields with no `shutdown`/`close` on shutdown | `@PreDestroy` or framework-managed `ThreadPoolTaskExecutor` |
| Unbounded queue or threads | `newFixedThreadPool`, `newSingleThreadExecutor` (unbounded `LinkedBlockingQueue`); `newCachedThreadPool` | `ThreadPoolExecutor` with a bounded queue and a rejection policy; virtual threads plus a `Semaphore` for blocking I/O |
| Blocking on the common pool | `parallelStream()`, `supplyAsync(` / `runAsync(` without an executor, around I/O | Explicit executor; for I/O, virtual threads |
| `ThreadLocal` not cleared in a pool | `ThreadLocal` `set` without `remove` in `finally` | `try { set } finally { remove() }`; scoped value (25+) |
| Raw `new Thread(` in application code | `new Thread\(` | An executor; `Thread.ofVirtual()` (21+) |

## Spring and frameworks

| Pattern | Fix |
|---|---|
| `@Async` or `@Transactional` method called from the same class | Call through the proxy (another bean), or restructure |
| `@Async` without a configured executor (Spring Boot defaults differ by version) | Name a bounded executor |
| Prototype or request-scoped state held in a singleton | `ObjectProvider` or a scoped proxy |
| WebFlux or Netty handler that blocks (`block()`, JDBC, `Thread.sleep`) | `subscribeOn(Schedulers.boundedElastic())`, or a non-blocking client |
| Kafka or JMS listener concurrency above 1 mutating shared state | Partition-keyed confinement, or a concurrent type |
| `spring.threads.virtual.enabled=true` with `synchronized` around I/O on JDK 21-23 | `ReentrantLock`, or JDK 24+ |
