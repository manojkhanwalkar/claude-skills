# Costs

Arithmetic for the "Evidence and estimate" column. State every input; label the result an estimate. Prices change and vary by region: take them from the project's design doc or the AWS pricing page at the time, and give units (RCU, WCU, GB) when no price is known.

## Units

- **Read**: 1 read unit = one strongly consistent read of up to 4 KB. Eventually consistent = 0.5 unit per 4 KB. Transactional = 2 units per 4 KB.
- **Write**: 1 write unit = one write of up to 1 KB. Transactional = 2 units per 1 KB.
- Sizes round **up**: a 4.1 KB strongly consistent read costs 2 units; a 1.1 KB write costs 2.
- **Query and Scan** sum the sizes of all items **read** (before the filter), then round up once per page: 40.8 KB → 44 KB → 11 units strongly consistent, 5.5 eventually. `ProjectionExpression` and `FilterExpression` don't reduce units.
- **BatchGetItem and BatchWriteItem** round **each item** separately: 1.5 KB + 6.5 KB reads = 4 KB + 8 KB = 3 units strongly consistent.
- **GetItem of a missing item** still costs 1 unit (0.5 eventual). A **failed conditional write** still costs the existing item's size in write units (at least 1).
- **GSI queries** are eventually consistent: up to 8 KB per read unit.
- **Index writes**: each write that touches an indexed attribute costs write units in every affected index too, entry rounded up to 1 KB; an update that changes an index key costs a delete plus a put there.

## Worked examples

| Pattern | Arithmetic | Units |
|---|---|---|
| Scan page, 1 MB, eventually consistent | 1,024 KB / 4 KB = 256 × 0.5 | 128 RCU per page |
| Scan of a 1 GB table to find one user's 3 items | 262,144 × 0.5 | about 131,000 RCU per call, whatever the filter keeps |
| Same pattern as a GSI `Query` (KEYS_ONLY, 3 entries of 100 B) | 300 B → 1 × 0.5 | 0.5 RCU |
| `Limit 40` query, 4 KB items, eventually consistent | 160 KB / 4 KB × 0.5 | 20 RCU |
| 20 KB item, strongly consistent `GetItem` | 20 / 4 = 5 | 5 RCU (eventual: 2.5) |
| Put of a 2.5 KB item with 2 GSIs projecting ALL | 3 + 3 + 3 | 9 WCU (KEYS_ONLY GSIs: 3 + 1 + 1 = 5) |
| Same put in a `TransactWriteItems` | 2 × 3 for the base item | 6 WCU, plus the index writes |
| Consistent → eventual on a 1,000 reads/s path, 4 KB items | 1,000 × (1 − 0.5) | saves 500 RCU/s |

## Capacity modes

- **On-demand** (the default and AWS's recommendation): pay per request, no planning; per-table default ceilings of 40,000 read and 40,000 write units per second apply. Good for spiky, unknown or low traffic.
- **Provisioned**: pay for units per hour whether used or not; cheaper for steady, predictable, high load, with auto scaling. A table at low utilisation is paying for idle capacity; one at high utilisation without auto scaling throttles on spikes.
- Recommending a mode switch is a "Needs a decision" item with the monthly arithmetic both ways from real or stated traffic.
- **Per partition**: 3,000 RCU and 1,000 WCU per second, whatever the mode. A 4 KB item read strongly 3,000 times a second, or a 1 KB item written 1,000 times a second, is at the limit.
- **Burst**: up to 300 seconds of unused capacity can absorb spikes; don't count on it.

## Storage

- Each item: attribute names plus values; each index entry: its keys plus projected attributes plus 100 bytes overhead. `ALL` projections roughly double storage and write cost.
- Standard-IA table class: cheaper storage, dearer reads and writes; fits large tables read rarely (old time-series periods).
- TTL deletes are free (no write units in the region that expires them; global-table replicas pay replicated writes).

## Latency

- A `GetItem` or small `Query` is single-digit milliseconds in-region; count round trips (calls × about 5–10 ms) for an estimate, and pages × that for a paginated read.
- DAX lowers eventually consistent read latency to microseconds for repeated reads; it adds a cluster to pay for and does nothing for writes or strongly consistent reads.
