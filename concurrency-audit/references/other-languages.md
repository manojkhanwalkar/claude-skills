# Other languages

## Kotlin coroutines

- `GlobalScope.launch` (no structured lifetime, leaks); use a scope tied to the component or `coroutineScope { }`.
- Blocking calls (`Thread.sleep`, JDBC, blocking HTTP) on `Dispatchers.Default` or `Main`; use `withContext(Dispatchers.IO)`.
- Shared mutable state across coroutines on a multi-threaded dispatcher: `Mutex`, `AtomicInteger`, or confine to one actor or `limitedParallelism(1)`.
- Catching `CancellationException` and not rethrowing (breaks cancellation); `runCatching` around suspending code swallows it.
- `runBlocking` inside a coroutine or on a request thread.

## Python

- The GIL doesn't make compound operations atomic: `d[k] += 1`, check-then-set and list read-modify-write race under `threading`; use a `threading.Lock`, `queue.Queue`, or `collections.Counter` per thread then merge. Free-threaded builds (3.13t and later) make unguarded shared state riskier still.
- `asyncio`: blocking calls (`requests`, `time.sleep`, sync DB drivers, heavy CPU) inside `async def` stall the loop; use async clients, `asyncio.to_thread`, or a process pool.
- Shared state across `await` points: another task can run between a read and a write; guard with `asyncio.Lock`.
- Fire-and-forget `asyncio.create_task` without keeping a reference (the task can be garbage-collected) or awaiting it (exceptions lost); use `asyncio.TaskGroup` (3.11).
- `multiprocessing` with shared objects not designed for it; global state in forked workers (gunicorn) that each process holds separately.

## Node.js and TypeScript

- Races across `await`: read, `await`, write on shared module state or a DB row; use atomic DB operations or a per-key mutex.
- Missing `await` (a floating promise): errors become unhandled rejections and ordering breaks; enable `@typescript-eslint/no-floating-promises`.
- `Promise.all` over an unbounded list hammering a downstream; bound it (`p-limit` or a manual pool).
- `forEach` with an `async` callback (nothing waits); use `for…of` with `await` or `Promise.all`.
- CPU-heavy work on the event loop; move to `worker_threads`.
- Module-level caches shared across requests holding per-user data.

## Go

- Run `go test -race`; data races are undefined behaviour.
- Maps written from several goroutines without a `sync.Mutex` (fatal error at run time); `sync.Map` only for its specific use cases.
- Goroutine leaks: sends or receives with no reader or writer, missing `context` cancellation, `time.After` in loops.
- Loop-variable capture before Go 1.22.
- `sync.WaitGroup.Add` called inside the goroutine instead of before it.
- Copying a struct that contains a `sync.Mutex` (`go vet` copylocks).
