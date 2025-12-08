# Coda Bridge (Extension)

**Location**: `Context-Engine/extension/`

The **Coda Bridge** is a Chrome Extension (Manifest V3) that connects the browser to the Coda Core.

## Capabilities
- **Voice**: Streaming chat interface via Side Panel.
- **Sight**: Context injection (reading active tab).
- **Memory**: **[Save to Memory]** button to ingest the current page/chat into the permanent knowledge graph.
- **Hands**: JavaScript execution on active pages (User-ratified).

## Installation
1.  Open Chrome and navigate to `chrome://extensions`.
2.  Enable **Developer Mode** (top right).
3.  Click **Load Unpacked**.
4.  Select this `extension/` directory.

## Development
- **Build**: Run `python scripts/build_extension.py` (from project root) to create a zip in `dist/`.
- **Permissions**:
    - `activeTab`: For reading the current page.
    - `scripting`: For executing actions.
    - `storage`: For persistent chat history.
    - `sidePanel`: For the UI.

