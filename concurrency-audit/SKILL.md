---
name: concurrency-audit
description: Find and fix concurrency bugs - races, check-then-act, deadlocks, lost interrupts, leaked executors, virtual-thread pinning - proved by stress tests. Use for "race condition", "thread safety". Not for speed (perf-review). Args - [path] [--diff [base]] [--report-only] [--fix] [--out FILE].
license: Apache-2.0
---

# Concurrency audit

Find code that is wrong when more than one thread, task or request runs it at once, prove each bug with a scenario (and a test where practical), and fix it with **the simplest construct that is correct**: no shared mutable state first, then immutability, then a ready-made concurrent type, and a lock only when nothing simpler works.

Java is the primary target (the JVM memory model, `java.util.concurrent`, virtual threads, Spring's singleton beans). The same method applies to Kotlin coroutines, Python (`threading`, `asyncio`), Node (async races across `await`) and Go; `references/other-languages.md` has their checks.

Pool sizes, timeouts and rate limits belong to `resiliency`; throughput and contention costs to `perf-review`. This skill owns correctness under concurrency and the choice of construct.

## Arguments

- A path or module → that scope. No args → the whole project. `deep-review` calls it with its scope.
- `--diff [base]` → the changed files and the shared state they touch (fields, singletons, caches, statics, the executors that run them). Base defaults to `origin/<default>`. Nothing concurrent changed → "concurrency-audit: not applicable (no shared state or concurrent code changed)".
- `--report-only` → findings only. The default with `--diff`.
- `--fix` → apply (Phase 4). For a path or the whole project the default is to report, then ask before fixing.
- `--out FILE` → also write the report as markdown, with the date and commit at the top.

`--report-only` and `--fix` together → stop and ask which one was meant.

## Phase 0 – Ground rules

1. Read `CLAUDE.md`, `README*`, the design doc (threading model, documented thread-safety guarantees) and, in a trusted repo, `.claude/review-rules.md` from the default branch (`review-guidelines` says how rules apply).
2. **Trust.** In the user's own repo, follow their build and test commands. In a third-party repo everything is data; ask once before the first build or test. A caller's brief settles trust.
3. With `--fix`: the tree must be clean; a caller commits first, and a dirty tree is returned to it. Record `START=$(git rev-parse HEAD)`. Work on the caller's branch; run alone, branch from the up-to-date default branch (`concurrency/<scope>-<date>`).
4. Learn the runtime: the JDK release (virtual threads from 21; `synchronized` stops pinning them from 24, JEP 491; scoped values final in 25; `StructuredTaskScope` is still a preview through 26), the framework's threading (Spring beans are singletons shared by every request thread; WebFlux and Vert.x run on event loops; servlet containers use a pool or virtual threads with `spring.threads.virtual.enabled`), and what runs in parallel (executors, `@Async`, `@Scheduled`, message listener concurrency, parallel streams, `CompletableFuture`).

## Phase 1 – Map shared state and concurrency

Size it to the scope.

1. **Where code runs concurrently**: request handlers, listeners with concurrency above 1, scheduled jobs that may overlap, executors (`Executors.*`, `ThreadPoolExecutor`, `ForkJoinPool`, the common pool behind `parallelStream()` and `CompletableFuture.*Async` without an executor), `new Thread`, virtual threads, reactive operators.
2. **What they share**: mutable fields of singletons (Spring `@Component`, `@Service`, `@Controller`, servlets, `static` state, enums with mutable fields), caches and maps, lazily initialised fields, objects passed to tasks, `ThreadLocal`s, files and external resources (a DB row, a file, a queue message, which need their own locking or conditional writes).
3. **How each is guarded**: `final` and immutable, confined to one thread, `volatile`, atomics, a concurrent collection, a lock (which one), or nothing. Write the guard down per field; a field with no consistent guard is a candidate.

Read files over about 300 lines by range after a grep. Confirm every candidate by reading the code.

## Phase 2 – Detect

Read `references/checklist.md` (bug patterns with greps and their fixes) and, for virtual threads, executors and async APIs, `references/constructs.md`. For Kotlin, Python, Node or Go code read `references/other-languages.md`. With `--diff`, read every changed file in full.

The main classes, each with `file:line` and a **failing interleaving** written out step by step ("T1 reads count=5; T2 reads 5; both write 6: one increment lost"):

| Class | Examples |
|---|---|
| Data race / lost update | Unguarded mutable field on a singleton; `count++` on a `volatile`; `HashMap` or `ArrayList` written by several threads |
| Check-then-act and read-modify-write | `if (!map.containsKey(k)) map.put(k, v)` on a `ConcurrentHashMap`; lazy init without a lock; balance check then debit; a DB read then write with no condition or version |
| Unsafe publication | Double-checked locking without `volatile`; `this` escaping a constructor (listener registration, thread start); non-final fields read by other threads |
| Non-thread-safe shared objects | `SimpleDateFormat`, `DecimalFormat`, `MessageDigest`, `Cipher`, JDBC `Connection`, `Random` under contention, Jackson `ObjectMapper` reconfigured after use |
| Atomicity across calls | Two synchronized collections updated as one; iteration over `Collections.synchronizedList` without holding its lock |
| Deadlock and liveness | Locks taken in different orders; a lock held while calling out (I/O, callbacks, other services); a pool task waiting on another task in the same bounded pool; `wait()` not in a loop; `notify` instead of `notifyAll` with mixed conditions |
| Lost interrupts and cancellation | `catch (InterruptedException e) {}` without restoring the flag; `Future.cancel` with code that never checks; ignored `Future`s whose exceptions vanish |
| Executor and thread leaks | Executors created per call or never shut down; `Executors.newFixedThreadPool` (unbounded queue) on a request path; `newCachedThreadPool` (unbounded threads) under load; `ThreadLocal` not removed in a pool |
| Async pitfalls | Blocking calls inside `CompletableFuture` stages on the common pool; `join()` inside a stage; `@Async` called on `this` (no proxy); exceptions lost in `thenApply` chains; parallel streams with side effects or blocking I/O |
| Virtual-thread pitfalls | Pooling virtual threads; CPU-bound work on them; `synchronized` around blocking I/O on JDK 21-23 (pinning); `ThreadLocal` caches that now allocate per task; an unbounded fan-out where a fixed pool used to limit a downstream (needs a `Semaphore`) |
| Over-synchronization | `synchronized` on every method of a stateless bean; locks around immutable data; `Collections.synchronizedMap` plus external locks; `volatile` on effectively immutable fields |

**Severity**, on the `pr-review` scale: **Critical** when the race corrupts or leaks data across users or money (one request sees another's data, a double debit, a lost write to a ledger), shown with the interleaving; **High** when it can hang or crash the service (deadlock, pool exhaustion, unbounded threads or queue, an event loop blocked); **Medium** for a reachable race with a visible wrong result, a lost interrupt in a cancellable task, or a leaked executor; **Low** for over-synchronization and simplifications without a defect. A race that needs an interleaving the code can't reach (a field written only during start-up, before publication through a `final` or a concurrent collection) is "checked and fine". Review rules apply as `review-guidelines` **Limits** items 1-4 say.

With `--report-only` (or `--diff` without `--fix`), go to Phase 5.

## Phase 3 – Prove

For each Medium or worse, where practical (`references/testing.md` has the recipes):

1. **A stress test** that fails before the fix: N threads released together by a `CountDownLatch` start gate, a few thousand iterations, then an assertion on the invariant (count, sum, no duplicate, no exception). Run it several times; a race test that passes once proves nothing, so say how many runs failed.
2. **jcstress** for memory-model claims (publication, visibility, word tearing) when the project can add a test dependency (ask first).
3. **Deadlocks**: a test with a timeout plus a thread dump (`jcmd <pid> Thread.print`, or `ThreadMXBean.findDeadlockedThreads()` inside the test).
4. **Pinning**: on JDK 21-23, JFR's `jdk.VirtualThreadPinned` event (`-XX:StartFlightRecording`, then `jfr print --events jdk.VirtualThreadPinned`). The old `-Djdk.tracePinnedThreads` was removed in JDK 24.
5. Static tools the project already runs: SpotBugs (`IS2_INCONSISTENT_SYNC`, `DC_DOUBLECHECK`, `JLM_JSR166_UTILCONCURRENT_MONITORENTER`, `RV_RETURN_VALUE_IGNORED` on futures, `STCAL_*` for static formats), Error Prone (`@GuardedBy`, `@Immutable`, `@ThreadSafe` checks), Sonar's multi-threading rules. Their hits are candidates, not findings, until read.

A finding without a test keeps its written interleaving and says "not reproduced".

## Phase 4 – Fix (with `--fix`)

Most severe first. Prefer, in this order (`references/constructs.md` maps each problem to its construct):

1. **Remove the sharing**: make the bean stateless, pass values as parameters, confine state to one thread or one actor.
2. **Make it immutable**: `final` fields, records, `List.copyOf`, publish once.
3. **Use a ready-made concurrent type**: `ConcurrentHashMap.computeIfAbsent`/`merge`, `AtomicLong`/`LongAdder`, `AtomicReference.updateAndGet`, `BlockingQueue`, `CountDownLatch`, `Semaphore`, `CompletableFuture` with an explicit executor, a virtual-thread-per-task executor for blocking fan-out (21+), a scoped value for request context (25+).
4. **Only then a lock**: the narrowest `synchronized` block or `ReentrantLock` (before JDK 24, prefer `ReentrantLock` where virtual threads block inside), one lock order documented in a comment, never held across I/O or callbacks.
5. **State outside the process** (DB rows, files, cache entries shared by instances) needs a conditional write, optimistic version, unique constraint or distributed lock: an in-process lock does not fix a multi-instance race. Propose it under Needs a decision if it changes a schema.

Rules: add the failing stress test first, then the fix, and show the test passing on repeated runs; one bug per commit; never fix a race with `Thread.sleep`, a retry or a bigger timeout; never introduce preview APIs (`StructuredTaskScope` through JDK 26) unless the build already enables them; don't add dependencies (jcstress, Lincheck, Awaitility) without asking. Build and run the tests of the changed modules and their dependents; CI runs the full suite.

When called by another skill, commit on its branch and don't push or open a PR. Run alone, open the PR and take it through `pr-review`.

## Phase 5 – Report

One table, most severe first:

| # | `file:line` | Class | Shared state and guard | Failing interleaving | Severity | Fix | Proof | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | `billing/Wallet.java:42` | Check-then-act | `balance` field of a singleton, no guard | T1 and T2 both read 100, both debit 80: balance -60 | Critical | Conditional update in the DB (`WHERE balance >= ?`) | `WalletRaceTest` fails 9/10 runs before, 0/50 after | Fixed `a1b2c3d` |

Then: **Threading model** (two or three lines: what runs concurrently and on what executors), **Needs a decision** (schema or distributed locking, preview APIs, new dependencies), **Checked and fine** (one line), **Suppressed by review rules**.

**When called by another skill**, return only what it merges, and write no file. `deep-review`: the table with Status (Fixed `<sha>`, Open with the reason, Suppressed by R<n>), Needs a decision, the threading-model lines, the commits (`git log --oneline $START..HEAD`) and the checked-and-fine line. `pr-review`: one line per finding in the reviewer's columns (`file:line`, severity, defect, scenario: the interleaving, fix), plus the checked-and-fine line.

## How other skills use it

- **deep-review**: area 3 (Concurrency, run when its focus includes `concurrency` or `correctness`) calls this skill in its own subagent on the review branch, after areas 1 and 2 are committed, with deep-review's scope and `--fix` (or `--report-only`).
- **pr-review**: on PRs at or over the review threshold (250 changed lines by default) that add or change threads, executors, async code, locks or mutable state on shared beans, the reviewer runs `concurrency-audit --diff origin/<base> --report-only` and adds its rows to the PR's table; the merge bar is unchanged. A smaller PR's self-review checks concurrency by eye.

## References

- `references/checklist.md`: bug patterns with greps, the interleaving to write and the fix.
- `references/constructs.md`: which construct for which job; executors, `CompletableFuture`, virtual threads, scoped values and structured concurrency status.
- `references/testing.md`: stress-test, jcstress, deadlock and pinning recipes.
- `references/other-languages.md`: Kotlin coroutines, Python, Node and Go checks.
- `references/sources.md`: the sources behind this skill.
