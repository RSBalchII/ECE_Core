# **Anchor Engine ⚓**  
### *Deterministic semantic memory for local‑first AI systems*

Anchor Engine is a **semantic memory layer** — not an agent framework, not a vector database, and not a cloud service.  
It’s a **deterministic, explainable, CPU‑only** system for storing and retrieving long‑term memory for AI agents.

It replaces embeddings with a **physics‑inspired graph algorithm (STAR)** that retrieves context using structure, time, and meaning — not dense vectors.

---

## **Why This Exists**
Most AI memory systems today assume:

- GPU‑heavy vector search  
- Probabilistic retrieval  
- Cloud dependence  
- Opaque similarity metrics  

I kept running into the same problem:  
**I needed a memory system that behaved like a mind, not a search engine.**

Anchor Engine is built around three principles:

- **Determinism** — same query → same result  
- **Explainability** — every retrieval comes with provenance  
- **Local sovereignty** — your data stays on your machine  

This project grew out of months of building agents that needed reliable memory — and discovering that existing tools weren’t designed for that job.

---

## **What Anchor Engine *Is***
A semantic memory layer that provides:

- Deterministic retrieval  
- Graph‑based semantics  
- Temporal decay  
- Provenance receipts  
- CPU‑only performance (<1GB RAM)  
- Local‑first architecture  

Use it as:

- A drop‑in replacement for embeddings/vector DBs  
- A memory backend for MCP‑compatible agents (Claude, Cursor, Qwen Code)  
- A personal knowledge system for long‑term projects  

---

## **What Anchor Engine *Is Not***
- ❌ An agent framework  
- ❌ A cloud service  
- ❌ A probabilistic vector search engine  
- ❌ A tool that stores your data anywhere except your machine  

---

## **Architecture & Technology Stack** ⚡

### Native Modules (Rust WASM)

Anchor Engine uses **Rust-compiled WebAssembly modules** for performance-critical operations. This eliminates the need for native compilation and provides universal platform support.

**Published Packages:**
| Package | Purpose | Version |
|---------|---------|---------|
| `@rbalchii/anchor-fingerprint-wasm` | Content fingerprinting (MD5, SHA256) | 1.0.0+ |
| `@rbalchii/anchor-atomizer-wasm` | Text atomization & entity extraction | 1.0.0+ |
| `@rbalchii/anchor-keyextract-wasm` | Key-value extraction from text | 1.0.0+ |
| `@rbalchii/anchor-tagwalker-wasm` | Semantic tag traversal | 1.0.0+ |

**Benefits:**
- ✅ Zero native compilation required (works on Windows ARM64, macOS, Linux)
- ✅ 97% smaller binary size (~35KB WASM vs ~1.2MB C++ DLLs)
- ✅ 10x faster module loading
- ✅ Universal platform support

**Note:** The older C++ native modules (`engine/src/native/` directory) have been deprecated and removed in favor of these Rust WASM packages. See [`engine/src/README.md`](./engine/src/README.md) for full architectural details.

---

## **QwenPaw Agent Configuration Protection 🔒**

To protect sensitive QwenPaw agent configuration files from being accidentally committed to the repository, the following files are now gitignored:

- `BOOTSTRAP.md`
- `MEMORY.md`
- `PROFILE.md`
- `SOUL.md`
- `AGENTS.md`

These files may contain private information and should never be shared. The `.gitignore` has been updated to prevent accidental commits of these sensitive configuration files.

---

## **Quick Start**
```bash
git clone https://github.com/RSBalchII/anchor-engine-node
cd anchor-engine-node
./install.sh   # or install-macos.sh / install.ps1
pnpm start
```

Open: **http://localhost**

---

## **How It Works (High‑Level)**

### **1. Content lives on disk, not in the database**
The database stores **pointers only**:

- file path  
- byte offsets  
- tags  
- timestamps  
- provenance  

All content is read directly from disk.  
This keeps RAM low and makes the DB disposable.

### **2. Retrieval uses the STAR algorithm**
STAR = *Semantic Temporal Associative Retrieval*

It combines:

- **Semantic gravity** (shared tags × hop distance)  
- **Temporal decay** (recent memories pull harder)  
- **Structural gravity** (SimHash proximity)  

The scoring equation is deterministic and explainable.  
Every result includes a receipt showing *why* it was retrieved.

### **3. The engine rebuilds itself on startup**
Your data lives in:

- `notebook/inbox/` (trusted, high‑weight)  
- `notebook/external-inbox/` (external, normal weight)  

The engine mirrors and indexes these on launch.

---

## **MCP Integration**
Anchor Engine can run as an **MCP server**, giving any MCP‑compatible agent persistent memory.

Available tools:

- `/anchor_query` — semantic search  
- `/anchor_distill` — session distillation  
- `/anchor_illuminate` — graph traversal  
- `/anchor_read_file` — byte‑range file reads  
- `/anchor_ingest_text` — opt‑in write operations  

Works with:

- Claude Desktop  
- Cursor  
- Qwen Code  

---

## **Example Query**
```bash
curl -X POST http://localhost/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What did we decide about OAuth?",
    "token_budget": 2048
  }'
```

Returns:

- matched atoms  
- provenance  
- hop distance  
- temporal weighting  
- byte‑range pointers  

---

## **Security Posture**
Anchor Engine is designed for local‑first, offline use.

Security features include:

- Path traversal prevention  
- API key authentication  
- Rate limiting  
- Input validation  
- Zero-copy deduplication  
- Disposable ephemeral DB  
- No cloud dependencies  

A full CodeQL audit (April 2026) found no unmitigated high‑severity issues.

---

## **Benchmarks**
Dataset: 91MB chat history (~25M tokens)

- Ingestion: **178 seconds**  
- Search p95: **<200ms**  
- Idle memory: **~600MB**  
- Restore: **281k atoms in 13.8 minutes**  

Hardware: consumer laptop, no GPU.

---

## **Why “Anchor”?**
Drop a query into your memory graph.  
It sinks to the semantic bottom.  
The chain plays out to your chosen radius.  
What you retrieve is what’s relevant — nothing more, nothing less.

Same anchor, same spot, same result.

---

## **Documentation**
- Quick Start  
- API Reference  
- MCP Integration  
- Architecture Overview  
- STAR Algorithm Whitepaper  
- Security Standards  
- Benchmarks  

---

## **License**
AGPL‑3.0

---

## **Citation**
```
@software{anchor_engine,
  title={STAR: Semantic Temporal Associative Retrieval},
  author={Balch II, R.S.},
  version={5.2.0},
  year={2026},
  url={https://github.com/RSBalchII/anchor-engine-node}
}
```

