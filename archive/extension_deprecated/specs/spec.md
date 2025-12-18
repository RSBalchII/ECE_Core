# Browser Extension (Coda Bridge) - Technical Specification

## Mission

Build **"The Bridge"** - A Chrome Extension (Manifest V3) that connects the browser to the Context-Engine system for context-aware browsing and memory-enhanced interactions.

**Philosophy**: Your browser, cognitively enhanced. Your data, sovereign. Your tools, open.

## Architecture Overview

### Extension Architecture (Manifest V3)
- **Type**: Chrome Extension with Side Panel interface
- **Communication**: HTTP/SSE to `localhost:8080`
- **State**: Local Storage (Persistent across browsing sessions)
- **Permissions**: Host access restricted to localhost only

### Capabilities
1. **Voice**: Streaming chat interface via Side Panel
2. **Sight**: Context injection (reading active page content from tab)  
3. **Memory**: **[Save to Memory]** functionality to archive web content to Neo4j knowledge graph
4. **Hands**: JavaScript execution on active pages (User-ratified)

### Integration Points
- **ECE_Core API**: Connects to Context-Engine backend for memory operations
- **Content Scripts**: Page content extraction and DOM manipulation
- **Background Service**: Message routing and session management

## Component Architecture

### Core Components
1. **Side Panel UI**: Streaming chat interface with persistent history
2. **Content Scripts**: DOM extraction and context injection on active pages
3. **Background Service**: Message routing between UI and content scripts
4. **API Client**: HTTP communication with Context-Engine backend

### API Interface
- **Chat Endpoint**: `POST /chat/stream` for streaming memory-enhanced conversations
- **Memory Endpoint**: `POST /archivist/ingest` for saving page content to memory graph
- **Summary Endpoints**: `GET /memory/summaries` for historical context access
- **Health Check**: `GET /health` for Context-Engine availability verification

### Security Model

#### Permission Architecture
- **Host Permissions**: `localhost` only (prevents web-based attacks)
- **Active Tab Access**: Read-only access to current page content (requires user activation)
- **Script Execution**: JavaScript execution via `scripting` API with user ratification
- **Local Storage**: Session persistence within extension context

#### Content Security Policy
- **No Remote Scripts**: All JavaScript must be included locally in extension bundle
- **Strict CSP**: Prevents injection of malicious content into extension pages
- **Isolated Worlds**: Content scripts run in isolated world from page scripts
- **Safe Communication**: All communication via Chrome messaging API

### Memory Architecture Integration

#### Page Ingestion Protocol
1. **User Action**: Click "Save to Memory" button in side panel
2. **Content Extraction**: Content script extracts page content using DOM traversal
3. **Adapter Selection**: Select appropriate DOM adapter based on domain recognition
4. **Content Cleaning**: Normalize content using selected adapter
5. **Ingestion Request**: Send cleaned content to `/archivist/ingest`
6. **Graph Storage**: ECE_Core stores as Neo4j nodes with relationships

#### Context Injection Protocol
1. **User Request**: Activate context injection via button or command
2. **Content Extraction**: Content script reads active page content
3. **Adaptive Cleaning**: Apply domain-specific cleaning rules
4. **Context Injection**: Include extracted content in chat prompt
5. **Response Processing**: Process response with full context awareness

### DOM Adapter System

#### Available Adapters
- **GeminiAdapter**: Clean extraction for Google Gemini conversations
- **ChatGPTAdapter**: Clean extraction for ChatGPT interface
- **ClaudeAdapter**: Clean extraction for Claude.ai interface
- **GenericAdapter**: Universal fallback for any webpage

#### Adapter Architecture
Each adapter implements:
- `extract_content(document)`: Extract clean plaintext from DOM
- `identify_domain(url)`: Recognize if this adapter applies to the domain
- `sanitize_content(text)`: Clean up extracted text for memory storage
- `get_metadata(document)`: Extract titles, dates, authors, etc.

## Integration with Infinite Context Pipeline

### Context Continuity
- **Session Preservation**: Maintain conversation history in local storage across page reloads
- **Cross-Tab Awareness**: Share context across multiple browser tabs
- **Memory Linking**: Connect saved content to historical ContextGist memories in Neo4j

### Large Content Handling
- **Chunked Extraction**: Process large pages in segments to avoid memory limits
- **Progress Indication**: Show extraction progress for large documents
- **Content Fallbacks**: Graceful degradation for sites that fail extraction

### Historical Context Access
- **ContextGist Retrieval**: Query Neo4j for historical context summaries when available
- **Chronological Linking**: Navigate through ContextGist chain from current session
- **Memory Continuity**: Maintain reasoning flow across browser sessions

## Performance Characteristics

### Responsiveness
- **Streaming UI**: Real-time chat rendering as responses arrive
- **Background Processing**: Content extraction happens asynchronously
- **Local Caching**: Frequently used assets cached locally for speed

### Memory Management
- **Content Limits**: Size limits for extracted content to prevent OOM
- **Automatic Cleanup**: Periodic cleanup of old chat history
- **Efficient Serialization**: Optimized data transfer between extension components

## Privacy & Sovereignty

### Data Flow
- **Local Processing**: All content processing happens within browser extension
- **Selective Sharing**: User controls what content is sent to Context-Engine
- **Local Storage**: Chat history maintained locally in extension storage
- **No Telemetry**: Zero external data transmission

### Access Control
- **URL-Based Restrictions**: Only process content from user-approved domains
- **Content Filtering**: Sanitize content before sending to external systems
- **User Ratification**: All save operations require explicit user confirmation
- **Session Isolation**: Separate storage for different browsing contexts

## Deployment Architecture

### Manifest V3 Compliance
- **Service Worker**: Background operations without persistent background pages
- **Asset Bundling**: All required assets included in extension package
- **Permissions**: Minimal required permissions as defined in manifest.json
- **Content Security**: All policies enforced as per Chrome Web Store guidelines

### Cross-Browser Potential
- **Manifest Compatibility**: Structure designed for potential Firefox compatibility
- **API Compatibility**: Chrome-specific APIs documented for porting
- **Build Pipeline**: Extension build process supports multiple targets

## Extensibility Points

### Custom Adapters
- **Domain-Specific Adapters**: Extend with adapters for specialized websites
- **Content Type Handlers**: Special processing for different content types (PDF, video, etc.)
- **Metadata Enrichment**: Domain-specific metadata extraction

### UI Customization
- **Theme Support**: Configurable appearance options
- **Layout Options**: Different UI layouts for different use cases
- **Feature Toggles**: Enable/disable specific extension capabilities

### Integration Points
- **Bookmarklet Backup**: Alternative access via bookmarklet for non-extension browsers
- **API Key Management**: Multiple Context-Engine instance support
- **Profile Management**: Different profiles for different use cases