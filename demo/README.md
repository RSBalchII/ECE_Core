# STAR Demo - Interactive Browser Demo

**Live Demo:** [Open in Browser](demo/index.html)

A lightweight, client-side implementation of the STAR (Semantic Temporal Associative Retrieval) algorithm that runs entirely in your browser.

## Features

- 📚 **Project Gutenberg Integration** - Fetch and ingest classic books
- ⚡ **Instant Search** - Sub-millisecond retrieval
- 🕸️ **Graph Visualization** - See atoms, tags, and edges in real-time
- 🎯 **Deterministic** - Same query = same results every time
- 🔍 **Inspectable** - Understand why each result matched (tag receipts)

## Quick Start

1. Open `demo/index.html` in your browser
2. Click "Select Book from Gutenberg"
3. Choose a classic book (Frankenstein, Moby Dick, etc.)
4. Wait for ingestion (~2-5 seconds)
5. Search for themes, characters, or concepts

## How It Works

### 1. Atomization
Text is split into sentences, and each sentence is tagged with key concepts:
```
"The whale swam through the dark ocean"
→ Tags: [whale, swam, dark, ocean]
```

### 2. Graph Building
Atoms sharing tags are connected with edges:
- Atoms with tag "whale" → connected to each other
- Atoms with tag "ocean" → connected to each other
- Creates a semantic network

### 3. STAR Search
Two-phase retrieval:
1. **Anchor Phase** - Find atoms with direct tag matches
2. **Neighbor Phase** - Traverse graph to find related atoms
3. **Temporal Decay** - Older content weighted lower

## Example Searches

**Frankenstein:**
- "monster" - Find creation scenes
- "life" - Philosophical passages
- "death" - Tragic moments

**Moby Dick:**
- "whale" - Cetology and hunting
- "sea" - Maritime descriptions
- "captain" - Ahab's speeches

## Technical Details

- **Zero Dependencies** - Pure HTML/CSS/JavaScript (ES5)
- **No Backend** - All processing in browser
- **CORS Proxy** - Uses allorigins.win for Gutenberg API
- **Performance** - <1ms search on 400+ atoms
- **Memory** - Lightweight Map/Set data structures

## Algorithm Comparison

| Feature | STAR (This Demo) | Vector Search |
|---------|------------------|---------------|
| Deterministic | ✅ Yes | ❌ No (embedding drift) |
| Inspectable | ✅ Tag receipts | ❌ Black box |
| Setup | ✅ Zero | ❌ Requires embeddings |
| Speed | ✅ <1ms | ~50-200ms |
| Hardware | ✅ Any browser | GPU preferred |

## Demo Limitations

- **50KB text limit** - For browser performance
- **Basic NLP** - Simple word extraction (not full NER)
- **Single book** - One book at a time (no cross-book search)
- **No persistence** - Reset on page reload

For production use with full features, see the main [Anchor Engine](../README.md).

## Sharing

**Perfect for:**
- Quick demos to colleagues
- Social media posts (Reddit, HN, Twitter)
- Understanding the algorithm visually
- Teaching graph-based retrieval

**Screenshot Tips:**
1. Ingest a popular book (Frankenstein works great)
2. Search for a dramatic term ("monster", "death", "love")
3. Show the stats bar (atoms/tags/edges)
4. Highlight the tag receipts showing WHY results matched

## License

AGPL-3.0 (same as main project)

## Try It Now

Just open `demo/index.html` in any modern browser - no installation required!
