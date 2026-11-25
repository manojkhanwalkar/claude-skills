# Checklist by focus area

Signs to grep for, and the question that confirms each. A grep hit is a lead, not a finding: read the call and its caller first. The basics are also in `perf-review/references/data-access.md`; this list goes further.

## Finding the calls

```bash
# Java SDK v2 (low-level and Enhanced), boto3, JS SDK v3
grep -rnE '\.(getItem|query|scan|batchGetItem|batchWriteItem|transactWriteItems|transactGetItems|putItem|updateItem|deleteItem)\(' --include=*.java --include=*.kt .
grep -rnE 'queryPaginator|scanPaginator|PageIterable|\.items\(\)|lastEvaluatedKey|exclusiveStartKey' --include=*.java .
grep -rnE '\.(get_item|query|scan|batch_get_item|batch_write_item|transact_write_items|put_item|update_item|delete_item|batch_writer)\(' --include=*.py .
grep -rnE '(Query|Scan|BatchGet|BatchWrite|TransactWrite|Put|Update|Delete|Get)(Item)?Command|paginateQuery|paginateScan' --include=*.ts --include=*.js .
# table definitions
grep -rnE 'createTable|CreateTableRequest|updateTimeToLive|AWS::DynamoDB::Table|aws_dynamodb_table|new (dynamodb\.)?Table(V2)?\(|globalSecondaryIndex|GlobalSecondaryIndexes|LocalSecondaryIndexes|TimeToLiveSpecification|ttl \{' .
```

Skip `target/`, `build/`, `node_modules/` and generated code.

## keys

- Partition key with few distinct values (status, type, a date, a boolean, one tenant id for most traffic) on a write or read path that runs often → hot partition (each partition: 3,000 RCU and 1,000 WCU per second). Confirm with the expected rate per key value.
- A key that is a timestamp truncated to a day or hour on a write path → all writes for that period hit one partition. Shard with a calculated suffix (`modeling.md`).
- One partition key that collects items without bound (an event log per user forever) → large item collections and slow queries; with an LSI on the table, a hard 10 GB stop (`ItemCollectionSizeLimitExceededException`).
- Sort key that holds a value the code filters on with a range (`createdAt`, a version, a path) but the code uses a `FilterExpression` instead → key condition.
- Composite sort keys built by string concatenation: check the separator can't appear in the parts, numbers are zero-padded (strings sort by UTF-8 bytes: `"10" < "9"`), and timestamps are ISO-8601 UTC or fixed-width.
- Numbers as strings in keys where numeric order matters, or the reverse.

## indexes

- For every GSI and LSI in the inventory, find a `query` that names it (`indexName`, `index(...)`, `IndexName=`). None → unused (write and storage cost on every write).
- For every query on an index, list the attributes the code reads from the results. Projection `ALL` while every reader needs keys plus one or two attributes → `INCLUDE` or `KEYS_ONLY` (a new index; projections can't be changed).
- A GSI query followed by `getItem` per result to fetch missing attributes → either project those attributes or accept it knowingly (N+1).
- An LSI: does any query need strongly consistent reads on it? Can any partition key's items grow past 10 GB? LSIs can't be added or removed after creation. No and maybe → a GSI would have served.
- "All items in state X" patterns (unsent, pending, open, flagged) read by scan or by a GSI keyed on a status → sparse GSI: write the GSI key attribute only while the item is in state X, remove it after.
- GSI on a low-cardinality partition key (status, type) → hot index partition; back-pressure from a throttled GSI throttles the base table's writes.
- Code expecting a GSI read to see a write just made → correctness bug (GSIs are eventually consistent).

## queries

- `query`/`scan` with no loop on `LastEvaluatedKey` and no paginator, returning a list to the caller → truncation (High). A single page is fine only when it is deliberate (a UI page with a cursor returned, or `Limit 1` for "latest").
- `.stream()` on a paginator (pages) where `.items()` was meant, or `Limit` used as "max results" (it is items evaluated per page, before the filter).
- `scan` anywhere on a request path (High if hot, Medium if warm). `scan` in a batch job: is a query or a sparse index possible? Is it paged, rate-limited, and does it page through the whole table?
- `FilterExpression` on an attribute that could be the sort key, or that could become a GSI key. Filters don't reduce read units; pages can come back empty with a `LastEvaluatedKey`.
- No `ProjectionExpression` on reads of large items where a few attributes are used.
- `getItem` in a loop → `batchGetItem` (up to 100 keys, 16 MB), retrying `UnprocessedKeys`.
- `batchWriteItem` (up to 25 puts or deletes, 16 MB) with no loop on `UnprocessedItems`, or a loop with no backoff, or no bound → High / Medium.
- Duplicate keys in one batch → whole batch rejected (`ValidationException`).
- Count via scan (`Select.COUNT` over the table) on a request path → a counter item updated atomically.

## ttl

- TTL attribute values: `toEpochMilli()`, `System.currentTimeMillis()`, `Date.now()` (JS ms), `time.time()` as float, an ISO string, or `fromS(...)` → wrong (must be a Number in epoch **seconds**; anything else is ignored and the item never expires).
- TTL enabled in IaC or `updateTimeToLive`? Same attribute name as the code writes? A code-created table that sets TTL only in tests or only locally is a finding for production IaC.
- Every read path where an expired item must not be served (sessions, one-time codes, tokens, holds, offers): does it compare the TTL attribute (or an expiry field) with now? Deletion can lag by days.
- Updates to an item that may have expired: condition on the TTL attribute, or the update revives a dead item.
- Streams consumers: do they distinguish TTL deletes (`userIdentity.type = "Service"`, `principalId = "dynamodb.amazonaws.com"`) from user deletes where it matters (audit, archive)?
- Enabling TTL on an existing table deletes items already past their expiry (up to five years back): check before enabling.

## capacity

- Client built per call or per request (`DynamoDbClient.create()`, `builder()...build()`, `boto3.client(...)`, `new DynamoDBClient(...)` inside a method) → one shared client.
- Enhanced `TableSchema.fromBean`/`fromImmutableClass` built per call (reflection) → build once.
- No `apiCallTimeout` / `apiCallAttemptTimeout` (the SDK sets none) → point to `resiliency`.
- Retry mode: legacy (pre-2.58.0 default, 9 attempts for DynamoDB) or custom unbounded retries; standard and adaptive make 4 attempts. Note it; `resiliency` owns the change.
- Provisioned mode without auto scaling on spiky traffic, or on-demand on a steady, high, predictable load → note for "Needs a decision" with the arithmetic (`costs.md`).
- DAX: only for read-heavy, eventually consistent, repeated reads (hit rate above about 90%); not for write-heavy or strongly consistent work. Top-level attribute names that are unbounded (timestamps or ids as names) exhaust DAX memory.
- Parallel scan on a small table, or more than one segment per about 2 GB, or on a request path.

## consistency

- `consistentRead(true)` / `ConsistentRead=True`: is the item written earlier in the same flow, and does the flow break if it reads the old value? No → eventual (half the RCU).
- The reverse: a write then an eventual read in the same request (or a GSI read) that drives a decision (balance, one-time code, idempotency check) → strongly consistent base-table read, or use `ReturnValues` from the write.
- Global tables (MREC): last writer wins across regions; conditional writes protect only within a region; transactions aren't atomic across regions.

## transactions

- `transactWriteItems` with one item, or with items that don't need all-or-nothing → a conditional single write (transactions cost two writes per item, also when cancelled).
- Uniqueness across attributes (one email per account) done by query-then-write → race; use a claim item (`PK = EMAIL#...`) written with `attribute_not_exists` in a transaction with the main item.
- `TransactionCanceledException` handled as one error: read `cancellationReasons` to tell a condition failure (a business outcome) from a conflict (retry with backoff).
- No `clientRequestToken` on a transaction the caller retries → a retry after a timeout may apply twice when it includes non-idempotent updates.
- Atomic counters (`ADD`, `SET x = x + :n`) retried by the SDK or the caller → over- or under-counting; acceptable for approximate counts only.
- Optimistic locking: Enhanced Client's `VersionedRecordExtension` is on by default, but only for classes with `@DynamoDbVersionAttribute`, and `deleteItem` ignores it. Passing your own `.extensions(...)` turns the defaults off.
- Failed conditional writes still consume WCU; catching `ConditionalCheckFailedException` to implement "insert if absent" is fine, but in a hot loop it costs.

## cost

- Item sizes: attributes holding documents, reports, images or long JSON → S3 with a pointer, or a separate item. Items near 400 KB fail with `ValidationException` when they grow.
- Long attribute names on very large tables: names count toward item size on every item and every index entry.
- `ALL` projections and unused GSIs (each GSI write costs WCU, rounded up to 1 KB per entry).
- Old time-series data on Standard storage, read rarely → Standard-IA table class, or archive to S3 (`modeling.md`).
- Scans in scheduled jobs: units per run × runs per month.

## tests

- Do tests run against DynamoDB Local, Testcontainers (`amazon/dynamodb-local`) or LocalStack, or only mocks? Mocks can't catch a wrong key condition, a missing condition expression or a reserved word.
- Is there a test with more than one page of results (set `Limit` small to force pages)?
- Is there a test where a conditional write fails (two writers, a stale version)?
- Is there a test that an expired-but-present item is not returned?
- Is there a test that unprocessed batch items are re-sent (a mocked client returning `UnprocessedItems` once)?
- DynamoDB Local differences: no throughput limits, `Segment`/`TotalSegments` ignored, no `TransactionConflictException`, table names case-insensitive. Don't rely on it for those.
