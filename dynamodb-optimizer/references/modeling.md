# Modeling

How DynamoDB schemas are meant to be designed, so a review can tell a schema that fits its access patterns from one that fights them.

## Access patterns first

- Relational design starts from entities and normalises; DynamoDB design starts from the **access patterns**: list every read and write, its keys, its frequency and its latency need, then pick keys and indexes so each frequent pattern is one `GetItem` or one `Query`.
- Design around data size, shape and velocity. Keep the number of tables small; separate tables are justified for high-volume time series and for data sets with very different access patterns.
- In a review, rebuild the access-pattern table from the code (Phase 1 of the skill) and compare it with the keys. Each row that needs a `Scan`, a filter on a key-like attribute or a fetch per result is a mismatch.
- NoSQL Workbench's data modeler does the same on paper: define tables and GSIs, define access patterns as real operations, check them against sample data, then commit the model to DynamoDB Local or an account. Suggest it for a redesign; it is not needed for a review.

## Partition keys

- The partition key spreads data and traffic. Each partition serves at most 3,000 read units and 1,000 write units per second; one hot key can't go past that, however much capacity the table has. Adaptive capacity moves throughput to hot partitions automatically (and isolates a hot item), but it can't raise one key above the per-partition limit, and it doesn't split item collections on a table with an LSI.
- Good keys have many distinct values requested fairly evenly: user id, device id, order id. Bad keys on hot paths: status, type, a date, a boolean, a tenant that dominates traffic.
- Burst capacity keeps up to 300 seconds of unused capacity; it hides spikes, not a design problem.

### Write sharding

When the natural key is low-cardinality (all of today's events) and writes are heavy, add a suffix:

- **Random suffix** (`2026-11-25.1` … `2026-11-25.200`): spreads writes evenly, but reading one item needs all suffixes queried and merged.
- **Calculated suffix** (`hash(orderId) % 200 + 1`): spreads writes and still allows `GetItem` when the id is known. Reading the whole day still queries every suffix (a bounded parallel fan-out).

Sharding is a key change: a new table or index and a migration. Recommend it only with numbers showing the key exceeds or approaches the per-partition limit.

## Sort keys

- The sort key orders an item collection and is what range conditions act on: `=`, `<`, `<=`, `>`, `>=`, `BETWEEN`, `begins_with`. Without a sort-key condition a query reads the whole collection.
- Hierarchies: `country#region#state#city` lets `begins_with` query any level.
- Time: an ISO-8601 UTC timestamp (or a zero-padded number) as the sort key, often with an id suffix for uniqueness (`2026-11-25T10:00:00Z#a1b2`), so "last 30 days" is a `BETWEEN` and "latest N" is `ScanIndexForward=false` with `Limit N`.
- Versions: keep the latest as `v0_<id>` and history as `v1_`, `v2_` … under the same partition key; query `begins_with(v0_)` for current state.
- Strings sort by UTF-8 bytes and numbers numerically: zero-pad numeric parts of string keys.

## Secondary indexes

| | GSI | LSI |
|---|---|---|
| Keys | Any partition and sort key (top-level String, Number or Binary) | Same partition key, different sort key |
| When | Any time; created online with a backfill | Only at table creation; can't be removed except by deleting the table |
| Throughput | Its own; a throttled GSI throttles base-table writes (back-pressure) | Shares the table's |
| Consistency | Eventually consistent only | Strong or eventual |
| Size limit | None per key | 10 GB per partition key value, table plus all LSIs |
| Per table | 20 (adjustable) | 5 |

- **Prefer a GSI** unless the pattern needs strongly consistent reads on an alternate sort key and every partition key's items will stay well under 10 GB.
- **Projections**: `KEYS_ONLY`, `INCLUDE` (named attributes; at most 100 across all indexes) or `ALL`. `ALL` roughly doubles storage and write cost. A GSI query can't fetch non-projected attributes; an LSI query can, at extra read cost. Project what the queries on the index read, nothing more. Projections can't be changed after creation.
- **Write cost**: every base-table write that changes an indexed attribute writes each affected index too (an update that changes an index key is a delete plus a put in the index). Index entries round up to 1 KB.
- **Sparse indexes**: an item appears in a GSI only if it has all of the index's key attributes. Write the key attribute only while the item is in an interesting state (an open order, an unsent notification) and remove it after; the index then holds only those items, is small, and needs little capacity.
- **Overloading**: one GSI can serve several item types if a generic attribute (for example `GSI1PK`, `GSI1SK`, or the sort key reused as the index's partition key) holds a different meaning per type. Useful in single-table designs; confusing elsewhere.
- **Adding a GSI** is online: DynamoDB backfills it, and base-table writes can throttle during the backfill if the index has too little write capacity. Readers must wait until the index is `ACTIVE`.
- **Removing a GSI** breaks any reader still using it; remove readers first, in an earlier release.

## Large items

- Items are capped at 400 KB (larger writes fail with `ValidationException`), and read and write cost scale with size.
- Options: compress large attributes (GZIP into Binary; the attribute can no longer be filtered on), split into several items under the same partition key (vertical partitioning: a summary item read often, detail items read rarely), or store the object in S3 and keep its key. There is no transaction across S3 and DynamoDB: write the S3 object first, then the item, and clean up orphans.

## Time series

- One table per period (per day or month), created ahead; the current table gets the throughput, older ones drop to minimal capacity or move to the Standard-IA table class (cheaper storage, dearer reads), then get archived or dropped. TTL is the simpler alternative when old data is simply deleted.
- Sharding combines with this when the current period is write-hot.

## Many-to-many and graphs

- **Adjacency list**: the partition key is the entity; relationship items under it have the related entity's id as the sort key. A GSI on the sort key gives the reverse lookup.
- **Materialised graph**: a `Type#Target` sort key and a GSI on it. Multi-hop graph queries belong in a graph database (Neptune).

## Relational data and uniqueness

- No joins: denormalise and use composite keys so one request returns what a screen needs. `TransactWriteItems` (up to 100 items) keeps denormalised copies consistent where that matters.
- Uniqueness of a non-key attribute (email, username, an external id): a separate claim item keyed by that value, written with `attribute_not_exists` in the same transaction as the main item. A query-then-write check races.

## Single-table design: trade-offs

- **For**: several item types in one item collection come back in one `Query` (a customer and their orders); fewer tables to operate. Rick Houlihan's re:Invent talks and Alex DeBrie's *The DynamoDB Book* (foreword by Houlihan) popularised it, and AWS's table-design guidance recommends few tables.
- **Against** (DeBrie): steep learning curve; rigid when access patterns change; harder analytics and export; little gain for a new, fast-changing app or for GraphQL, whose resolvers fetch separately anyway.
- **In a review**: don't recommend merging working tables into one for its own sake. Recommend single-table only where a hot pattern now makes several round trips for data that is always read together. Recommend splitting where unrelated entities share a table with no shared reads and the overloaded keys confuse readers.
- Multi-table with one GSI per extra pattern is a sound default for a service with a handful of entities.

## Streams, outbox and global tables

- Streams keep 24 hours of change records, exactly once per record, ordered per item (not across items). No record for a write that changes nothing. At most two readers per shard; more throttle. A transaction's records can arrive at different times, interleaved.
- **Outbox**: to publish an event reliably with a state change, write the change (and, if needed, an outbox item in the same transaction) and let a Streams consumer publish it, instead of writing to DynamoDB and calling a broker in the same request (one can succeed while the other fails).
- TTL deletes appear in the stream as service deletes (`userIdentity.type = "Service"`, `principalId = "dynamodb.amazonaws.com"`); a Lambda event filter can select only them, for archiving.
- **Global tables**: multi-Region eventual (MREC, the default) resolves conflicts last-writer-wins and doesn't run transactions across regions; multi-Region strong (MRSC) gives strongly consistent reads in any replica, same account only, chosen at creation. Code that relies on conditional writes for correctness needs one write region per item, or MRSC.
