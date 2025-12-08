// extension/content.js - Coda Bridge (Modular Architecture v2.1)

console.log("[Coda Bridge] Content adapter system active.");

// ==========================================
// 1. ADAPTER DEFINITIONS (The "Hands")
// ==========================================

const GeminiAdapter = {
    name: "Gemini",
    matches: (url) => url.includes("gemini.google.com") || url.includes("aistudio.google.com"),
    selectors: {
        INPUT_BOX: 'div.ql-editor, div[contenteditable="true"]',
        SEND_BUTTON: 'button[aria-label*="Send"]',
        MESSAGE_BUBBLE: '.message-content, .query-text, .model-response-text, [data-test-id="message-content"]',
        NOISE: '.params-button, .edit-button, .regenerate-button, svg, img, .speech_icon'
    },
    clean: (text) => text.replace(/[\u200B-\u200D\uFEFF]/g, '').replace(/\s+/g, ' ').trim()
};

const ChatGPTAdapter = {
    name: "ChatGPT",
    matches: (url) => url.includes("chatgpt.com"),
    selectors: {
        INPUT_BOX: '#prompt-textarea',
        SEND_BUTTON: '[data-testid="send-button"]',
        MESSAGE_BUBBLE: '[data-message-author-role]',
        NOISE: '.text-xs, button, svg'
    },
    clean: (text) => text.trim()
};

const ClaudeAdapter = {
    name: "Claude",
    matches: (url) => url.includes("claude.ai"),
    selectors: {
        INPUT_BOX: 'div[contenteditable="true"]',
        SEND_BUTTON: 'button[aria-label*="Send"]',
        MESSAGE_BUBBLE: '.font-claude-message',
        NOISE: ''
    },
    clean: (text) => text.trim()
};

// The "Universal Fallback" - Logic will eventually route to Port 8082 Vision
const GenericAdapter = {
    name: "Generic Web",
    matches: () => true, 
    selectors: {},
    clean: (text) => text.replace(/\s+/g, ' ').trim(),
    extract: () => document.body.innerText
};

// ==========================================
// 2. THE FACTORY
// ==========================================

function detectAdapter() {
    const url = window.location.hostname;
    if (GeminiAdapter.matches(url)) return GeminiAdapter;
    if (ChatGPTAdapter.matches(url)) return ChatGPTAdapter;
    if (ClaudeAdapter.matches(url)) return ClaudeAdapter;
    return GenericAdapter;
}

const CurrentAdapter = detectAdapter();
console.log(`[Coda Bridge] Active Adapter: ${CurrentAdapter.name}`);

// ==========================================
// 3. CORE LOGIC
// ==========================================

function getCleanText(element) {
    if (!element) return "";
    const clone = element.cloneNode(true);
    
    if (CurrentAdapter.selectors.NOISE) {
        clone.querySelectorAll(CurrentAdapter.selectors.NOISE).forEach(el => el.remove());
    }
    
    return CurrentAdapter.clean(clone.innerText);
}

function snapshotChatHistory() {
    // Phase 2 Goal: If Generic, trigger Vision Service on Port 8082
    if (CurrentAdapter.name === "Generic Web") {
        return [CurrentAdapter.extract()]; 
    }

    const messages = [];
    const bubbles = document.querySelectorAll(CurrentAdapter.selectors.MESSAGE_BUBBLE);
    
    bubbles.forEach(bubble => {
        const text = getCleanText(bubble);
        if (text.length > 2 && !text.includes("Typing")) {
            messages.push(text);
        }
    });
    return messages;
}

function injectContextToInput(contextText) {
    // "Hands" require DOM access. Vision cannot do this yet.
    if (CurrentAdapter.name === "Generic Web") {
        console.warn("[Coda Bridge] Cannot inject into generic page without selectors.");
        return false;
    }

    const inputBox = document.querySelector(CurrentAdapter.selectors.INPUT_BOX);
    if (!inputBox) {
        console.error("Input box not found for " + CurrentAdapter.name);
        return false;
    }

    const p = document.createElement('p');
    p.innerHTML = `<strong>[Coda Context]:</strong> ${contextText}<br>`;
    p.style.color = '#4a90e2';
    
    inputBox.prepend(p);
    inputBox.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
}

// ==========================================
// 4. COMMUNICATION BUS
// ==========================================

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "GET_PAGE_CONTENT") {
        const history = snapshotChatHistory();
        const fullTranscript = history.join("\n\n---\n\n");
        sendResponse({ 
            content: fullTranscript, 
            type: CurrentAdapter.name.toLowerCase() + "_transcript",
            adapter: CurrentAdapter.name
        });
    }
    
    if (request.action === "INJECT_CONTEXT") {
        const success = injectContextToInput(request.text);
        sendResponse({ success: success });
    }
    
    return true;
});
