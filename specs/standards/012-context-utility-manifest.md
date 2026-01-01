<<<<<<< HEAD
# Standard 012: Context Utility Manifest

**Authority:** Active | **Philosophy:** Invisible Infrastructure

## The Principle
The Anchor Core is not a "Chat App". It is a **Context Utility** (like electricity or WiFi).
1.  **Headless First**: The system must provide value without a visible UI window.
2.  **Passive Observation**: Data ingestion should happen automatically (Daemon Eyes) rather than requiring manual user input.
3.  **Universal Availability**: Context must be accessible via standard HTTP endpoints (`/v1/memory/search`) to any client (Terminal, VS Code, Browser).

## The Rules
1.  **No UI Blocking**: Long-running tasks (like VLM analysis) MUST run in background threads/processes.
2.  **Zero-Touch Ingestion**: Screen/Audio capture must require zero clicks after initial activation.
3.  **Ground Truth**: All ingested context is immutable "Ground Truth" until proven otherwise.
=======
# Standard 012: Context Utility Manifest - The Invisible Infrastructure

## What Happened?
The Anchor Core system was originally conceived as a chat application, but has evolved into a unified cognitive infrastructure. The system now needs to transition from "active user input" to "passive observation" to function as truly invisible infrastructure like electricity - always present but never demanding attention.

## The Cost
- UI bloat with multiple chat interfaces competing for user attention
- Manual data entry required to populate context
- Users having to copy/paste information instead of automatic capture
- Architecture treating UI as primary rather than as debugging tool
- Missing opportunity to create true "ambient intelligence"

## The Rule
1. **Headless by Default**: All core functionality must operate without user interface interaction
   ```python
   # Core services run as background daemons
   daemon_services = [
       "memory_graph",      # CozoDB persistence
       "gpu_engine",        # WebLLM inference
       "context_capture",   # Screen/Audio observation
       "data_ingestion"     # Memory writing
   ]
   ```

2. **Passive Observation**: System captures context automatically rather than waiting for user input
   - **Eyes**: Automated screen sampling and OCR
   - **Ears**: Continuous audio transcription (when enabled)
   - **Memory**: Automatic ingestion without user intervention

3. **Architecture Priority**: `webgpu_bridge.py` is the nervous system; UIs are merely debugging/interaction tools
   - UIs are temporary visualization layers
   - Core logic exists independently of any UI
   - Background services operate without UI presence

4. **Invisible Utility**: The system should function like electricity - always available, rarely noticed, essential infrastructure
   - Zero user interaction required for core functions
   - Automatic context capture and storage
   - Seamless integration with user's workflow

5. **Context First**: Prioritize capturing and understanding user context over responding to queries
   - Short-term context populated automatically
   - Long-term memory built passively
   - Responses based on observed reality rather than explicit input

## Implementation Requirements

### Core Daemon Services
- **Memory Daemon**: Continuous CozoDB operations in background
- **Vision Daemon**: Automated screen capture and OCR (daemon_eyes.py)
- **Audio Daemon**: Optional background audio processing
- **Ingestion Daemon**: Automatic data flow to memory graph

### API-First Design
- All functionality accessible via API endpoints
- UIs as thin clients consuming API services
- Background services operating independently

### Error Handling
- Daemons must handle errors gracefully without user intervention
- Automatic recovery from common failures
- Silent operation with optional logging for debugging

## Transition Protocol

When implementing new features:
1. Design for headless operation first
2. Add UI as optional visualization layer
3. Ensure all functionality available via API
4. Test daemon operation independently of UI

This standard ensures that Anchor Core evolves into true invisible infrastructure rather than remaining a traditional application.
>>>>>>> 3cd511631b7eaf7d033a1bacccff36325545fc78
