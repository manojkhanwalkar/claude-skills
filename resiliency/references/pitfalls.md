# Resiliency pitfalls

Each of these shipped in a first attempt and was caught later by a review or a test. Check for every one.

## Retries

- **Off-by-one on the last try.** The interceptor counted a try only after `execute()` succeeded. After two I/O failures, a 503 on the real last try was thrown as an internal "retryable" exception instead of being returned. Callers caught only their HTTP client's exceptions, so users got a 500 instead of "temporarily unavailable". Count the try *before* the call, and on the last try return the response unchanged.
- **Retrying something that isn't safe to repeat.** Retrying after a read timeout or a 502/504 can repeat work the server already did: a billed check, a sent message, a created record. For such calls, retry only failures that prove the request never arrived, plus 429 and 503.
- **Retries multiplied across layers.** A retries B, B retries C, so one user request becomes 9 calls to C during an outage. Retry at one layer; don't retry an error that only relays a downstream failure the callee already retried.
- **Stacked retries inside one service.** A retrying HTTP interceptor was added, and a caller kept its own retry loop around the same client: 3 × 3 tries per call, and three times the worst-case wait. When adding an interceptor, remove the callers' loops (or exempt those clients), and test the request count at the callee.
- **Wrapping an SDK that already retries.** The AWS SDK v2's standard retries are a layer of their own; a `RetryTemplate` around a DynamoDB call multiplies them. Configure the SDK's `maxAttempts` instead.
- **Freeing an idempotency key on an unknown outcome.** A charge timed out, the code released its idempotency key as "failed", and the next try ran the charge again under a fresh reservation. On a timeout, a reset after sending, 502 or 504, keep the key reserved and mark the operation pending until the callee's answer or a reconciliation settles it.
- **Mixing up tries and retries.** Spring's `maxRetries` counts retries (`maxRetries(3)` is 4 tries); Resilience4j's `maxAttempts` and the AWS SDK's `maxAttempts` count the first call. Name settings `maxAttempts` or `maxRetries` to match what they count, and test the request count.
- **Retrying bugs.** A predicate like "anything that isn't a protocol error" also retries `NullPointerException` and other programming errors, and may reset shared connections each time. Prefer I/O failures found in the cause chain, where the library's exception types allow it.
- **Retries without timeouts.** A retry never fires if the first call hangs forever. Check for libraries that wait with no limit inside the client (for example `CompletableFuture.get()` with no argument).
- **Assuming how jitter behaves.** Spring's `RetryPolicy` jitter never shortens a wait below the base delay. Check the library's semantics before documenting "±jitter", and test the bounds you document.
- **Retry settings with a "no retries" default constructor.** It is easy to wire production code through the convenience constructor by mistake. Require the settings explicitly.

## Timeouts

- **`CompletableFuture.cancel(true)` does not interrupt** the running task. A timed-out call keeps its thread and connection blocked, and these pile up under steady traffic. Use a `FutureTask` on a (virtual) thread; its `cancel(true)` interrupts.
- **Per-attempt vs. overall budget.** An attempt timeout of half the overall timeout means that after one hung attempt only one more fits. Document the real behaviour, not "3 tries".
- **Connect timeout as long as the budget.** A 10 s connect timeout inside a 10 s budget spends it all on one unreachable host, so the retry never runs. Keep connect timeouts short (about 1–2 s on a LAN) and well under the total.
- **Worst case past the caller's budget.** Tries × timeout plus the waits; 3 × 5 s ≈ 15 s behind a caller that gives up after 10 s means the last tries run for nobody and hold threads. Make Σ attempt timeouts + Σ waits fit the caller's budget, or stop at a deadline, and tell the user the number.
- **`Retry-After` taken at face value.** A callee answered `Retry-After: 120`, and the caller slept two minutes inside a request. Cap the wait at the remaining budget and fail at once when it doesn't fit.

## Request limits

- **Health checks matched on the raw URI.** `getRequestURI().startsWith("/actuator/")` lets `/actuator/..;/api/...` and `/actuator/%2e%2e/api/...` skip the limits. Decoding alone still leaves `/actuator/../api/...`. Match the decoded path without `;params` that the router uses, and treat any `..` segment as not exempt.
- **One shared bucket in front of a per-client limiter.** One client can use up the global bucket, and then everyone gets 429. Run the per-client limiter first.
- **Static files counted.** Page loads (HTML, CSS, JS) used up the bucket in a service that also serves the UI. Scope the limits to API paths there.
- **Queueing instead of refusing.** A blocking semaphore just moves the overload into waiting threads. Use `tryAcquire()` and answer 503 at once. Library defaults block too: Spring's `@ConcurrencyLimit` waits unless `policy = REJECT` (7.0.3+), and Resilience4j's `RateLimiter` waits up to 5 s for a permit unless `timeoutDuration` is 0.
- **Slot leaks.** Release the semaphore in `finally`, so a handler that throws doesn't shrink capacity for good.
- **Filter order.** Security headers come first, so refusals carry them. Then the per-client limiter, then the shared limits, then the body-size limit, then authentication.
- **Unbounded body reads.** A controller that takes `@RequestBody String` and checks the length afterwards has already buffered the whole body. Cap the body in a filter before it is read.

## Testing

- **MockMvc does not apply servlet multipart or filter-registration limits.** Test 413 and filter behaviour on a real server (random port) or with the filter directly.
- **`-rf :module` resumes take older sibling modules from the local repository.** A new class in a shared module shows up as `NoClassDefFoundError`. Build with `-pl <module> -am` (or the full reactor) instead.
- **Mock servers refuse new expectations after requests have run** (Spring `MockRestServiceServer`). Set up all expectations first.
