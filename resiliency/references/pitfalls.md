# Resiliency pitfalls

Each of these shipped in a first attempt and was caught later by a review or a test. Check for every one.

## Retries

- **Off-by-one on the last try.** The interceptor counted a try only after `execute()` succeeded. After two I/O failures, a 503 on the real last try was thrown as an internal "retryable" exception instead of being returned. Callers caught only their HTTP client's exceptions, so users got a 500 instead of "temporarily unavailable". Count the try *before* the call, and on the last try return the response unchanged.
- **Retrying something that isn't safe to repeat.** Retrying after a read timeout or a 502/504 can repeat work the server already did: a billed check, a sent message, a created record. For such calls, retry only failures that prove the request never arrived, plus 429 and 503.
- **Retries multiplied across layers.** A retries B, B retries C, so one user request becomes 9 calls to C during an outage. Retry at one layer; don't retry an error that only relays a downstream failure the callee already retried.
- **Retrying bugs.** A predicate like "anything that isn't a protocol error" also retries `NullPointerException` and other programming errors, and may reset shared connections each time. Prefer I/O failures found in the cause chain, where the library's exception types allow it.
- **Retries without timeouts.** A retry never fires if the first call hangs forever. Check for libraries that wait with no limit inside the client (for example `CompletableFuture.get()` with no argument).
- **Assuming how jitter behaves.** Spring's `RetryPolicy` jitter never shortens a wait below the base delay. Check the library's semantics before documenting "±jitter", and test the bounds you document.
- **Retry settings with a "no retries" default constructor.** It is easy to wire production code through the convenience constructor by mistake. Require the settings explicitly.

## Timeouts

- **`CompletableFuture.cancel(true)` does not interrupt** the running task. A timed-out call keeps its thread and connection blocked, and these pile up under steady traffic. Use a `FutureTask` on a (virtual) thread; its `cancel(true)` interrupts.
- **Per-attempt vs. overall budget.** An attempt timeout of half the overall timeout means that after one hung attempt only one more fits. Document the real behaviour, not "3 tries".
- **Worst-case latency.** Tries × timeout plus the waits; 3 × 5 s ≈ 15 s. Tell the user.

## Request limits

- **Health checks matched on the raw URI.** `getRequestURI().startsWith("/actuator/")` lets `/actuator/..;/api/...` and `/actuator/%2e%2e/api/...` skip the limits. Decoding alone still leaves `/actuator/../api/...`. Match the decoded path without `;params` that the router uses, and treat any `..` segment as not exempt.
- **One shared bucket in front of a per-client limiter.** One client can use up the global bucket, and then everyone gets 429. Run the per-client limiter first.
- **Static files counted.** Page loads (HTML, CSS, JS) used up the bucket in a service that also serves the UI. Scope the limits to API paths there.
- **Queueing instead of refusing.** A blocking semaphore just moves the overload into waiting threads. Use `tryAcquire()` and answer 503 at once.
- **Slot leaks.** Release the semaphore in `finally`, so a handler that throws doesn't shrink capacity for good.
- **Filter order.** Security headers come first, so refusals carry them. Then the per-client limiter, then the shared limits, then the body-size limit, then authentication.
- **Unbounded body reads.** A controller that takes `@RequestBody String` and checks the length afterwards has already buffered the whole body. Cap the body in a filter before it is read.

## Testing

- **MockMvc does not apply servlet multipart or filter-registration limits.** Test 413 and filter behaviour on a real server (random port) or with the filter directly.
- **`-rf :module` resumes take older sibling modules from the local repository.** A new class in a shared module shows up as `NoClassDefFoundError`. Re-run the full reactor.
- **Mock servers refuse new expectations after requests have run** (Spring `MockRestServiceServer`). Set up all expectations first.
