document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const API_BASE = "http://127.0.0.1:8000";
    const SESSION_ID = "browser-session"; // Static session for the browser bridge

    // --- Elements ---
    const chatContainer = document.getElementById('chat-container');
    const promptInput = document.getElementById('prompt');
    const sendButton = document.getElementById('send');
    const clearButton = document.getElementById('clear-btn');
    const saveMemoryButton = document.getElementById('save-memory-btn');
    const includeContextToggle = document.getElementById('include-context');
    const debugLog = document.getElementById('debug-log');

    let messageHistory = [];

    // --- Helpers ---
    function logDebug(msg) {
        if (!debugLog) return;
        const timestamp = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        entry.textContent = `[${timestamp}] ${msg}`;
        debugLog.appendChild(entry);
        debugLog.scrollTop = debugLog.scrollHeight;
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function formatMessage(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
            .replace(/\n/g, '<br>');
    }

    function appendMessage(role, text, save = true) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'user-message' : 'coda-message'}`;
        if (role === 'system') {
            msgDiv.style.fontStyle = 'italic';
            msgDiv.style.color = '#888';
            msgDiv.textContent = text;
        } else {
            msgDiv.innerHTML = formatMessage(text);
        }
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    // --- Core Logic ---

    function loadHistory() {
        chrome.storage.local.get("chat_history", (result) => {
            if (result.chat_history) {
                messageHistory = result.chat_history;
                if (messageHistory.length === 0) {
                    appendMessage('assistant', 'Hello. I am Coda. The Bridge is active.', false);
                } else {
                    messageHistory.forEach(msg => appendMessage(msg.role, msg.content, false));
                }
            } else {
                appendMessage('assistant', 'Hello. I am Coda. The Bridge is active.', false);
            }
            scrollToBottom();
        });
    }

    function saveHistory() {
        chrome.storage.local.set({ chat_history: messageHistory });
    }

    // --- Event Handlers ---

    // 1. CLEAR MEMORY (Full Reset)
    clearButton.addEventListener('click', async () => {
        if (!confirm("Reset active memory context (Local & Server)?")) return;
        
        // Clear UI & Local
        chrome.storage.local.remove("chat_history");
        messageHistory = [];
        chatContainer.innerHTML = '';
        const loadingMsg = appendMessage('assistant', '🧹 Wiping server context...', false);

        // Clear Server
        try {
            const res = await fetch(`${API_BASE}/context/${SESSION_ID}`, { method: 'DELETE' });
            if (res.ok) {
                loadingMsg.innerHTML = "✅ <b>Context Cleared.</b> I have forgotten this session.";
            } else {
                loadingMsg.innerHTML = `⚠️ Local cleared, but Server returned ${res.status}`;
            }
        } catch (e) {
            loadingMsg.innerHTML = `❌ Local cleared, but Server unreachable: ${e.message}`;
        }
    });

    // 1.5 SAVE MEMORY (Archivist)
    saveMemoryButton.addEventListener('click', async () => {
        const originalText = saveMemoryButton.textContent;
        saveMemoryButton.disabled = true;
        saveMemoryButton.textContent = "Saving...";
        logDebug("Save button clicked.");

        try {
            // 1. Get Page Content
            logDebug("Attempting to read active tab...");
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab || !tab.id) throw new Error("No active tab");

            // Safety check for restricted URLs
            const currentUrl = tab.url || "";
            logDebug(`Target URL: ${currentUrl}`);
            if (currentUrl.startsWith("chrome://") || currentUrl.startsWith("edge://") || currentUrl.startsWith("about:")) {
                 throw new Error("Cannot save memory from restricted browser pages.");
            }

            let response;
            try {
                response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
                logDebug("Content script responded directly.");
            } catch (err) {
                // If connection fails, try injecting the script
                console.log("Connection failed, attempting injection...", err);
                logDebug("Connection failed, attempting injection...");
                try {
                    await chrome.scripting.executeScript({
                        target: { tabId: tab.id },
                        files: ['content.js']
                    });
                    logDebug("Script injection successful.");
                    // Wait a bit for the script to initialize
                    await new Promise(resolve => setTimeout(resolve, 500));
                    // Retry
                    response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
                    logDebug("Content script responded after injection.");
                } catch (injectionErr) {
                    logDebug(`Injection failed: ${injectionErr.message}`);
                    if (injectionErr.message.includes("Cannot access contents")) {
                        throw new Error("⚠️ Restricted Page: Cannot read this tab (Browser Security)");
                    }
                    throw new Error("Failed to inject content script: " + injectionErr.message);
                }
            }

            if (!response || !response.success) {
                logDebug(`Extraction failed: ${response ? response.error : "No response"}`);
                throw new Error(response ? (response.error || "Failed to read page") : "No response from page");
            }

            const content = response.content;
            logDebug(`Content extraction length: ${content.length} chars`);
            const url = tab.url || "unknown_source";
            
            // 2. Determine Type
            let type = "web_page";
            if (url && (url.includes("gemini.google.com") || url.includes("chatgpt.com") || url.includes("claude.ai"))) {
                type = "gemini_chat"; // Generic "AI Chat" type, mapped in backend
            }

            // 3. Send to Archivist
            logDebug("Sending payload to /archivist/ingest...");
            const res = await fetch(`${API_BASE}/archivist/ingest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: content,
                    type: type,
                    adapter: "chrome_extension"
                })
            });

            logDebug(`Backend response status: ${res.status}`);
            if (!res.ok) throw new Error(`Server error: ${res.status}`);
            
            const data = await res.json();
            logDebug(`Archivist response: ${JSON.stringify(data)}`);
            appendMessage('system', `✅ Memory Ingested ID: ${data.memory_ids.join(", ")}`, false);

        } catch (e) {
            logDebug(`Error: ${e.message}`);
            appendMessage('system', `❌ Save failed: ${e.message}`, false);
        } finally {
            saveMemoryButton.disabled = false;
            saveMemoryButton.textContent = originalText;
        }
    });

    // 2. SEND MESSAGE
    async function sendMessage() {
        const text = promptInput.value.trim();
        if (!text) return;

        // Lock UI
        promptInput.value = '';
        promptInput.style.height = '40px';
        sendButton.disabled = true;
        sendButton.textContent = "Sending...";
        
        appendMessage('user', text, false);
        messageHistory.push({ role: "user", content: text });
        saveHistory();

        const responseDiv = appendMessage('assistant', '<span class="blinking-cursor">▌</span>', false);
        
        // Context Injection
        let finalMessage = text;
        
        // If "Read Page" is checked, grab context
        if (includeContextToggle && includeContextToggle.checked) {
            try {
                logDebug("Reading page for chat context...");
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tab && tab.id) {
                    // responseDiv.innerHTML = "<i>Reading page...</i>"; // Don't flicker UI
                    let response;
                    try {
                        response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
                    } catch (err) {
                        logDebug("Injecting script for chat context...");
                        await chrome.scripting.executeScript({
                            target: { tabId: tab.id },
                            files: ['content.js']
                        });
                        await new Promise(resolve => setTimeout(resolve, 500));
                        response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
                    }
                    
                    if (response && response.content) {
                        logDebug(`Context read: ${response.content.length} chars`);
                        const contextBlock = `\n\n[Active Browser Context]\nURL: ${tab.url}\nTitle: ${tab.title}\nContent:\n${response.content.slice(0, 8000)}`; // Limit size
                        finalMessage += contextBlock;
                    } else {
                        logDebug("Context read failed or empty.");
                    }
                }
            } catch (e) {
                logDebug(`Context error: ${e.message}`);
                console.error("Failed to read page context:", e);
            }
        }
                console.warn("Context read failed:", e);
            }
        }

        // Request with Long Timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minutes

        try {
            const response = await fetch(`${API_BASE}/chat/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: SESSION_ID,
                    message: finalMessage
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            let rawResponse = data.response;
            let displayHtml = "";

            // 1. Handle JSON Parsing Failures (Raw Text)
            if (rawResponse.startsWith("[SGR Parsing Failed]")) {
                const rawText = rawResponse.replace("[SGR Parsing Failed]", "").trim();
                displayHtml = `
                    <div style="border: 1px solid #ffcc00; background: #fffbe6; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
                        <strong style="color: #d48806;">⚠️ Model Output Format Error</strong><br>
                        <small>The model failed to produce valid JSON, but here is the raw output:</small>
                    </div>
                    ${formatMessage(rawText)}
                `;
            } 
            // 2. Handle "Thinking" UI
            else if (rawResponse.includes("thinking:")) {
                // Expected format: "thinking: <trace>\n\n<response>"
                // We use a regex to capture the thinking part and the rest
                const match = rawResponse.match(/thinking:\s*([\s\S]*?)\n\n([\s\S]*)/);
                
                if (match) {
                    const thinking = match[1];
                    const finalAnswer = match[2];
                    
                    displayHtml = `
                        <details style="margin-bottom: 10px; border-left: 2px solid #ccc; padding-left: 10px;">
                            <summary style="cursor: pointer; color: #666; font-size: 0.9em;">💭 Reasoning Process</summary>
                            <div style="margin-top: 5px; color: #555; font-size: 0.9em; white-space: pre-wrap;">${formatMessage(thinking)}</div>
                        </details>
                        ${formatMessage(finalAnswer)}
                    `;
                } else {
                    // Fallback if regex fails but "thinking:" is present
                    displayHtml = formatMessage(rawResponse);
                }
            } 
            // 3. Standard Response
            else {
                displayHtml = formatMessage(rawResponse);
            }

            responseDiv.innerHTML = displayHtml;
            messageHistory.push({ role: "assistant", content: rawResponse }); // Save raw for history
            saveHistory();

        } catch (error) {
            if (error.name === 'AbortError') {
                responseDiv.innerHTML = `<span style="color:red">⏱️ Request timed out (180s). The local model is too slow.</span>`;
            } else {
                responseDiv.innerHTML = `<span style="color:red">❌ Error: ${error.message}</span>`;
                if (error.message.includes("Failed to fetch")) {
                    responseDiv.innerHTML += `<br><small>Check if ECE Backend is running on port 8000</small>`;
                }
            }
        } finally {
            sendButton.disabled = false;
            sendButton.textContent = "Send";
            promptInput.focus();
        }
    }

    // --- Bindings ---
    sendButton.addEventListener('click', sendMessage);
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Initialize
    loadHistory();
});
