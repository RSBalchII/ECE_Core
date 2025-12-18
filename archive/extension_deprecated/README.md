# Browser Extension (Bridge)

> **Coda Bridge** - Browser integration for Context-Engine

**Philosophy**: Your mind, augmented. Your data, sovereign. Your tools, open.

## Overview
The Browser Extension is the "Bridge" between your browser and the Context-Engine system. This Chrome Extension (Manifest V3) connects the browser to the Coda Core for context-aware browsing and memory-enhanced interactions.

## Capabilities
- **Voice**: Streaming chat interface via Side Panel.
- **Sight**: Context injection (reading active page content).
- **Memory**: **[Save to Memory]** button to ingest the current page/chat into the permanent knowledge graph.
- **Hands**: JavaScript execution on active pages (User-ratified).

## Architecture
- **Type**: Chrome Extension (Manifest V3)
- **Communication**: HTTP/SSE to `localhost:8000`
- **State**: Local Storage (Persistence)
- **Integration**: Connects to ECE_Core API for context-aware browsing

## Key Features
- ✅ Persistent chat history in side panel
- ✅ Real-time context injection from active tabs
- ✅ One-click memory saving with "Save to Memory" button
- ✅ Secure JavaScript execution with user confirmation

## Documentation
- `specs/spec.md` - Technical architecture
- `specs/plan.md` - Vision and implementation roadmap  
- `specs/tasks.md` - Current work items

## Integration
Connects to the ECE_Core backend via API endpoints for context-aware page reading and memory ingestion.