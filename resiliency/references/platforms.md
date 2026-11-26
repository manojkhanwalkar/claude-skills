# Platform built-ins

Use what the stack already has; don't add a library without asking. Check the project's versions before relying on a feature marked with one.

## Spring Framework 7 (Spring Boot 4)

The separate Spring Retry project (`spring-retry`, `@EnableRetry`) is superseded by these core features; don't add it to a Framework 7 project.

- **`org.springframework.core.retry.RetryTemplate`** with a `RetryPolicy`:
  - `RetryPolicy.builder()`: `maxRetries`, `delay`, `multiplier`, `maxDelay`, `jitter`, `includes`, `excludes`, `predicate`, `backOff`. `includes` and `excludes` match nested causes too; a `predicate` runs after them.
  - **`maxRetries` counts retries, not tries:** 3 tries in total is `maxRetries(2)`. The default (`new RetryTemplate()`, `RetryPolicy.withDefaults()`) is 3 retries with a fixed 1 s wait.
  - `execute(Retryable)` throws the checked `RetryException` when retries run out; its cause is the last failure, earlier ones are suppressed. Rethrow the cause (or a domain exception); don't propagate `RetryException`. Newer 7.x versions also have `invoke(Supplier)` / `invoke(Runnable)`, which rethrow the last original exception.
  - A `RetryListener` (or `CompositeRetryListener`) observes each try, for metrics and logs.
- **`@Retryable`** (`org.springframework.resilience.annotation`), enabled by `@EnableResilientMethods` on a `@Configuration` class: the same attributes as the builder, with `String` variants for placeholders. The default retries **any** exception, 3 times, 1 s apart, so always set `includes` or a `predicate`. Reactive return types get a Reactor retry spec. Annotations go through a proxy: a call from inside the same bean isn't retried.
- **`@ConcurrencyLimit`** (same package and enabler): limits concurrent calls to a method or bean. By default (`policy = BLOCK`) the excess **waits**, like a pool. Since 7.0.3, `policy = REJECT` throws `InvocationRejectedException` (a `RejectedExecutionException`) at once. Use `BLOCK` only as an outbound bulkhead with a bounded caller; for inbound load shedding use `REJECT` mapped to 503, or `Semaphore.tryAcquire()` in a filter.
- **HTTP clients:** `RestClient` and HTTP interface clients have no built-in retry; add it with a `ClientHttpRequestInterceptor` or around the call, not both. Set connect and read timeouts on the request factory (`JdkClientHttpRequestFactory`, or `HttpComponentsClientHttpRequestFactory` with its connection-request timeout too) or with Spring Boot's HTTP client properties.

## Resilience4j

Use it when the project already does. Its defaults differ from what the names suggest:

- **Retry:** `maxAttempts` counts the first call (default 3, wait 500 ms). Set `retryOnException` / `retryExceptions` narrowly; the default retries every exception.
- **RateLimiter:** permits per refresh period (default 50 per 500 ns), not a token bucket with a burst. `timeoutDuration` defaults to **5 s of waiting** for a permit; set it to 0 for load shedding, then answer 429.
- **Bulkhead:** the semaphore bulkhead's `maxWaitDuration` defaults to 0 (refuse at once), `maxConcurrentCalls` to 25. The thread-pool bulkhead queues.
- **TimeLimiter:** works on futures; `cancelRunningFuture` cancelling a `CompletableFuture` does not interrupt the running task (see the pitfalls).
- **Decorator order** (`Retry(CircuitBreaker(RateLimiter(TimeLimiter(Bulkhead(call)))))` by default with the annotations): the retry is the outer layer. Don't also retry in an interceptor underneath.

## JDK `HttpClient`

`HttpClient.newBuilder().connectTimeout(...)` covers connecting only; `HttpRequest.newBuilder().timeout(...)` covers until the response headers arrive, not the body. Bound a streamed body read yourself. No built-in retry for application errors.

## AWS SDK for Java v2

- **The SDK's retries are one retry layer.** Standard and adaptive modes already retry throttling, 5xx and transient I/O with backoff and jitter, behind a client-side retry quota. Tune them; don't wrap SDK calls in another retry. Set the strategy and its attempts explicitly, so the count doesn't change with the SDK version: `ClientOverrideConfiguration.builder().retryStrategy(b -> b.maxAttempts(3))`, or `retryStrategy(RetryMode.STANDARD)`; `AWS_RETRY_MODE` and `AWS_MAX_ATTEMPTS` set it from the environment. `retryPolicy` is the older, deprecated API. The defaults per mode and service are in `dynamodb-optimizer`'s `references/sdk-java.md`.
- **Timeouts:** the SDK sets no default `apiCallTimeout` (the whole call, all attempts) or `apiCallAttemptTimeout` (one attempt). Set both: attempt timeout × attempts + waits ≤ call timeout ≤ the caller's budget. On the HTTP client (Apache or URL connection) set `connectionTimeout` (short), `socketTimeout` and, for Apache, `connectionAcquisitionTimeout`.
- **Not safe to repeat:** the SDK retries non-idempotent operations too (an `UpdateItem` with `ADD`, an SQS send without deduplication). Make them repeatable with a condition expression, `TransactWriteItems`' `ClientRequestToken`, or FIFO deduplication IDs, or lower their attempts.

## Others

- **Python:** urllib3 `Retry` (`total`, `backoff_factor`, `backoff_jitter`, `status_forcelist`, `allowed_methods`, `respect_retry_after_header`) on a requests `HTTPAdapter`; tenacity (`stop_after_attempt`, `wait_random_exponential`, `retry_if_exception_type`); `httpx.Timeout(connect=..., read=...)`. botocore has its own retry modes: the same one-layer rule applies.
- **Node:** `retry-axios` or a fetch wrapper; `AbortSignal.timeout(ms)` for fetch. The AWS SDK v3 has `maxAttempts` and `retryMode`.
- **.NET:** Polly (`Microsoft.Extensions.Http.Resilience` standard handler: retry, circuit breaker, attempt and total timeouts).
- **gRPC:** a service config `retryPolicy` (`maxAttempts`, `initialBackoff`, `maxBackoff`, `backoffMultiplier`, `retryableStatusCodes` such as `UNAVAILABLE`) plus a deadline on every call; the deadline covers all attempts.
