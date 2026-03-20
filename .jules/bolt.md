## 2024-05-18 - [N+1 Query Bottleneck in Search Service]
**Learning:** Found an N+1 query issue in `enrichAtomsWithMoleculeTags` where a separate SQL query was being executed for each `compound_id`.
**Action:** When working with nested loops or arrays that require data fetching, always look for opportunities to batch queries. Used `SELECT ... WHERE compound_id = ANY($1)` to fetch all molecule tags in a single query, significantly improving performance.
## 2025-02-14 - Parallelizing N+1 queries with early exit boundaries
**Learning:** When parallelizing repetitive sequential I/O queries via `Promise.all`, blindly applying it to an entire chunk array causes dangerous over-fetching and severe performance regressions if the original loop has an early-exit boundary (like a `maxCount` cap) to prevent querying the entire dataset. In `engine/src/services/search/explore.ts`, converting the entire sequence to `Promise.all` removed this exit condition.
**Action:** Use batched chunking (e.g., executing 3 chunks concurrently in a batch inside a constrained loop) to dramatically increase throughput while respecting early-exit logic limits.
