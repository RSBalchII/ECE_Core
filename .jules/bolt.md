## 2024-05-18 - [N+1 Query Bottleneck in Search Service]
**Learning:** Found an N+1 query issue in `enrichAtomsWithMoleculeTags` where a separate SQL query was being executed for each `compound_id`.
**Action:** When working with nested loops or arrays that require data fetching, always look for opportunities to batch queries. Used `SELECT ... WHERE compound_id = ANY($1)` to fetch all molecule tags in a single query, significantly improving performance.
## 2025-03-09 - [Sequential Queries in Search Path and TagAuditor]
**Learning:** Found sequential independent asynchronous database/processing calls in the critical path of `_executeSearchInternal` (executing engram lookups before primary anchor searches) and `getTagStatistics` in `TagAuditor` (fetching total statistics before orphan statistics).
**Action:** When working with multiple independent await calls, always identify if they can be executed concurrently using `Promise.all` to prevent event loop blocking and reduce latency. Refactored both instances to run concurrently.
