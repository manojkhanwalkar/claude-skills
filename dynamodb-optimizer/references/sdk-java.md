# SDK for Java v2 (plus boto3 and JS v3 notes)

## Clients

- `DynamoDbClient` (low-level, `Map<String, AttributeValue>`) and `DynamoDbEnhancedClient` (maps classes with `TableSchema`, the successor of v1's `DynamoDBMapper`; also an Enhanced Document API for schemaless items). Both are fine; mixing them for one table is a smell only when the two disagree on attribute names or types.
- Clients are thread-safe and hold their own connection pool: build **one per application** (a Spring bean), close it on shutdown. A client per request leaks pools and pays TLS handshakes.
- Build each `TableSchema` (`fromBean`, `fromImmutableClass`) and `DynamoDbTable` once; they use reflection.
- **Timeouts**: the SDK sets no default `apiCallTimeout` (whole call, all attempts) or `apiCallAttemptTimeout` (one attempt). Set both in `ClientOverrideConfiguration`. The values and the retry budget belong to the `resiliency` skill (its checklist, and the AWS SDK section of its `references/platforms.md`).
- **Retries**: since SDK 2.58.0 the default mode is `standard`: for DynamoDB 4 attempts, 25 ms base delay, backoff with jitter on throttling and transient errors. `legacy` (the earlier default) makes 9 attempts. `adaptive` adds client-side rate limiting; use one client per table with it. Configure with `overrideConfiguration(o -> o.retryStrategy(RetryMode.STANDARD))`, `AWS_RETRY_MODE`, or `aws.retryMode`; `AWS_MAX_ATTEMPTS` caps attempts.
- `TransactionCanceledException` is a client error the SDK doesn't retry; handle it by its cancellation reasons (see Transactions).

## Paginators

```java
// low-level: every page, every item
dynamo.queryPaginator(QueryRequest.builder()
        .tableName(table)
        .keyConditionExpression("#pk = :pk AND #sk BETWEEN :from AND :to")
        .expressionAttributeNames(Map.of("#pk", "customerId", "#sk", "createdAt"))
        .expressionAttributeValues(Map.of(":pk", s(id), ":from", s(from), ":to", s(to)))
        .build())
    .items().forEach(this::accept);

// stop after N items across pages
dynamo.queryPaginator(request).items().stream().limit(20).toList();
```

- `.items()` flattens pages; `.stream()` on the paginator streams **pages**. Manual loops use `lastEvaluatedKey()` → `exclusiveStartKey(...)` until `hasLastEvaluatedKey()` is false or the map is empty.
- `limit(n)` on the request is items **evaluated per page**, not a result cap.
- For a UI page, return the `LastEvaluatedKey` as an opaque cursor (encode it; it contains key values, so don't expose it raw if they are sensitive).

### Enhanced Client

```java
DynamoDbTable<Order> orders = enhanced.table("orders", ORDER_SCHEMA);   // once
QueryConditional range = QueryConditional.sortBetween(
        k -> k.partitionValue(customerId).sortValue(from),
        k -> k.partitionValue(customerId).sortValue(to));
orders.query(r -> r.queryConditional(range)).items().forEach(this::accept);   // all pages
orders.index("open-orders").query(r -> r.queryConditional(QueryConditional.keyEqualTo(k -> k.partitionValue("OPEN"))))   // a GSI: SdkIterable<Page<T>>, no .items()
      .stream().flatMap(page -> page.items().stream()).forEach(this::accept);
```

- A table's `query` and `scan` return `PageIterable` (sync) or `PagePublisher` (async); `.items()` iterates across all pages. An index's (`DynamoDbIndex`) return `SdkIterable<Page<T>>`: flatten the pages as above. `batchGetItem` returns `BatchGetResultPageIterable` and `batchWriteItem` a `BatchWriteResult` (see Batch calls). Code that takes `.iterator().next()` or `.stream().findFirst()` on pages reads one page only.
- `QueryConditional.keyEqualTo`, `sortBeginsWith`, `sortBetween`, `sortGreaterThan(OrEqualTo)`, `sortLessThan(OrEqualTo)` are key conditions; methods named `sort...` compare the sort key, they don't sort. A `filterExpression` on the request is applied after the read.

## Batch calls

```java
Map<String, List<WriteRequest>> pending = Map.of(table, requests);   // ≤ 25, no duplicate keys
for (int attempt = 0; !pending.isEmpty(); attempt++) {
    if (attempt == MAX_ATTEMPTS) throw new IllegalStateException(count(pending) + " items not written");
    if (attempt > 0) sleep(backoffWithJitter(attempt));               // e.g. 50 ms × 2^attempt, full jitter, cap 2 s
    var batch = pending;                                              // a lambda needs an effectively final local
    BatchWriteItemResponse r = dynamo.batchWriteItem(b -> b.requestItems(batch));
    pending = r.hasUnprocessedItems() ? r.unprocessedItems() : Map.of();
}
```

- Same loop for `batchGetItem` with `unprocessedKeys()` (up to 100 keys, 16 MB; results unordered).
- Enhanced: `enhanced.batchWriteItem(...)` returns `BatchWriteResult`; read `unprocessedPutItemsForTable(table)` and `unprocessedDeleteItemsForTable(table)` and re-send them. `batchGetItem(...)` returns pages; read `unprocessedKeysForTable(table)` on each page.
- A batch is rejected whole for duplicate keys, more than 25 writes, an item over 400 KB or a request over 16 MB. No conditions and no updates in a batch.

## Conditions, updates and locking

- Use `UpdateItem` with `SET`, `ADD`, `REMOVE` instead of get-then-put; it changes only named attributes and can carry a condition.
- **Insert if absent**: `conditionExpression("attribute_not_exists(#pk)")`. **Compare and set**: `"#version = :expected"` then `SET #version = :next`.
- `ConditionalCheckFailedException` is the expected outcome of a lost race, not an error to retry blindly. Set `returnValuesOnConditionCheckFailure(ALL_OLD)` to read the current item from the exception without another read.
- `ReturnValues`: `ALL_NEW` or `UPDATED_NEW` returns the result of an update without a second read (useful for counters and read-your-write). `PutItem` and `DeleteItem` support only `NONE` and `ALL_OLD`.
- Atomic counters (`ADD #n :one`) are not idempotent: an SDK retry after a timeout can count twice.
- **Enhanced optimistic locking**: `VersionedRecordExtension` and `AtomicCounterExtension` load by default; passing your own `.extensions(...)` replaces the defaults, so add them back. `@DynamoDbVersionAttribute` on a `Long`/`Integer` getter makes each put and update conditional on the version. `deleteItem` ignores the version: add a `conditionExpression` yourself.

## Transactions

- `transactWriteItems`: up to 100 actions on 100 distinct items, 4 MB in total; the same item can't appear twice (no `ConditionCheck` plus `Update` on one item). Each item costs two writes (prepare and commit), also when the transaction is cancelled. `transactGetItems`: up to 100 gets.
- `clientRequestToken`: makes a retried call idempotent for 10 minutes; reusing a token with different parameters fails with `IdempotentParameterMismatchException`.
- On `TransactionCanceledException`, read `cancellationReasons()`: `ConditionalCheckFailed` is a business outcome; `TransactionConflict` can be retried with backoff.
- Transactions can't target indexes, and aren't atomic across global-table regions.

## TTL types

```java
item.put("expiresAt", AttributeValue.fromN(Long.toString(expiry.getEpochSecond())));   // right
item.put("expiresAt", AttributeValue.fromN(Long.toString(expiry.toEpochMilli())));     // wrong: ~year 57,000, never expires
item.put("expiresAt", AttributeValue.fromS(expiry.toString()));                        // wrong: strings are ignored
```

- Enhanced Client: map the TTL attribute to `Long` epoch seconds (or an `Instant` with a converter that writes seconds as a Number; the default `Instant` converter writes an ISO **string**, which TTL ignores).
- Reads that must not see expired items: `filterExpression("#exp > :now")` with `:now` in epoch seconds, or check in code after a `getItem`.
- Other expiry fields kept in milliseconds for business logic are fine; only the TTL attribute must be seconds. Mixing units in one class is a readability finding.

## Tests

- **DynamoDB Local** (`amazon/dynamodb-local` image, port 8000; `-inMemory` for tests) through **Testcontainers** (`GenericContainer` with that image, or the community DynamoDB module) or LocalStack. Point the client at it with `endpointOverride`, a fixed region and static dummy credentials (letters and digits only).
- Create tables from the same code or IaC-derived definitions production uses, so a key or index mismatch fails the test.
- Force pagination with a small `limit` and more items than one page; assert all come back.
- Race test: two writers update the same version; assert one gets `ConditionalCheckFailedException`.
- Mocked-client tests (Mockito on `DynamoDbClient`) when there's no container: capture the request with an `ArgumentCaptor` and assert `keyConditionExpression`, `indexName`, `projectionExpression`, `consistentRead`, `conditionExpression`; return `unprocessedItems` once and assert the second call re-sends them.
- DynamoDB Local ignores throughput, runs parallel scans sequentially, never throws `TransactionConflictException`, makes indexes `ACTIVE` at once and returns reads that look strongly consistent (GSI lag never shows); simulate those with a mocked client.

## boto3

- `boto3.resource('dynamodb').Table(name)` or `boto3.client('dynamodb')`; create once per process (module level or a cached factory), not per Lambda invocation or request.
- `Key('pk').eq(x) & Key('sk').between(a, b)` for key conditions; `Attr(...)` builds filters.
- `table.batch_writer()` re-sends unprocessed items itself; `overwrite_by_pkeys=[...]` de-duplicates keys within a batch. Raw `client.batch_write_item` needs the `UnprocessedItems` loop.
- Pagination: `client.get_paginator('query')`; the resource's `table.query` returns one page (loop on `LastEvaluatedKey`).
- Numbers come back as `decimal.Decimal`; `int(time.time())` for TTL (not a float, not milliseconds).
- Timeouts and retries: `botocore.config.Config(connect_timeout=..., read_timeout=..., retries={'mode': 'standard', 'max_attempts': ...})`.

## JavaScript SDK v3

- `DynamoDBDocumentClient.from(new DynamoDBClient({...}))` from `@aws-sdk/lib-dynamodb`, created once at module scope.
- `paginateQuery({ client }, input)` / `paginateScan` with `for await (const page of ...)`; a single `QueryCommand` returns one page.
- `BatchWriteCommand` returns `UnprocessedItems`; AWS's own example chunks to 25 and doesn't check it, so copied code often drops items.
- TTL: `Math.floor(Date.now() / 1000)`; `Date.now()` alone is milliseconds.
- Timeouts: `requestHandler` with `requestTimeout` and `connectionTimeout`; `maxAttempts` and `retryMode` on the client.
