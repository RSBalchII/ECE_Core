document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const promptInput = document.getElementById('prompt');
    const sendButton = document.getElementById('send');
    const clearButton = document.getElementById('clear-btn');
    const saveMemoryButton = document.getElementById('save-memory-btn');

    let messageHistory = [];

    // --- Persistence ---
    function loadHistory() {
        chrome.storage.local.get("chat_history", (result) => {
            if (result.chat_history) {
                messageHistory = result.chat_history;
                // Render history
                if (messageHistory.length === 0) {
                    appendMessage('assistant', 'Hello. I am Coda. I am listening.', false);
                } else {
                    messageHistory.forEach(msg => {
                        appendMessage(msg.role, msg.content, false);
                    });
                }
            } else {
                // Default welcome message
                appendMessage('assistant', 'Hello. I am Coda. I am listening.', false);
            }
        });
    }

    function saveHistory() {
        chrome.storage.local.set({ chat_history: messageHistory });
    }

    clearButton.addEventListener('click', () => {
        chrome.storage.local.remove("chat_history");
        messageHistory = [];
        chatContainer.innerHTML = '';
        appendMessage('assistant', 'Memory cleared.', false);
    });

    // --- Ingestion Handler ---
    saveMemoryButton.addEventListener('click', async () => {
        saveMemoryButton.disabled = true;
        saveMemoryButton.textContent = "Saving...";
        
        try {
            // 1. Get active tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab) throw new Error("No active tab found");

            // 2. Request page content from content script
            const response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
            
            if (!response || !response.content) {
                throw new Error("No content received from page");
            }

            // 3. Send to Backend
            const ingestRes = await fetch('http://localhost:8000/archivist/ingest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer secret-token' // Hardcoded for now, should be config
                },
                body: JSON.stringify({
                    content: response.content,
                    type: response.type || "web_page",
                    adapter: response.adapter || "Generic"
                })
            });

            if (!ingestRes.ok) {
                const errText = await ingestRes.text();
                throw new Error(`Server error: ${ingestRes.status} - ${errText}`);
            }

            const result = await ingestRes.json();
            appendMessage('assistant', `✅ **Memory Ingested**\nID: \`${result.memory_ids[0]}\`\nSource: ${response.adapter}`, false);

        } catch (error) {
            console.error("Ingestion failed:", error);
            appendMessage('assistant', `❌ **Ingestion Failed**\n${error.message}`, false);
        } finally {
            saveMemoryButton.disabled = false;
            saveMemoryButton.textContent = "Save to Memory";
        }
    });

    // --- Markdown Parser ---
    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatMessage(text) {
        // 1. Escape HTML first to prevent XSS and rendering issues
        let formatted = escapeHtml(text);

        // 2. Code Blocks: ```lang ... ```
        // We use a non-greedy match for content
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const language = lang || 'text';
            return `<pre><div class="code-header">${language}</div><code>${code}</code></pre>`;
        });

        // 3. Inline Code: `code`
        formatted = formatted.replace(/`([^`]+)`/g, '<code class="inline">$1</code>');

        // 4. Action Blocks: :::action ({...}) :::
        // We want to hide the raw block and show a card instead.
        // But wait, if we replace it here, it will be part of the innerHTML.
        // We need to attach event listeners to the buttons.
        // Since we are setting innerHTML repeatedly during stream, we can't easily attach listeners until the end?
        // Or we can use onclick attributes (not recommended in extensions usually, but might work if inline scripts allowed? No, CSP).
        // Better approach: Render a placeholder, and then after rendering, find the placeholder and hydrate it?
        // Or just render a button with a data-code attribute and use a global event listener on the container.
        
        formatted = formatted.replace(/:::action\s*({.*?})\s*:::/g, (match, jsonStr) => {
            try {
                // Validate JSON
                const action = JSON.parse(jsonStr);
                // Encode code for attribute
                const codeEncoded = encodeURIComponent(action.code);
                return `
                    <div class="action-card">
                        <div class="action-header">Browser Action</div>
                        <div class="action-code">${escapeHtml(action.code.slice(0, 100))}${action.code.length > 100 ? '...' : ''}</div>
                        <button class="action-btn" data-code="${codeEncoded}">Run Script</button>
                    </div>
                `;
            } catch (e) {
                return `<div class="error">Invalid Action Block</div>`;
            }
        });

        return formatted;
    }

    // --- Global Event Listener for Action Buttons ---
    chatContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('action-btn')) {
            const btn = e.target;
            const code = decodeURIComponent(btn.getAttribute('data-code'));
            
            btn.disabled = true;
            btn.textContent = "Running...";
            
            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (!tab) throw new Error("No active tab");

                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: (codeToRun) => {
                        // Execute in MAIN world to access window variables, bypassing inline script CSP
                        try {
                            window.eval(codeToRun);
                        } catch (e) {
                            console.error("Coda Execution Error:", e);
                            throw e;
                        }
                    },
                    args: [code],
                    world: 'MAIN'
                });

                btn.textContent = "Executed";
                btn.style.backgroundColor = "#28a745";
            } catch (err) {
                console.error("Script execution failed", err);
                btn.textContent = "Failed";
                btn.style.backgroundColor = "#dc3545";
                btn.disabled = false;
            }
        }
    });

    // --- UI Logic ---
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function appendMessage(role, text, save = true) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'user-message' : 'coda-message'}`;
        
        // If it's a system message (like "Reading page..."), style it differently
        if (role === 'system') {
            msgDiv.style.fontStyle = 'italic';
            msgDiv.style.fontSize = '0.8em';
            msgDiv.style.color = '#888';
            msgDiv.textContent = text; // No markdown for system status
        } else {
            msgDiv.innerHTML = formatMessage(text);
        }

        chatContainer.appendChild(msgDiv);
        scrollToBottom();

        if (save && role !== 'system') {
            // We don't save system status messages to history, but we do save user/assistant messages
            // Note: The caller handles pushing to messageHistory array usually
        }
        return msgDiv;
    }

    async function sendMessage() {
        const text = promptInput.value.trim();
        if (!text) return;

        // UI Updates
        promptInput.value = '';
        appendMessage('user', text, false); // We push to history manually below
        
        // Add to history
        messageHistory.push({ role: "user", content: text });
        saveHistory();

        const responseDiv = appendMessage('assistant', '', false); // Placeholder
        
        // Check for context injection
        const includeContext = document.getElementById('include-context').checked;
        let contextMessage = null;

        if (includeContext) {
            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tab && tab.id) {
                    const statusMsg = appendMessage('system', 'Reading page...', false);
                    const response = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAGE_CONTENT" });
                    if (response && response.content) {
                        contextMessage = { 
                            role: "system", 
                            content: "## ACTIVE BROWSER TAB CONTEXT\n\n" + response.content 
                        };
                        statusMsg.remove();
                    }
                }
            } catch (e) {
                console.warn("Failed to read page context:", e);
            }
        }

        // Prepare payload
        let payloadMessages = [...messageHistory];
        if (contextMessage) {
            // Insert context before the latest user message
            // payloadMessages is [..., user_msg]
            // We want [..., context, user_msg]
            payloadMessages.splice(payloadMessages.length - 1, 0, contextMessage);
        }

        try:
            const response = await fetch('http://127.0.0.1:8000/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: "browser-session",
                    message: text,
                    messages: payloadMessages,
                    stream: true
                })
            });

            if (!response.ok) throw new Error(`API Error: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let assistantMessage = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') continue;
                        
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.chunk) {
                                assistantMessage += data.chunk;
                                // Live update with formatting
                                responseDiv.innerHTML = formatMessage(assistantMessage);
                            } else if (data.error) {
                                responseDiv.innerHTML += `<br><span style="color:red">[Error: ${data.error}]</span>`;
                            }
                        } catch (e) {
                            console.error("Failed to parse SSE data", e);
                        }
                        scrollToBottom();
                    }
                }
            }
            
            // Final save
            messageHistory.push({ role: "assistant", content: assistantMessage });
            saveHistory();

        } catch (error) {
            responseDiv.innerHTML += `<br><span style="color:red">[Error: ${error.message}]</span>`;
        }
    }

    sendButton.addEventListener('click', sendMessage);
    promptInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Initialize
    loadHistory();
});
