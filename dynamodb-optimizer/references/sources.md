# Sources

Pages read on 2026-11-25 when this skill was written. Book contents and conference talks are cited through the public pages that describe them.

## Design and modeling (AWS DynamoDB Developer Guide)

- [Best practices for designing and architecting with DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html): the index of AWS's best-practice guides.
- [NoSQL design for DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html): identify access patterns before the schema; keep as few tables as possible.
- [Best practices for DynamoDB table design](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-table-design.html): keep the table count low; one table in most cases.
- [Data modeling for DynamoDB tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/data-modeling.html): simple and composite keys, high-cardinality partition keys, LSI versus GSI, single- versus multi-table.
- [Partition key design](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html): 3,000 RCU and 1,000 WCU per partition; unit sizes; adaptive capacity in both modes.
- [Write sharding](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html): random and calculated suffixes, and the read cost of each.
- [Sort keys](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-sort-keys.html): range operators, hierarchical composite keys, the version-control pattern.
- [General guidelines for secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html): 20 GSIs and 5 LSIs, ALL projections double cost, 1 KB index-entry rounding, item-collection monitoring.
- [Sparse indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general-sparse-indexes.html): items appear in a GSI only when they have its key attributes.
- [Overloading GSIs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-gsi-overloading.html): one GSI serving several item types through a generic attribute.
- [Local secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html): created only with the table, shared throughput, strongly consistent reads, 10 GB item-collection limit.
- [Global secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html): eventual consistency only, projections, write cost, back-pressure throttling, online creation.
- [Large items and attributes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html): 400 KB limit; compression, vertical partitioning or S3 pointers.
- [Time series data](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-time-series.html): a table per period, Standard-IA for old periods.
- [Many-to-many relationships](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-adjacency-graphs.html): adjacency lists, reverse lookup by GSI, materialised graphs.
- [Modeling relational data](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-relational-modeling.html): denormalisation, composite keys, transactions of up to 100 items.
- [NoSQL Workbench](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/workbench.html): data modeler for access patterns, operation builder, DynamoDB Local bundled.

## Reads, writes and capacity

- [Querying and scanning best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-query-scan.html): scan cost per 1 MB page, `Limit`, when parallel scan is worth it.
- [Paginating query results](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.Pagination.html): 1 MB pages, `LastEvaluatedKey`, empty pages with a filter.
- [Filter expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.FilterExpression.html): applied after the read; same read units with or without.
- [Key condition expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.KeyConditionExpressions.html): equality on the partition key; `<`, `BETWEEN`, `begins_with` on the sort key; ordering.
- [Scanning tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html): units by items evaluated, parallel scan segments.
- [Projection expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ProjectionExpressions.html): projections don't reduce read units; attribute-name placeholders.
- [Read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html): eventual by default, GSIs and streams eventual only, global-table modes.
- [Read and write operations](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html): 4 KB and 1 KB rounding, query versus batch rounding, failed conditional writes cost units.
- [Working with items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html): conditional writes, atomic counters (not idempotent), `ReturnValues`, batch limits.
- [BatchWriteItem API reference](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html): 25 requests, 16 MB, `UnprocessedItems` with exponential backoff, whole-batch rejections.
- [Transactions: how it works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html): 100 items, 4 MB, double cost, `ClientRequestToken` for 10 minutes, cancellation reasons.
- [Throughput capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html): on-demand (default) versus provisioned.
- [Burst and adaptive capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/burst-adaptive-capacity.html): 300 seconds of burst, hot-item isolation, no splitting with LSIs.
- [Service quotas](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ServiceQuotas.html): index counts, projected-attribute limit, per-table throughput defaults.
- [DynamoDB Accelerator (DAX)](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html): microsecond eventually consistent reads; not for writes or strong reads; attribute-name memory.

## TTL, streams and global tables

- [Using TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html): Number in epoch seconds, deletion within a few days, service deletes in streams. (`howitworks-ttl.html` serves the same page.)
- [Computing TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/time-to-live-ttl-before-you-start.html): epoch seconds; values more than five years in the past are ignored.
- [Streams and TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/time-to-live-ttl-streams.html): the `userIdentity` of TTL deletes and a Lambda filter for them.
- [Change data capture for DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html): 24-hour retention, exactly-once records, per-item ordering, two readers per shard.
- [Global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html): MREC and MRSC, last writer wins, no cross-region transactions.

## SDKs

- [SDK for Java 2.x: Enhanced Client](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/dynamodb-enhanced-client.html): object mapping, successor of `DynamoDBMapper`, Enhanced Document API.
- [Enhanced Client: paginated scans and queries](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/ddb-en-client-use-multirecord.html): `PageIterable`, `.items()`, `QueryConditional`.
- [Enhanced Client extensions](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/ddb-en-client-extensions.html): versioning and atomic counters by default, custom extensions replace defaults, delete ignores the version.
- [SDK for Java 2.x best practices](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/best-practices.html): share clients, close streams, no default call timeouts.
- [SDK for Java 2.x retry strategy](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/retry-strategy.html): standard default since 2.58.0, 4 attempts for DynamoDB (legacy 9).
- [SDK for Java 2.x pagination](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/pagination.html): `queryPaginator(...).items()`, request `limit`.
- [Boto3 DynamoDB guide](https://docs.aws.amazon.com/boto3/latest/guide/dynamodb.html): resource interface, `Key`/`Attr` conditions, `batch_writer` resends unprocessed items.
- [SDK for JavaScript v3 DynamoDB examples](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/javascript_dynamodb_code_examples.html): `DynamoDBDocumentClient`, `paginateQuery`; its batch example doesn't check `UnprocessedItems`.

## Testing

- [DynamoDB Local setup](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html): port 8000, `-inMemory`, `-sharedDb`.
- [DynamoDB Local usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.UsageNotes.html): differences from the service (throughput ignored, sequential parallel scan, no transaction conflicts).
- [Testcontainers DynamoDB module](https://testcontainers.com/modules/dynamodb/): the `amazon/dynamodb-local` image.
- [Testcontainers LocalStack module](https://java.testcontainers.org/modules/localstack/): endpoint override and credentials; LocalStack now needs an auth token.

## Single-table design

- [Alex DeBrie, The What, Why, and When of Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table/): one request for related items; downsides (learning curve, rigidity, analytics); when not to use it; Rick Houlihan's position.
- [Alex DeBrie, The DynamoDB Book](https://www.dynamodbbook.com/): data modeling strategies with worked examples; foreword by Rick Houlihan.
