# Sources

Pages read on 2026-11-22 when this skill was written, and rechecked on 2026-11-25 for the JDK 24 and 25 changes. Book contents are cited through the pages that describe them.

## Methodology

- [Brendan Gregg, The USE Method](https://www.brendangregg.com/usemethod.html): utilisation, saturation and errors for every resource; averages hide saturation bursts.
- [Brendan Gregg, Performance Analysis Methodology](https://www.brendangregg.com/methodology.html): the catalogue of methods (USE, RED, CPU profile, workload characterisation) and anti-methods, from *Systems Performance*.
- [Brendan Gregg, Flame Graphs](https://www.brendangregg.com/flamegraphs.html): how to read flame graphs; width is the share of samples, the x-axis is not time.
- [Grafana Labs, The RED Method](https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/): rate, errors and duration per service, and how RED complements USE.
- [Dean and Barroso, The Tail at Scale (CACM, 2013)](https://www.barroso.org/publications/TheTailAtScale.pdf): fan-out amplifies tail latency (63% slow at 100 leaves, 1 in 100 slow); hedged and tied requests, micro-partitions. Abstract page: [research.google](https://research.google/pubs/the-tail-at-scale/).
- [Wikipedia, Little's law](https://en.wikipedia.org/wiki/Little%27s_law): L = λW for long-run averages of a stable system.
- [Wikipedia, Amdahl's law](https://en.wikipedia.org/wiki/Amdahl%27s_law): overall speedup is limited by the share of time the improved part takes.
- [Wikiquote, Donald Knuth](https://en.wikiquote.org/wiki/Donald_Knuth): "premature optimization is the root of all evil" in context, with "the critical 3%", from "Structured Programming with go to Statements" (1974).

## Measurement

- [OpenJDK, JMH](https://github.com/openjdk/jmh): the Java microbenchmark harness; set up with the archetype, don't run from the IDE, peer-review benchmarks.
- [JMH sample 08, Dead code](https://github.com/openjdk/jmh/blob/master/jmh-samples/src/main/java/org/openjdk/jmh/samples/JMHSample_08_DeadCode.java): return or consume results, or the JIT removes the work.
- [JMH sample 10, Constant folding](https://github.com/openjdk/jmh/blob/master/jmh-samples/src/main/java/org/openjdk/jmh/samples/JMHSample_10_ConstantFold.java): read inputs from non-final state fields.
- [async-profiler](https://github.com/async-profiler/async-profiler): low-overhead sampling profiler for CPU, allocation and locks without safepoint bias; flame graph output.
- [Oracle, JDK 21 Diagnostic Tools](https://docs.oracle.com/en/java/javase/21/troubleshoot/diagnostic-tools.html): JFR recordings at start-up and with `jcmd`, the default and profile settings.
- [Grafana k6, Open and closed models](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/): arrival-rate executors, and coordinated omission in closed models.
- [Python docs, profile](https://docs.python.org/3/library/profile.html): `cProfile` (an alias of `profiling.tracing` from 3.15), `pstats`, overhead caveats.
- [PEP 799](https://peps.python.org/pep-0799/): the `profiling` package in 3.15, with `profiling.tracing` and the `profiling.sampling` statistical profiler.
- [py-spy](https://github.com/benfred/py-spy): sampling profiler that attaches to running Python processes; flame graphs; ptrace permissions.
- [Node.js, Profiling Node.js Applications](https://nodejs.org/en/learn/getting-started/profiling): `--prof` and `--prof-process`, and a sync-crypto example.
- [Clinic.js on GitHub](https://github.com/clinicjs/node-clinic): Doctor, Flame, Bubbleprof, HeapProfiler; no longer actively maintained.

## JVM

- [Oracle, JDK 21 GC tuning: available collectors](https://docs.oracle.com/en/java/javase/21/gctuning/available-collectors.html): Serial, Parallel, G1 and ZGC, and when to choose each.
- [Oracle, HotSpot performance enhancements (JDK 21)](https://docs.oracle.com/en/java/javase/21/vm/java-hotspot-virtual-machine-performance-enhancements.html): escape analysis and scalar replacement, lock elision, compressed oops up to about 32 GB, compact strings.
- [Oracle, Virtual Threads (JDK 21)](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html): for I/O-bound concurrency, never pooled, Semaphore for limits, pinning and `jdk.tracePinnedThreads`.
- [Oracle, Virtual Threads (JDK 24)](https://docs.oracle.com/en/java/javase/24/core/virtual-threads.html): pinning now listed only for native methods and foreign functions.
- [inside.java, JEP 491 targeted to JDK 24](https://inside.java/2024/11/15/jep491-target-jdk24/): `synchronized` no longer pins virtual threads from JDK 24 (found by search; openjdk.org refused the fetch).
- [Oracle, Virtual Threads (JDK 25)](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html): pinning only for native methods and foreign functions; `jdk.VirtualThreadPinned` on by default at 20 ms.
- [JDK-8337395, JEP 491](https://bugs.openjdk.org/browse/JDK-8337395) and [InfoQ, Virtual threads after JDK 24](https://infoq.com/articles/virtual-threads-after-jdk24): `jdk.tracePinnedThreads` has no effect from JDK 24; class initialization and native frames still pin.
- [JEP 474](https://openjdk.org/jeps/474) and [JEP 490](https://openjdk.org/jeps/490): generational ZGC the default in JDK 23; non-generational mode removed in JDK 24.
- [JEP 509](https://openjdk.org/jeps/509): experimental JFR CPU-time profiling on Linux in JDK 25 (`jdk.CPUTimeSample`).
- [HikariCP, About Pool Sizing](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing): small pools, `(cores × 2) + spindles` as a start, the deadlock floor formula.
- [AWS, SDK for Java 2.x best practices](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/best-practices.html): reuse thread-safe clients, close streams so connections return to the pool, call timeouts.
- [Oracle, HttpClient (Java 21)](https://docs.oracle.com/en/java/javase/21/docs/api/java.net.http/java/net/http/HttpClient.html): each client has its own connection pool; reuse one client.

## Spring, Jackson and logging

- [Spring Boot, SpringApplication: lazy initialisation](https://docs.spring.io/spring-boot/reference/features/spring-application.html): `spring.main.lazy-initialization`, `@Lazy(false)`, and the trade-offs.
- [Jackson, Performance presentation](https://github.com/FasterXML/jackson-docs/wiki/Presentation:-Jackson-Performance): reuse `ObjectMapper`, `ObjectReader` and `ObjectWriter`; byte input over `String`; Afterburner.
- [SLF4J FAQ](https://www.slf4j.org/faq.html): parameterised logging versus guards; at least 30× faster for disabled statements.

## Data access

- [AWS, DynamoDB: querying and scanning best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-query-scan.html): avoid Scan; page sizes and read cost; parallel scans for large tables only.
- [AWS, DynamoDB: partition key design](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html): 3,000 read and 1,000 write units per partition; read and write unit sizes.
- [AWS, DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html): eventual reads cost half; GSIs are eventually consistent only.
- [AWS, DynamoDB secondary index guidelines](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html): projections and their write and storage cost; LSI limits.
- [AWS, DynamoDB large items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html): the 400 KB item limit; compression, splitting, S3 pointers.
- [AWS, BatchGetItem API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchGetItem.html): 100 keys and 16 MB per call; retry `UnprocessedKeys` with backoff.
- [AWS, DynamoDB query pagination](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.Pagination.html): 1 MB pages, `LastEvaluatedKey`, `Limit`, filters applied after the page.
- [Vlad Mihalcea, N+1 query problem with JPA and Hibernate](https://vladmihalcea.com/n-plus-1-query-problem/): eager and lazy N+1, `JOIN FETCH`, the query-cache pitfall.
- [Use The Index, Luke: No Offset](https://use-the-index-luke.com/no-offset): why OFFSET degrades and how keyset pagination works.

## Caching, HTTP and front end

- [Caffeine, Eviction](https://github.com/ben-manes/caffeine/wiki/Eviction): size, weight and time bounds; avoid soft values.
- [Caffeine, Refresh](https://github.com/ben-manes/caffeine/wiki/Refresh): `refreshAfterWrite` serves old values during one reload.
- [Wikipedia, Cache stampede](https://en.wikipedia.org/wiki/Cache_stampede): locking, external recomputation and probabilistic early expiration.
- [MDN, HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching): `Cache-Control`, `immutable`, `no-cache` with validation, `Vary` pitfalls.
- [MDN, Compression in HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression): gzip and Brotli; don't recompress images; `Vary: Accept-Encoding`.
- [web.dev, Web Vitals](https://web.dev/articles/vitals): LCP, INP and CLS thresholds at the 75th percentile.
- [Node.js, Don't Block the Event Loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop): sync APIs, ReDoS, JSON cost, partitioning and offloading.
