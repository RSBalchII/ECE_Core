import asyncio
import pytest
from src.vector_adapters.redis_vector_adapter import RedisVectorAdapter
from src.memory import TieredMemory
from src.config import settings
import importlib


@pytest.mark.asyncio
async def test_redis_vector_adapter_basic_flow():
    adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")  # invalid port to force in-memory fallback
    await adapter.initialize()

    # Health should be True (in-memory fallback)
    assert await adapter.health() is True

    a_id = "a"
    b_id = "b"
    c_id = "c"

    a_emb = [1.0, 0.0, 0.0]
    b_emb = [0.0, 1.0, 0.0]
    c_emb = [0.9, 0.1, 0.0]

    await adapter.index_chunk(a_id, node_id="node_a", chunk_index=0, embedding=a_emb, metadata={"source": "test"})
    await adapter.index_chunk(b_id, node_id="node_b", chunk_index=0, embedding=b_emb, metadata={"source": "test"})
    await adapter.index_chunk(c_id, node_id="node_c", chunk_index=0, embedding=c_emb, metadata={"source": "test"})

    # Query with a vector close to 'a'
    hits = await adapter.query_vector([1.0, 0.0, 0.0], top_k=3)
    assert len(hits) >= 1
    # Expect the top hit to be either 'a' or 'c' (closest to a_emb)
    top = hits[0]
    assert top["embedding_id"] in {a_id, c_id}
    # Ensure metadata and node_id are returned
    assert "metadata" in top and top["metadata"]["source"] == "test"

    # Test get
    get_a = await adapter.get(a_id)
    assert get_a["node_id"] == "node_a"
    assert get_a["embedding"] == a_emb

    # Test delete
    await adapter.delete(a_id)
    assert await adapter.get(a_id) is None


@pytest.mark.asyncio
async def test_redis_vector_adapter_with_client_paths():
    adapter = RedisVectorAdapter(redis_url="redis://localhost:6379")

    # Create a fake redis client with necessary async methods
    class FakeRedisClient:
        def __init__(self):
            self.store = {}
            self.index = set()

        async def ping(self):
            return True

        async def hset(self, key, mapping):
            self.store[key] = mapping

        async def sadd(self, key, value):
            self.index.add(value)

        async def smembers(self, key):
            return list(self.index)

        async def hgetall(self, key):
            return self.store.get(key) or {}

        async def srem(self, key, value):
            self.index.discard(value)

        async def delete(self, key):
            if key in self.store:
                del self.store[key]

    adapter.client = FakeRedisClient()
    await adapter.initialize()  # doesn't try to connect, just returns because client exists

    await adapter.index_chunk("x1", node_id="node_x", chunk_index=0, embedding=[1, 0, 0], metadata={"source": "r"})
    await adapter.index_chunk("x2", node_id="node_y", chunk_index=0, embedding=[0, 1, 0], metadata={"source": "r"})

    hits = await adapter.query_vector([1, 0, 0], top_k=2)
    assert hits[0]["embedding_id"] in {"x1", "x2"}

    get_x1 = await adapter.get("x1")
    assert get_x1["node_id"] == "node_x"

    await adapter.delete("x1")
    assert await adapter.get("x1") is None


@pytest.mark.asyncio
async def test_tieredmemory_index_embedding_for_memory(monkeypatch):
    # Enable vector in settings and ensure TieredMemory picks an adapter
    settings.vector_enabled = True
    settings.vector_adapter_name = "redis"
    mem = TieredMemory()
    # Force vector adapter to in-memory fake redis
    mem.vector_adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")
    await mem.vector_adapter.initialize()

    embedding = [0.7, 0.3]
    emb_id = await mem.index_embedding_for_memory("session-xyz", embedding, metadata={"note": "test"})
    assert emb_id is not None
    # check that adapter has this embedding by listing internal store
    stored = await mem.vector_adapter.get(emb_id)
    assert stored is not None and stored["embedding"] == embedding


@pytest.mark.asyncio
async def test_tieredmemory_add_memory_indexes_embedding(monkeypatch):
    settings.vector_enabled = True
    mem = TieredMemory()

    # Fake Neo4j driver to skip DB write and still run add_memory logic
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run(self, *args, **kwargs):
            return None

    class FakeDriver:
        def session(self):
            return FakeSession()

    mem.neo4j_driver = FakeDriver()
    mem.vector_adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")
    await mem.vector_adapter.initialize()

    embedding = [0.4, 0.6]
    await mem.add_memory(session_id="test-sess", content="hello", category="note", metadata={"embedding": embedding})

    # There should be at least one vector indexed in the adapter
    # Since we generated ID using timestamp-based composite, query by similarity
    hits = await mem.vector_adapter.query_vector(embedding, top_k=5)
    assert len(hits) >= 1
    assert hits[0]["score"] > 0


@pytest.mark.asyncio
async def test_tieredmemory_add_memory_auto_embedding(monkeypatch):
    settings.vector_enabled = True
    mem = TieredMemory()

    # Fake Neo4j driver so add_memory doesn't fail
    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def run(self, *args, **kwargs):
            return None
    class FakeDriver:
        def session(self):
            return FakeSession()
    mem.neo4j_driver = FakeDriver()

    # Fake llm that returns a deterministic embedding for content
    class FakeLLM:
        async def get_embeddings(self, text):
            return [[0.2, 0.8]]

    mem.vector_adapter = RedisVectorAdapter(redis_url="redis://localhost:9999")
    await mem.vector_adapter.initialize()

    fake_llm = FakeLLM()
    await mem.add_memory(session_id="sess-auto", content="hello auto", category="note", metadata=None, llm_client=fake_llm)

    # query to check vector indexed
    hits = await mem.vector_adapter.query_vector([0.2, 0.8], top_k=3)
    assert len(hits) >= 1


def test_neo4j_index_embeddings_dry_run():
    # Just import the script and run main with dry-run via command line args simulation
    import sys
    from scripts import neo4j_index_embeddings as script
    # Monkeypatch settings to force dry run and limit small
    # We won't call main() to avoid starting asyncio event, instead test run() with loop
    async def run_once():
        await script.run(limit=1, dry_run=True)
    asyncio.get_event_loop().run_until_complete(run_once())


@pytest.mark.asyncio
async def test_llm_client_get_embeddings_api(monkeypatch):
    from src.llm import LLMClient
    client = LLMClient()

    class FakeResp:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            return None
        def json(self):
            return self._data

    async def fake_post(url, json):
        return FakeResp({"data": [{"embedding": [1.0, 2.0, 3.0]}]})

    monkeypatch.setattr(client, "client", type("C", (), {"post": fake_post}))
    embeddings = await client.get_embeddings("test sentence")
    assert isinstance(embeddings, list)
    assert embeddings[0] == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_llm_client_get_embeddings_local_fallback(monkeypatch):
    from src.llm import LLMClient
    client = LLMClient()

    async def fake_post(url, json):
        raise Exception("API down")

    class FakeLocal:
        def __init__(self):
            pass
        def embed(self, inputs):
            return [[9.0, 9.0, 9.0] for _ in inputs]

    monkeypatch.setattr(client, "client", type("C", (), {"post": fake_post}))
    client._local_llm = FakeLocal()
    embeddings = await client.get_embeddings(["hi"])
    assert isinstance(embeddings, list)
    assert embeddings[0] == [9.0, 9.0, 9.0]


@pytest.mark.asyncio
async def test_redis_vector_adapter_ft_search_path():
    adapter = RedisVectorAdapter(redis_url="redis://localhost:6379")

    # Create a fake redis client with an FT-like API
    class FakeFTIndex:
        def __init__(self, storage):
            self.storage = storage

        async def info(self):
            return {"index_name": "vec_index"}

        async def search(self, query, query_params=None):
            # naive search: return all docs as docs with id and fields
            class Doc:
                def __init__(self, id, fields):
                    self.id = id
                    for k, v in fields.items():
                        setattr(self, k, v)
                    self.score = 1.0

            docs = []
            for key, value in self.storage.items():
                emb = value.get("embedding")
                try:
                    emb_list = json.loads(emb)
                except Exception:
                    emb_list = emb
                docs.append(Doc("vec:" + key, {"node_id": value.get("node_id"), "chunk_index": value.get("chunk_index"), "metadata": value.get("metadata")}))
            class Res:
                def __init__(self, docs):
                    self.docs = docs
            return Res(docs)

    class FakeRedisClientWithFT:
        def __init__(self):
            self.store = {}
        async def ping(self):
            return True
        async def hset(self, key, mapping):
            self.store[key.replace("vec:","")] = mapping
        async def sadd(self, key, value):
            pass
        async def smembers(self, key):
            return list(self.store.keys())
        async def hgetall(self, key):
            return self.store.get(key.replace("vec:", "")) or {}
        async def execute_command(self, *args, **kwargs):
            return None
        def ft(self, index_name):
            return FakeFTIndex(self.store)

    adapter.client = FakeRedisClientWithFT()
    await adapter.initialize()

    # Test indexing
    await adapter.index_chunk("f1", node_id="n1", chunk_index=0, embedding=[1,0,0], metadata={"source": "r"})
    await adapter.index_chunk("f2", node_id="n2", chunk_index=0, embedding=[0,1,0], metadata={"source": "r"})

    hits = await adapter.query_vector([1,0,0], top_k=2)
    assert len(hits) >= 1

