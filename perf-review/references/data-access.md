# Data access

Every round trip to a store costs network time plus the store's work. On a hot path, count round trips per request first; most data-access findings are "too many calls" or "too much data per call".

## N+1

- **Shape**: one call returns N things, then one call per thing. Each call is fast, so slow-query logs don't flag it; the cost is N round trips.
- **JPA/Hibernate**: `@ManyToOne` and `@OneToOne` are eager by default and still N+1 when a JPQL query doesn't `JOIN FETCH` them; `LAZY` associations accessed in a loop are N+1 too. Fix with `JOIN FETCH`, an entity graph, or `@BatchSize`; the query cache stores only IDs, so uncached entities are still fetched one by one.
- **Across services**: a client call per item in a loop. Fix with a bulk endpoint, or a bounded parallel fan-out when no bulk API exists.
- **Prove it**: a test that counts calls (a Mockito spy on the repository or client, Hibernate statistics, a DynamoDB client interceptor) and asserts the batched count.

## Batching

- Batch independent reads and writes, within the store's limits, and keep per-item error handling.
- SQL: `IN (...)` with a bounded list; JDBC batch inserts (`hibernate.jdbc.batch_size`, `reWriteBatchedInserts` for PostgreSQL).
- Batch sizes are a trade-off: too large holds locks and memory, too small keeps the round trips.

## Pagination and limits

- Every list query on a request path has a limit, and every list API pages.
- `OFFSET n` makes the database read and discard n rows, and shifts when rows are inserted between pages; use keyset (seek) pagination: `WHERE (sort_key, id) < (?, ?) ORDER BY sort_key DESC, id DESC FETCH FIRST 20 ROWS ONLY`. Keyset can't jump to page 37; most UIs don't need it.
- Return only the columns needed (projections, DTO queries); `SELECT *` and whole entities pull large columns nobody reads.

## Indexes (SQL)

- A query on a request path filters and sorts on indexed columns; check with `EXPLAIN`. A function on an indexed column (`lower(email)`) needs a matching expression index.
- Every index slows writes; adding one is a schema change for "Needs a decision" with the query and its plan.

## DynamoDB

### Query, not Scan

- A `Scan` reads the whole table or index and filters afterwards; a 1 MB page of 4 KB items costs about 128 read units eventually consistent (256 strongly). On a request path it is Medium at least. Use `GetItem`, `Query` on the partition key, `BatchGetItem`, or a GSI keyed for the access pattern.
- `FilterExpression` is applied after the read: you pay for what you filter out, and a page can come back empty with a `LastEvaluatedKey`. If a filter does a key's job, the key design is wrong for this access pattern.
- Parallel scans are for offline jobs on large tables (one segment per about 2 GB), never request paths.

### Pagination

- A `Query` or `Scan` page holds at most 1 MB; loop on `LastEvaluatedKey` → `ExclusiveStartKey` until it is absent (the SDK paginators do this). Code that reads only the first page silently truncates.
- `Limit` caps items read per page; use it for request-path pages and pass the key back to the client as an opaque cursor.

### Batch APIs

- `BatchGetItem`: up to 100 keys and 16 MB per request; no duplicate keys; results unordered. `BatchWriteItem`: up to 25 puts or deletes, no updates or conditions.
- Partial results come back as `UnprocessedKeys` or `UnprocessedItems`: retry them with exponential backoff (not immediately); code that ignores them loses data silently (a correctness finding).
- A batch saves round trips, not read units: each item still costs its read.

### Hot partitions and key design

- Each partition handles about 3,000 read units and 1,000 write units per second. One read unit is one strongly consistent read (or two eventually consistent) of up to 4 KB; one write unit is one write of up to 1 KB.
- A key that concentrates traffic (a date, a status, a global counter, one tenant) throttles however much capacity the table has; adaptive capacity helps but doesn't remove the limit. Fix with higher-cardinality keys or write sharding (a suffix), which is a data-model change.

### Read consistency

- Eventually consistent reads cost half as much and are the default; `ConsistentRead(true)` only where the read must see a write just made (read-your-own-write in the same flow). GSIs and streams are always eventually consistent; code that expects a GSI read to see a fresh write is a correctness bug.

### Item size and projections

- Items are capped at 400 KB, and read and write cost scales with item size (a 20 KB item costs 5 read units per strongly consistent read). Large, rarely read attributes (reports, documents) belong in S3 with a pointer in the item, or in a separate item under the same partition key; compression saves units but loses filtering.
- Use `ProjectionExpression` to return only needed attributes (it saves bandwidth and deserialisation, not read units).
- GSIs: each has its own throughput and copies the projected attributes on every write. `ALL` projections roughly double storage and write cost; project the keys and the few attributes the query needs. Index entries under 1 KB cost one write unit each.

### Clients

- One `DynamoDbClient` or `DynamoDbEnhancedClient` per application, shared; table schemas (`TableSchema.fromBean`) built once, since they use reflection.
- Close `ResponseInputStream`s; set call timeouts (see `resiliency`).
