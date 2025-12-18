# Chrome Extension Bridge Specification

**Silent context injection for corporate LLMs. Turn Gemini/ChatGPT into your "dumb terminal".**

---

## Identity

- **Name:** Sovereign Context Bridge
- **Target Platforms:** `gemini.google.com`, `chatgpt.openai.com` (extensible)
- **Trigger:** 3-second pause in text input
- **Injection Method:** Automatic text append before submission
- **Data Source:** Local CozoDB (zero backend latency)

---

## Architecture Overview

```
User types in gemini.google.com
  ↓
Content Script detects 3-second pause
  ↓
Background Service Worker queries local CozoDB
  ↓
Memory results returned (< 100ms)
  ↓
Context Summary generated
  ↓
Silently append to text area (or insert as system instruction if available)
  ↓
User hits Enter (normal flow)
```

---

## Components

### 1. Manifest (`manifest.json`)

**MV3 Manifest Structure:**
```json
{
  "manifest_version": 3,
  "name": "Sovereign Context Bridge",
  "version": "1.0.0",
  "description": "Silent context injection for LLM conversations",
  "permissions": [
    "activeTab",
    "scripting",
    "storage",
    "webRequest"
  ],
  "host_permissions": [
    "*://gemini.google.com/*",
    "*://chatgpt.openai.com/*"
  ],
  "content_scripts": [
    {
      "matches": ["*://gemini.google.com/*", "*://chatgpt.openai.com/*"],
      "js": ["content.js"],
      "run_at": "document_start"
    }
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html",
    "default_title": "Sovereign Context Bridge"
  },
  "icons": {
    "16": "images/icon-16.png",
    "32": "images/icon-32.png",
    "128": "images/icon-128.png"
  }
}
```

### 2. Content Script (`content.js`)

**Responsibilities:**
- Inject status indicator into page
- Detect user input in text area
- Monitor for 3-second pause
- Receive context from background worker
- Inject context into textarea

**Key Functions:**

#### `detectTextArea()`
```javascript
function detectTextArea() {
  // Platform-specific selectors
  const selectors = {
    'gemini.google.com': 'div[contenteditable="true"], textarea',
    'chatgpt.openai.com': 'textarea'
  };
  return document.querySelector(selectors[domain]);
}
```

#### `setupPauseDetector()`
```javascript
let inputTimeout;
const PAUSE_THRESHOLD = 3000; // 3 seconds

textArea.addEventListener('input', () => {
  clearTimeout(inputTimeout);
  inputTimeout = setTimeout(() => {
    console.log('[Sovereign] 3-second pause detected, querying memories...');
    chrome.runtime.sendMessage(
      { action: 'queryMemories', query: getVisibleText() },
      (response) => injectContext(response)
    );
  }, PAUSE_THRESHOLD);
});
```

#### `injectContext(contextData)`
```javascript
function injectContext(contextData) {
  const summary = `[Sovereign Context Injection at ${new Date().toLocaleTimeString()}]\n${contextData.summary}\n---\n`;
  
  // For contenteditable (Gemini)
  if (textArea.contentEditable === 'true') {
    const currentText = textArea.textContent;
    textArea.textContent = currentText + '\n' + summary;
  }
  // For textarea (ChatGPT)
  else {
    textArea.value += '\n' + summary;
  }
  
  displayIndicator('✓ Context injected (memories found)', 'success');
}
```

#### Status Indicator
```javascript
function displayIndicator(message, type) {
  const indicator = document.getElementById('sovereign-indicator') || 
                    createIndicator();
  indicator.textContent = message;
  indicator.className = `sovereign-indicator ${type}`;
  setTimeout(() => indicator.remove(), 5000);
}
```

### 3. Background Service Worker (`background.js`)

**Responsibilities:**
- Maintain persistent connection to local CozoDB (if backend running)
- Query memories based on visible text
- Generate summaries
- Handle pause trigger messages

**Key Functions:**

#### `queryMemories()`
```javascript
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'queryMemories') {
    queryMemoriesFromCozoDB(request.query)
      .then(memories => ({
        success: true,
        memories: memories,
        summary: generateSummary(memories)
      }))
      .then(sendResponse)
      .catch(err => ({
        success: false,
        error: err.message
      }));
    return true; // Keep channel open for async response
  }
});
```

#### `queryMemoriesFromCozoDB(userInput)`
```javascript
async function queryMemoriesFromCozoDB(userInput) {
  try {
    // Option 1: If backend API available
    const response = await fetch('http://localhost:8000/memories/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: userInput })
    });
    return response.json();
  } catch (e) {
    // Option 2: Fall back to local CozoDB via SharedArrayBuffer or WebWorker
    console.warn('[Sovereign] Backend unavailable, querying local store...');
    return queryLocalCozoDB(userInput);
  }
}
```

#### `generateSummary(memories)`
```javascript
function generateSummary(memories) {
  if (memories.length === 0) return 'No relevant memories found.';
  
  const maxMemories = 3;
  const relevant = memories.slice(0, maxMemories);
  
  return relevant
    .map((m, idx) => `[Memory ${idx + 1}] ${m.content.substring(0, 100)}...`)
    .join('\n');
}
```

### 4. Popup UI (`popup.html`)

**Simple status page shown when user clicks extension icon:**

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="popup-container">
    <h3>🧠 Sovereign Context Bridge</h3>
    
    <div id="status">
      <p>Status: <span id="status-badge">●</span></p>
      <p id="status-text">Initializing...</p>
    </div>
    
    <div id="stats">
      <p>Memories cached: <span id="mem-count">0</span></p>
      <p>Last injection: <span id="last-inject">Never</span></p>
    </div>
    
    <button id="settings-btn">⚙️ Settings</button>
    <button id="test-inject-btn">🧪 Test Injection</button>
  </div>
  
  <script src="popup.js"></script>
</body>
</html>
```

---

## Data Flow: Query → Inject

```
Step 1: User types "Tell me about Chronos" in Gemini
  ↓
Step 2: Content script detects 3-second pause
  ↓
Step 3: Send message to background worker: {action: 'queryMemories', query: '...'}
  ↓
Step 4: Background worker queries memories
  (Option A: /memories/search endpoint if backend available)
  (Option B: Direct CozoDB query if local store accessible)
  ↓
Step 5: Return top-3 memories + summary
  {
    success: true,
    memories: [
      {id: "123", content: "Chronos is about time management..."},
      {id: "124", content: "In July session..."},
      {id: "125", content: "Key insight: context rotation..."}
    ],
    summary: "[Memory 1] Chronos is about... [Memory 2] In July... [Memory 3] Key insight..."
  }
  ↓
Step 6: Content script injects into textarea:
  "Tell me about Chronos
   
   [Sovereign Context Injection at 14:32:05]
   [Memory 1] Chronos is about time management...
   [Memory 2] In July session we discovered...
   [Memory 3] Key insight: context rotation prevents token loss...
   ---"
  ↓
Step 7: User presses Enter → Gemini processes augmented prompt
  ↓
Step 8: Response includes your memory context!
```

---

## Trigger Mechanisms

### Primary: 3-Second Pause

```javascript
// User stops typing → wait 3 seconds → trigger query
const PAUSE_THRESHOLD = 3000;
let pauseTimer;

textArea.addEventListener('input', () => {
  clearTimeout(pauseTimer);
  pauseTimer = setTimeout(() => triggerMemoryQuery(), PAUSE_THRESHOLD);
});
```

### Secondary: Manual Hotkey (Optional)

```javascript
// Ctrl+Shift+M to manually inject
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.shiftKey && e.code === 'KeyM') {
    triggerMemoryQuery();
  }
});
```

---

## Context Injection Format

### Option 1: Append to User Text
```
Tell me about Project Chronos

[Sovereign Context - Memories]
[Mem 1] Project Chronos explores infinite context windows...
[Mem 2] Discovered in July: context rotation is key...
[Mem 3] Verifier agent reduces hallucinations...
---
```

### Option 2: System Instruction (if API allows)
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You have access to these contextual memories: [Mem 1] ... [Mem 2] ..."
    },
    {
      "role": "user",
      "content": "Tell me about Project Chronos"
    }
  ]
}
```

---

## Configuration & Settings

**User-Configurable (popup.js):**
```javascript
const CONFIG = {
  pauseThreshold: 3000,           // 3 seconds
  maxMemoriesToInject: 3,          // Top 3
  injectionFormat: 'append',       // or 'system-instruction'
  enabledSites: {
    'gemini.google.com': true,
    'chatgpt.openai.com': true
  },
  backendUrl: 'http://localhost:8000',
  fallbackToLocal: true            // Use local CozoDB if backend down
};
```

---

## Error Handling

### Scenario 1: Backend Unavailable
```
→ Fall back to local CozoDB (if accessible)
→ If local unavailable, show status: "⚠ No memories available"
```

### Scenario 2: No Relevant Memories Found
```
→ Display indicator: "No relevant memories found"
→ Still allow user to submit normally
```

### Scenario 3: Injection Failed
```
→ Show error: "Failed to inject context"
→ Allow user to retry manually via button
```

---

## Performance Targets

- **Pause detection latency:** < 50ms
- **Memory query latency:** < 100ms (local) or < 500ms (backend)
- **Injection latency:** < 50ms
- **Total E2E:** < 150ms (user should not notice delay)

---

## Privacy & Security

- **Local-first:** All queries stay on user's machine
- **No logging:** Extension doesn't upload queries to external services
- **User control:** Manual disable via popup toggle
- **Memory source:** Only accesses local CozoDB, never user's active Gemini text

---

## Platform Adaptations

### For Gemini
- **Text Area:** `div[contenteditable="true"]`
- **Submission:** Detect Enter key or "Send" button click
- **Format:** Append to contenteditable div

### For ChatGPT
- **Text Area:** `textarea`
- **Submission:** Detect Enter or Ctrl+Enter
- **Format:** Append to textarea value

### Future: Claude, Copilot, etc.
- Extend `host_permissions` in manifest
- Add platform-specific selector in `content.js`

---

## Related Specs

- See [Sovereign WASM Spec](sovereign-wasm.spec.md) for CozoDB query patterns
- See [Memory Layer Spec](memory-layer.spec.md) for memory retrieval
- See [API Spec](api.spec.md) for `/memories/search` endpoint

---

**Last Updated:** 2025-12-15  
**Status:** Design Phase (ready for implementation)
**Development Phase:** Priority 3 (Sovereign Stack must be operational first)
