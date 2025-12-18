# Context-Engine Architecture: Function Graph & Data Flow

## Directory Structure (Post-Update)
```
C:\Users\rsbiiw\Projects\Context-Engine/
├── README.md                    ← Root project overview
├── CHANGELOG.md                 ← Complete project history
├── doc_policy.md               ← Documentation policy
├── specs/                      ← Root specs directory
│   ├── spec.md                 ← System architecture & design
│   ├── plan.md                 ← Vision & implementation roadmap
│   └── tasks.md                ← Current work items & priorities
├── start_llm_server.py         ← Main LLM server launcher (64k window)
├── start_llm_gemma3_server.py  ← Gemma3 server launcher (64k window)
├── start_llm_minimight.py      ← Minimight server launcher (64k window)
├── start_embedding_server.py   ← Embedding server launcher
├── backend/                    ← ECE_Core cognitive engine
│   ├── README.md               ← Backend-specific documentation
│   ├── launcher.py             ← Backend server entry point
│   ├── unified_launcher.py     ← Modular app with MCP integration
│   ├── src/
│   │   ├── context.py          ← ContextManager with rotation protocol
│   │   ├── graph.py            ← GraphReasoner with ContextGist integration  
│   │   ├── distiller_impl.py   ← Distiller with gist creation
│   │   ├── archivist.py        ← Archivist agent for context management
│   │   └── memory/             ← Neo4j/Redis integration
│   ├── specs/                  ← Backend specs directory
│   │   ├── spec.md             ← Backend architecture
│   │   ├── plan.md             ← Backend roadmap
│   │   └── tasks.md            ← Backend development tasks
│   └── plugins/                ← UTCP plugin system
├── anchor/                     ← Terminal interface
│   ├── README.md               ← Anchor-specific documentation
│   ├── main.py                 ← Anchor CLI entry point
│   ├── logic.py                ← Conversation and tool orchestration
│   ├── specs/                  ← Anchor specs directory
│   │   ├── spec.md             ← Anchor architecture
│   │   ├── plan.md             ← Anchor roadmap
│   │   └── tasks.md            ← Anchor development tasks
│   └── tools/                  ← Tool integration modules
├── extension/                  ← Browser extension
│   ├── README.md               ← Extension-specific documentation
│   ├── manifest.json           ← Chrome extension manifest
│   ├── sidepanel.html          ← UI template
│   ├── sidepanel.js            ← Extension logic
│   ├── specs/                  ← Extension specs directory
│   │   ├── spec.md             ← Extension architecture
│   │   ├── plan.md             ← Extension roadmap
│   │   └── tasks.md            ← Extension development tasks
│   └── content.js              ← Content script for page reading
└── models/                     ← Symlink to ../models (actual storage)
```

## Component Architecture and Function Graph

### 1. **Context Rotation Protocol (The New Infinite Context Pipeline)**

```
User Input (Large Document/Long Conversation)
    ↓
ContextManager.build_context()
    ↓
ContextManager.check_and_rotate_context()  ← NEW: Monitors total context size
    │
    ├── IF (context_size > 55000 chars)
    │       ↓
    │   ContextManager.rotate_context_logic()
    │       ├── old_portion = extract_first_half(context)
    │       ├── gist_summary = Distiller.distill_to_gist(old_portion)  ← NEW: Compress to narrative gist
    │       ├── gist_id = Neo4jStore.store_gist(gist_summary, metadata)  ← NEW: Store as ContextGist node
    │       └── new_context = reconstruct_with_gist(gist_summary, remaining_recent_context, new_input)
    │
    └── ELSE (normal flow)
            ↓
        Full context assembled with memories and summaries
```

### 2. **Graph-R1 Reasoning with Historical Context**

```
GraphReasoner.reason(query)
    ↓
GraphReasoner._retrieve_subgraph(query, session_id)
    ↓
Neo4jStore.execute_cypher(query)
    ↓
RETURNS:
├── Direct memories and summaries (current context)
├── ContextGist nodes (historical compressed context)  ← NEW: Historical context access
└── Related entities and relationships (graph traversal)
    ↓
GraphReasoner._attempt_answer(query, retrieved_context)
    ↓
IF has_context_gists(retrieved_context):  ← NEW: Check for historical context
    ↓
Context continuity maintained across rotation boundaries
```

### 3. **Distiller Integration with Context Rotation**

```
Distiller.distill_to_gist(content)
    ↓
Distiller._chunk_and_distill(content)  ← Used for context rotation
    ↓
Distiller._simple_entity_extraction(content)  ← Extract entities for graph linking
    ↓
RETURN {"summary": summary_text, "entities": entities}  ← For ContextGist creation
```

### 4. **Data Flow in Infinite Context Pipeline**

```
[Browser Extension / Anchor CLI]
    ↓ (User Input)
[ECE_Core API / ContextManager]
    ↓
├── IF: Context approaches 55k tokens
│   ├── OLD: Context truncated (pre-phase 5)
│   └── NEW: Context rotated with gist creation
│       ├── Old context → Distiller → Compressed gist
│       ├── Gist → Neo4j → ContextGist node
│       └── New context = [System Prompt] + [Gist Summaries] + [Recent Context] + [New Input]
└── ELSE: Normal context assembly with active memories
    ↓
[Neo4j Memory Graph]
├── (:Memory) nodes (active memories)
├── (:ContextGist) nodes (historical compressed context)  ← NEW
├── (:Summary) nodes (session summaries)
└── (:Entity) nodes (extracted entities)
    ↓
[LLM Server] (64k context window)
    ↓
[Response Streamed Back to User]
```

### 5. **Class Interactions Map**

```
ContextManager
├── → Distiller (for gist creation during rotation)
├── → Neo4jStore (for gist persistence)
├── → GraphReasoner (for retrieval logic)
└── → ArchivistAgent (for maintenance coordination)

GraphReasoner  
├── → Neo4jStore (for context gist retrieval)
├── → ContextManager (for context assembly)
└── → LLMClient (for reasoning iteration)

Distiller
├── → LLMClient (for content distillation)
└── → Neo4jStore (for entity storage)

ArchivistAgent
├── → ContextManager (for rotation oversight)
├── → Neo4jStore (for memory maintenance)  
└── → MemoryWeaver (for relationship repair)

MemoryWeaver (Maintenance Engine)
├── → Neo4jStore (for relationship repair)
└── → AuditLogger (for traceability)
```

### 6. **API Endpoints Integration**

```
HTTP /chat/stream (Anchor/Extension) 
    ↓
ContextManager.build_context_with_rotation()
    ↓
GraphReasoner.retrieve_enhanced_context() 
    ├── Current memories + summaries
    └── Historical ContextGist nodes  ← NEW
    ↓
LLM.generate_with_context()
    ↓
Streaming Response
```

### 7. **Memory Architecture (Post-Phase 5)**

```
Tiered Memory System:
├── Redis (Hot Cache - 24h TTL)
│   ├── Active conversation context
│   ├── Recent session data
│   └── Temporary processing state
└── Neo4j (Cold Storage - Persistent)
    ├── (:Memory) - Individual memory nodes
    ├── (:ContextGist) - Compressed historical context  ← NEW
    ├── (:Summary) - Session summaries
    ├── (:Entity) - Extracted entities
    └── Relationships - Connections between all nodes
        ├── [:RELATED_TO] - General connections
        ├── [:MENTIONS] - Reference connections
        ├── [:NEXT_GIST] - Chronological gist sequence  ← NEW for context continuity
        └── [:CAUSED_BY] - Provenance relationships
```

## Key Changes Implemented in Phase 5 (Infinite Context Pipeline):

1. **Hardware Foundation**: All LLM servers now boot with 65,536 context window
2. **Context Rotation Protocol**: ContextManager monitors and rotates context when needed
3. **Gist Creation System**: Distiller creates compressed context summaries for long-term storage
4. **ContextGist Storage**: Neo4j nodes to store historical context with chronological links
5. **Graph-R1 Enhancement**: Reasoner retrieves both current and historical context
6. **Documentation Policy**: Organized specs/ directories at all levels (root, backend, anchor, extension)

The system now supports **truly infinite context** by intelligently rotating old context into compressed summaries (ContextGists) that are persisted in Neo4j and can be retrieved during reasoning, creating a seamless cognitive experience that never runs out of memory space.