# Proving concurrency bugs

A race test reports how many of its runs failed; one passing run proves nothing.

## Stress test with a start gate (JUnit 5)

```java
@RepeatedTest(20)
void concurrentDebitsNeverOverdraw() throws Exception {
    int threads = 16;
    var start = new CountDownLatch(1);
    try (var pool = Executors.newFixedThreadPool(threads)) {
        List<Future<Boolean>> results = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            results.add(pool.submit(() -> { start.await(); return wallet.debit(80); }));
        }
        start.countDown();                       // release every thread at once
        long succeeded = 0;
        for (var r : results) if (r.get(5, TimeUnit.SECONDS)) succeeded++;
        assertThat(succeeded).isEqualTo(1);      // the invariant, not a timing
        assertThat(wallet.balance()).isEqualTo(20);
    }
}
```

- Use more threads than cores and a few thousand operations per thread for counters and maps.
- Assert invariants (totals, uniqueness, no exception), never sleeps or timings.
- For an external store, run the test against the real store in a container (Testcontainers) or the project's emulator; an in-memory fake usually serialises calls and hides the race.
- Keep the test after the fix as a regression test; tag it if it is slow.

## jcstress (memory-model claims)

For publication, visibility and tearing, where a stress test is too weak. Ask before adding the dependency.

```java
@JCStressTest
@Outcome(id = "1", expect = ACCEPTABLE, desc = "saw the published value")
@Outcome(id = "0", expect = FORBIDDEN, desc = "saw a half-built object")
@State
public class PublicationTest {
    Holder h;
    @Actor void writer() { h = new Holder(1); }
    @Actor void reader(I_Result r) { Holder l = h; r.r1 = (l == null) ? 1 : l.x; }
}
```

## Deadlocks

- Run the suspect path with `assertTimeoutPreemptively`, and on timeout dump threads: `ManagementFactory.getThreadMXBean().findDeadlockedThreads()` returns the cycle.
- On a running JVM: `jcmd <pid> Thread.print` (or `jcmd <pid> Thread.dump_to_file -format=json <file>` for virtual threads, 21+).

## Virtual-thread pinning (JDK 21-23)

- `java -XX:StartFlightRecording:filename=rec.jfr,settings=profile …`, then `jfr print --events jdk.VirtualThreadPinned rec.jfr`.
- `-Djdk.tracePinnedThreads` was removed in JDK 24; use JFR.

## Static analysis already in the build

- SpotBugs: `IS2_INCONSISTENT_SYNC`, `DC_DOUBLECHECK`, `LI_LAZY_INIT_STATIC`, `STCAL_INVOKE_ON_STATIC_DATE_FORMAT_INSTANCE`, `JLM_JSR166_UTILCONCURRENT_MONITORENTER`, `RV_RETURN_VALUE_IGNORED_BAD_PRACTICE`, `SWL_SLEEP_WITH_LOCK_HELD`, `UL_UNRELEASED_LOCK`.
- Error Prone: `GuardedBy`, `Immutable`, `ThreadSafe`, `DoubleCheckedLocking`, `SynchronizeOnNonFinalField`, `FutureReturnValueIgnored`, `InterruptedExceptionSwallowed`.
- Treat hits as candidates; read the code and write the interleaving.

## Other languages

- Go: `go test -race`. Kotlin: Lincheck (also usable from Java). Python: `pytest` with `threading.Barrier` as the start gate; `PYTHONASYNCIODEBUG=1` or `asyncio.run(main(), debug=True)` flags slow, blocking callbacks. Node: drive interleavings with controlled promises and fake timers.
