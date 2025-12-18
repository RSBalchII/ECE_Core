// content.js - Coda Chrome Extension Content Script
// "The Eyes" of the Context Engine

(function() {
    // Prevent multiple injections
    if (window.hasRun) return;
    window.hasRun = true;

    console.log("Coda: Content script loaded on:", window.location.href);

    /**
     * Extracts the main content from the page, removing clutter.
     * This is a simplified "Readability" implementation.
     */
    function extractPageContent() {
        // 1. Clone the body to avoid modifying the actual page
        const clone = document.body.cloneNode(true);

        // 2. Remove non-content elements (scripts, styles, ads, navs)
        const selectorsToRemove = [
            'script', 'style', 'noscript', 'iframe', 'svg',
            'header', 'footer', 'nav', 'aside',
            '.ad', '.ads', '.advertisement',
            '[role="banner"]', '[role="navigation"]', '[role="contentinfo"]',
            '#sidebar', '.sidebar', '#comments', '.comments'
        ];

        selectorsToRemove.forEach(selector => {
            const elements = clone.querySelectorAll(selector);
            elements.forEach(el => el.remove());
        });

        // 3. Extract text from what remains
        // We use a TreeWalker to get text nodes and join them with newlines
        let textContent = "";
        const walker = document.createTreeWalker(
            clone,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Filter out empty or whitespace-only nodes
                    if (!node.textContent.trim()) return NodeFilter.FILTER_REJECT;
                    // Filter out hidden nodes (simple check)
                    if (node.parentElement && node.parentElement.offsetParent === null) return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        let node;
        while (node = walker.nextNode()) {
            textContent += node.textContent.trim() + "\n";
        }

        // 4. Clean up multiple newlines
        textContent = textContent.replace(/\n{3,}/g, "\n\n");

        return textContent.trim();
    }

    /**
     * Message Listener
     * Handles requests from sidepanel.js or background.js
     */
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "GET_PAGE_CONTENT") {
            console.log("Coda: Received GET_PAGE_CONTENT request");
            try {
                const content = extractPageContent();
                const title = document.title;
                const url = window.location.href;

                console.log(`Coda: Extracted ${content.length} chars`);

                if (!content || content.trim().length === 0) {
                    throw new Error("Page content is empty or could not be extracted.");
                }

                sendResponse({
                    success: true,
                    content: content,
                    title: title,
                    url: url
                });
            } catch (error) {
                console.error("Coda: Extraction failed", error);
                sendResponse({
                    success: false,
                    error: error.message
                });
            }
        }
        // Return true to indicate we might respond asynchronously (though we responded synchronously above)
        return true;
    });

})();
