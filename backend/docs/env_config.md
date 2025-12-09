# Environment / .env configuration

ECE_Core uses pydantic BaseSettings configured in `src/config.py` to load service parameters from a `.env` file or from the environment. The following settings are commonly used and can be set in your `.env` using uppercase underscore-separated keys (Pydantic maps `weaver_candidate_limit` -> `WEAVER_CANDIDATE_LIMIT`):

- WEAVER_CANDIDATE_LIMIT: candidate limit per summary used by repair scripts (default 200)
- WEAVER_BATCH_SIZE_DEFAULT: default batch size used by the MemoryWeaver and repair scripts (default 2)
- LLM_EMBEDDINGS_CHUNK_SIZE_DEFAULT: char-based chunk size used for chunking long documents (default 2048)
- LLM_EMBEDDINGS_DEFAULT_BATCH_SIZE: number of document embeddings requested per API call (default 2)
- LLM_EMBEDDINGS_API_BASE: embeddings API base URL (default http://127.0.0.1:8081/v1)
- LLM_API_BASE: general LLM API base URL (default http://localhost:8080/v1)
- NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD: configuration for Neo4j
- REDIS_URL: redis server URL
- ECE_HOST, ECE_PORT: server host & port

Tips:
- Set `LLM_EMBEDDINGS_DEFAULT_BATCH_SIZE` and `LLM_EMBEDDINGS_CHUNK_SIZE_DEFAULT` to small values for local, lower-resource embedding servers to avoid 500 errors.
- You can also override behavior at runtime using CLI args for scripts like `scripts/weave_recent.py` (`--llm-embeddings-chunk-size`, `--llm-embeddings-batch-size`, `--candidate-limit`). If CLI args are not present, the settings from `.env` are used.

Example `.env` file:
```
WEAVER_CANDIDATE_LIMIT=200
WEAVER_BATCH_SIZE_DEFAULT=2
LLM_EMBEDDINGS_CHUNK_SIZE_DEFAULT=2048
LLM_EMBEDDINGS_DEFAULT_BATCH_SIZE=2
LLM_EMBEDDINGS_API_BASE=http://127.0.0.1:8081/v1
LLM_API_BASE=http://localhost:8080/v1
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=some-secret
REDIS_URL=redis://127.0.0.1:6379
ECE_HOST=127.0.0.1
ECE_PORT=8000
```

If you have a particular setting you'd like added to `src/config.py` as a `.env`-driven value, please let me know and I will add it.
