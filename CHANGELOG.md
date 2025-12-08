# Changelog

## [1.2.0] - 2025-12-07 "Reka & Local Proxy"

### Added
- **Reka Configuration**: Full support for Reka-Flash-3-21B (Q4_K_S) with 16k context, stop tokens, and optimized LLaMa server flags.
- **Local API Proxy**: Added `scripts/local_api_proxy.py` to enforce static API keys for local LLaMa instances (fixes Cline extension "OpenAI API Key" requirement).
- **VS Code Integration**: Added `.vscode/settings.json` template and `VSCODE_CLINE_SETUP.md` for seamless local development.
- **MCP Health**: Added `/health` endpoint to Unified Launcher for better compatibility.

### Fixed
- **MCP Routing**: Resolved duplicate `/mcp` prefix in Unified Launcher routes (`/mcp/tools` is now accessible).
- **LLM Client**: Added `stop` token support to API payloads and local GGUF generation.

## [1.1.0] - 2025-12-06 "Archivist Protocol"

### Added
- **Archivist Ingestion**: Implemented `POST /archivist/ingest` endpoint to accept live data from the browser.
- **Memory Schema**: Enforced **Directive INJ-A1** (`PlaintextMemory`) for immutable "Page-Store" records.
- **Modular DOM Adapters**:
    - `GeminiAdapter`: Clean extraction for Google Gemini.
    - `ChatGPTAdapter`: Clean extraction for ChatGPT.
    - `ClaudeAdapter`: Clean extraction for Claude.ai.
    - `GenericAdapter`: Universal fallback for any webpage.
- **Extension UI**: Added **[Save to Memory]** button to the Side Panel for manual ingestion.

### Fixed
- **Encoding Crash**: Resolved Windows `charmap` error by enforcing `PYTHONIOENCODING='utf-8'`.
- **Server Stability**: Fixed startup crashes caused by `MemoryWeaver` resource contention.

## [1.0.0] - 2025-12-06 "Operation Concrete"

### Added
- **Browser Bridge**: A Chrome Extension (MV3) capable of:
    - **Voice**: Streaming chat interface via Side Panel.
    - **Sight**: Context injection (reading active tab).
    - **Hands**: JavaScript execution on active pages (User-ratified).
- **Backend Architecture**: Migrated from monolithic scripts to **Modular Recipes** (MAX Agentic Cookbook standard).
    - `CodaChatRecipe`: Handles orchestration, context, and tool execution.
- **Persistence**: Side panel now saves chat history to local storage.
- **Markdown Support**: Chat interface renders code blocks and syntax highlighting.

### Changed
- **Identity**: System formally renamed from "Sybil" to **"Coda"**.
- **Documentation**: Adopted `specs/` based documentation policy.

### Fixed
- **Audit Logger**: Patched critical `NameError` in streaming endpoints.
- **Security**: Hardened extension execution via `world: "MAIN"` to bypass strict CSP on some sites.
