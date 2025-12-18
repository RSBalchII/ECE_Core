// background.js - Coda Chrome Extension Background Script

// Default settings
const DEFAULT_SETTINGS = {
    captureEnabled: true,
    captureInterval: 5000, // 5 seconds
    ocrEnabled: true, // Enable OCR fallback
    apiEndpoint: 'http://localhost:8000', // Main ECE backend
    sendToBackend: true // Whether to send to main backend
};

// Store current tab's capture state
const tabStates = new Map();

// Initialize extension
chrome.runtime.onInstalled.addListener(() => {
    console.log('Coda: Extension installed');
    
    // Create context menu item
    chrome.contextMenus.create({
        id: 'coda-capture',
        title: 'Coda: Capture Page',
        contexts: ['page', 'selection']
    });
    
    // Set default settings
    chrome.storage.sync.set(DEFAULT_SETTINGS);
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'coda-capture') {
        captureAndSend(tab.id);
    }
});

// Handle runtime messages
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('Coda: Background received message:', request.action);
    
    if (request.action === "captureVisibleTab") {
        // Capture screenshot of current tab
        chrome.tabs.captureVisibleTab(null, { format: 'png', quality: 80 }, (screenshot) => {
            if (chrome.runtime.lastError) {
                console.error('Coda: Screenshot capture failed:', chrome.runtime.lastError);
                sendResponse({ error: chrome.runtime.lastError.message });
            } else {
                sendResponse({ screenshot: screenshot });
            }
        });
        // Keep message channel open for async response
        return true;
    }
    
    return false;
});

// Listen for tab updates to auto-capture
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && DEFAULT_SETTINGS.captureEnabled) {
        // Add small delay to ensure page is fully loaded
        setTimeout(() => {
            captureAndSend(tabId);
        }, 2000);
    }
});

// Main capture and send function
async function captureAndSend(tabId) {
    console.log(`Coda: Attempting to capture tab ${tabId}`);
    
    try {
        // Query the active tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || tab.id !== tabId) {
            console.log(`Coda: Tab ${tabId} is not active, skipping capture`);
            return;
        }
        
        // Skip if already processing this tab
        if (tabStates.get(tabId) === 'processing') {
            console.log(`Coda: Tab ${tabId} already being processed, skipping`);
            return;
        }
        
        tabStates.set(tabId, 'processing');
        
        // Send capture request to content script
        chrome.tabs.sendMessage(tabId, { action: "capturePage" }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('Coda: Content script not available:', chrome.runtime.lastError.message);
                // If content script is not available, try OCR fallback
                attemptOCRDirect(tabId).then(ocrResult => {
                    if (ocrResult.success) {
                        sendToBackend(ocrResult.data);
                    }
                });
                tabStates.delete(tabId);
                return;
            }
            
            if (response && response.success) {
                console.log(`Coda: Content captured from tab ${tabId}`, response.data.method);
                
                // If it was captured via OCR, no need to try again
                if (response.data.method === "ocr") {
                    console.log("Coda: Content already OCR'd, sending to backend");
                    if (DEFAULT_SETTINGS.sendToBackend) {
                        sendToBackend(response.data);
                    }
                    tabStates.delete(tabId);
                    return;
                }
                
                // For DOM-captured content, if it seems insufficient, try OCR
                if (response.data.method === "dom" && isContentInsufficient(response.data.content)) {
                    console.log("Coda: DOM content insufficient, attempting OCR fallback...");
                    attemptOCRDirect(tabId).then(ocrResult => {
                        if (ocrResult.success) {
                            console.log("Coda: OCR fallback successful, sending to backend");
                            if (DEFAULT_SETTINGS.sendToBackend) {
                                sendToBackend(ocrResult.data);
                            }
                        } else {
                            console.log("Coda: OCR fallback failed, sending original DOM content");
                            if (DEFAULT_SETTINGS.sendToBackend) {
                                sendToBackend(response.data);
                            }
                        }
                        tabStates.delete(tabId);
                    });
                } else {
                    // Content seems sufficient, send to backend
                    if (DEFAULT_SETTINGS.sendToBackend) {
                        sendToBackend(response.data);
                    }
                    tabStates.delete(tabId);
                }
            } else {
                console.log(`Coda: Content script capture failed on tab ${tabId}`);
                tabStates.delete(tabId);
            }
        });
    } catch (error) {
        console.error('Coda: Capture error:', error);
        tabStates.delete(tabId);
    }
}

// Check if content is insufficient for processing
function isContentInsufficient(content) {
    if (!content || content.length < 200) {
        return true;
    }
    
    const genericPatterns = [
        /page not found/i,
        /error/i,
        /loading/i,
        /please enable javascript/i,
        /this page requires/i
    ];
    
    return genericPatterns.some(pattern => pattern.test(content));
}

// Direct OCR capture for when content script is unavailable
async function attemptOCRDirect(tabId) {
    return new Promise((resolve) => {
        if (!DEFAULT_SETTINGS.ocrEnabled) {
            resolve({ success: false, error: "OCR disabled" });
            return;
        }
        
        console.log(`Coda: Attempting direct OCR capture on tab ${tabId}`);
        
        // Capture screenshot
        chrome.tabs.captureVisibleTab(null, { format: 'png', quality: 80 }, async (screenshot) => {
            if (chrome.runtime.lastError) {
                console.error('Coda: Direct OCR screenshot failed:', chrome.runtime.lastError);
                resolve({ success: false, error: chrome.runtime.lastError.message });
                return;
            }
            
            try {
                // Remove data URL prefix
                const base64Image = screenshot.split(',')[1];
                
                // Send to OCR service (Vision Sidecar)
                const ocrResult = await fetch('http://localhost:8082/ocr', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        image_base64: base64Image
                    })
                });
                
                if (!ocrResult.ok) {
                    throw new Error(`OCR service error: ${ocrResult.status}`);
                }
                
                const ocrData = await ocrResult.json();
                
                const result = {
                    success: true,
                    data: {
                        method: "ocr_direct",
                        content: ocrData.text,
                        title: `Tab ${tabId} - OCR Capture`,
                        url: `chrome-extension://ocr-capture/${tabId}`,
                        timestamp: new Date().toISOString(),
                        ocr_raw: ocrData.raw_output
                    }
                };
                
                resolve(result);
            } catch (error) {
                console.error('Coda: Direct OCR processing failed:', error);
                resolve({ success: false, error: error.message });
            }
        });
    });
}

// Send data to backend
async function sendToBackend(data) {
    if (!DEFAULT_SETTINGS.sendToBackend) {
        console.log("Coda: Backend sending disabled, skipping");
        return;
    }
    
    try {
        console.log("Coda: Sending data to backend:", data.method, "- Content length:", data.content.length);
        
        const response = await fetch(`${DEFAULT_SETTINGS.apiEndpoint}/archivist/ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer secret-token'
            },
            body: JSON.stringify({
                content: data.content,
                type: 'web_content',
                adapter: 'chrome_extension'
            })
        });
        
        if (!response.ok) {
            throw new Error(`Backend error: ${response.status}`);
        }
        
        console.log("Coda: Data sent to backend successfully");
    } catch (error) {
        console.error("Coda: Failed to send to backend:", error);
    }
}

// Handle tab removal to clean up state
chrome.tabs.onRemoved.addListener((tabId) => {
    tabStates.delete(tabId);
});

console.log("Coda: Background script loaded");