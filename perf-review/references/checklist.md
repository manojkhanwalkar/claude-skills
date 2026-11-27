# Performance checklist by area

For each area: what to grep for, the questions that confirm a finding, and when to leave it alone. Grep patterns are starting points; confirm each hit by reading the code and its hot path. The `--focus` names match the headings.

## Finding hot paths (all areas)

| Look for | Grep |
|---|---|
| HTTP entry points | `@RestController`, `@(Get\|Post\|Put\|Delete\|Patch\|Request)Mapping`, `RouterFunction`, `app\.(get\|post)\(`, `@app\.(get\|post)`, `router\.` |
| Code on every request | `implements Filter`, `OncePerRequestFilter`, `HandlerInterceptor`, `@Around`, Express `app.use(` |
| Messages and jobs | `@KafkaListener`, `@SqsListener`, `@JmsListener`, `@Scheduled`, `@EventListener`, cron |
| Agent and tool endpoints | `@Tool`, `@McpTool`, A2A handlers, tool registries |
| Loops over data | `for (`, `.forEach(`, `.stream()`, `.map(` over repository or client results |

Questions: how often does this run (per request, per item, per minute)? How large can the collection be (bounded by what)? What does the design doc say the load is?

## latency

| Sign | Confirm | Leave alone when |
|---|---|---|
| Two or more independent remote calls in sequence on one request | Neither needs the other's result | The calls are fast (under a few ms each) and the endpoint is cold |
| A remote or store call inside a loop | The loop size grows with data (accounts, items, users) | The loop is bounded to 2 or 3 by the domain |
| The same remote call made twice in one request | Same arguments, no change between them | — |
| Fan-out with no deadline | One slow dependency holds the whole response | The fan-out has a timeout per call (see `resiliency`) |
| Heavy work on the request thread that the user doesn't wait for (emails, audit export, analytics) | The response doesn't depend on it | It must be durable before responding (use an outbox, not fire-and-forget) |
| Synchronous calls to an LLM or slow provider on a request path with no streaming | The user waits for the full answer | — |

Tail latency: with fan-out to N services, the request is as slow as the slowest; at 100 leaves with 1-in-100 slow, 63% of requests are slow (Dean and Barroso). Look for hedging only where replicas exist and requests are idempotent.

## memory

| Sign | Confirm | Leave alone when |
|---|---|---|
| `static` `Map`, `List` or `Set` that is added to at run time | Nothing removes entries, or removal depends on a happy path | The keys are a small fixed set (enum, config) |
| A cache (`HashMap`, `ConcurrentHashMap`, `@Cacheable` with the default simple provider) with no size or expiry | Keys come from users or requests | Keys are bounded by config |
| `readAllBytes`, `Files.readAllLines`, `findAll()`, `toList()` on a full result set, `response.body()` as `String` for large bodies | Input size is user- or data-driven | Bounded and small (config files) |
| Large objects retained by long-lived ones: listeners never removed, `ThreadLocal` without `remove()`, sessions holding reports | A heap dump or code path shows retention | — |
| Queues (`LinkedBlockingQueue()` with no capacity, `Executors.newFixedThreadPool` whose queue is unbounded, Node arrays used as queues) | The producer can outrun the consumer | Producer is bounded by a semaphore or rate limit |
| String building in loops with `+` | Loop over data, not 3 fixed parts | Compile-time constant concatenation |
| Off-heap: direct `ByteBuffer`s, Netty buffers not released, memory-mapped files | Container memory limit vs heap plus off-heap | — |

High when growth is unbounded and can reach `OutOfMemoryError` or the container's limit under normal traffic.

## throughput

| Sign | Confirm | Leave alone when |
|---|---|---|
| `synchronized` method on a singleton bean, or a lock held across I/O | It is on a request path with concurrency | The lock guards a fast, in-memory update |
| A pool smaller than the concurrency it serves (DB, HTTP, thread) | Little's Law: in-flight = rate × time held | Pool is a deliberate limit (see `resiliency`) |
| Thread-per-request blocking code at high concurrency on platform threads | Threads mostly wait on I/O | Concurrency is low |
| Virtual threads pooled, or used for CPU-bound work | `Executors.newFixedThreadPool(n, Thread.ofVirtual().factory())` | — |
| Virtual threads pinned: blocking inside `synchronized` (JDK 21 to 23), a native call or a static initializer | JFR `jdk.VirtualThreadPinned` events, or the JDK version and the blocking call under the lock | JDK 24+ and the lock is a plain `synchronized` |
| CPU-heavy work (crypto with high cost factors, PDF, image, compression) on a request path | It runs per request rather than once | It is the point of the endpoint and bounded by a limit |
| `parallelStream()` on request paths | It shares the common ForkJoinPool with everything else | Measured gain on large data, off the request path |
| Contended `AtomicLong` counters | Very high update rate | Use `LongAdder` only if measured |

## startup

Only when start-up time matters (scale-to-zero, CLIs, tests, frequent deploys).

- Eager initialisation of heavy beans that most runs don't use: `spring.main.lazy-initialization=true` trades faster start for later failures and first-request latency; opt out per bean with `@Lazy(false)`.
- Classpath scanning of huge packages; auto-configurations not needed (`spring.autoconfigure.exclude`).
- Network calls at start-up (warming caches from remote services) without a timeout.
- Class Data Sharing or AOT (Spring Boot's CDS and AOT support, GraalVM native image) for real start-up needs; these are deployment changes, so "Needs a decision".

## io

| Sign | Confirm | Leave alone when |
|---|---|---|
| `HttpClient.newHttpClient()`, `new RestTemplate()`, `WebClient.create()`, `DynamoDbClient.create()`, `requests.get` without a `Session`, `new Agent` per call | Built inside a method that runs per request | Built once in a `@Bean` or a static field |
| Response streams not closed or not fully read (AWS `ResponseInputStream`, `ofInputStream()`) | The connection can't go back to the pool | — |
| Large text responses without compression | Response is JSON or HTML over about 1 KB and the client accepts gzip or br | Already-compressed content (images, video) |
| Large payloads: whole entities returned where the client uses a few fields | Response size × call rate | — |
| Whole files or bodies buffered before sending | Size is unbounded | Small, bounded |
| Timeouts missing on outbound calls | — | Report under `resiliency`; flag here only the thread or connection it holds |

## db

See `data-access.md` for SQL, JPA and DynamoDB. Signs: repository or client calls inside loops; `scan(`, `ScanRequest`, `findAll(`; `OFFSET`; `SELECT *`; queries with no `Limit` or page; `ConsistentRead(true)` where the read doesn't need it; `FilterExpression` doing a key's job.

## frontend

For UIs the project serves.

- Core Web Vitals at the 75th percentile: LCP within 2.5 s, INP 200 ms or less, CLS 0.1 or less. Lab tools can't measure INP; Total Blocking Time is the lab proxy.
- Bundle size: one large JS bundle, whole libraries imported for one function (`import _ from 'lodash'`), no code splitting by route.
- Caching: hashed static assets without `Cache-Control: max-age=31536000, immutable`; HTML with long `max-age` (use `no-cache` and an `ETag`); `Vary: User-Agent` killing cache hits.
- Compression: text assets served without gzip or br; `Vary: Accept-Encoding` missing when negotiated.
- Render-blocking scripts in `<head>` without `defer`; images without width and height (CLS) or not lazy-loaded below the fold.
- Accessibility fixes go through `ada-compatibility`; don't trade them for speed.
- Page-load work (images, fold-aware lazy loading, render-blocking and async code, Lighthouse runs and budgets) belongs to `ui-optimizer`; flag it here and point there.

## Python

- Profile: `python -m cProfile -s cumulative app.py` (on 3.15+ `profiling.tracing`; `cProfile` stays an alias); for a running process `py-spy record -o profile.svg --pid <pid>`, `py-spy top --pid <pid>` or, on 3.15+, the built-in sampler `profiling.sampling` (both need ptrace rights; `--cap-add SYS_PTRACE` in Docker).
- Signs: `requests.get` per call (use a `Session`); blocking calls inside `async def` (use the async client or `run_in_executor`); `list` membership in loops; string `+=` in loops; ORM lazy loads in loops (`select_related`, `prefetch_related`); `json.loads` of large bodies; module-level caches with no bound (`functools.lru_cache(maxsize=None)`).

## Node

- Profile: `node --prof app.js` then `node --prof-process isolate-*.log`; `node --cpu-prof`; `node --inspect` with Chrome DevTools. Clinic.js (Doctor, Flame, Bubbleprof, HeapProfiler) is no longer actively maintained and may give inaccurate results on new Node versions.
- Signs that block the event loop: `*Sync` APIs on servers (`fs.readFileSync`, `zlib.*Sync`, `crypto.pbkdf2Sync`, `child_process.execSync`); regexes with nested quantifiers (ReDoS); `JSON.parse` or `JSON.stringify` of large bodies (about 1 s per 50 MB); long CPU loops without yielding (partition with `setImmediate` or offload to `worker_threads`). Also a new `http.Agent` per request, and `await` in a `for` loop over independent calls (use `Promise.all` with a concurrency bound).
