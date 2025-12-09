// Content script for extracting chat data from Gemini and other platforms

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extractChat') {
    const chatData = extractChatData();
    sendResponse({success: true, messages: chatData});
  }
  return true; // Keep message channel open for async response
});

function extractChatData() {
  // Detect the current platform and extract chat data accordingly
  const url = window.location.href;
  
  if (url.includes('gemini.google.com')) {
    return extractGeminiChat();
  } else if (url.includes('chat.openai.com')) {
    return extractChatGPTChat();
  } else if (url.includes('claude.ai') || url.includes('anthropic.com')) {
    return extractClaudeChat();
  } else {
    // Generic extraction for unknown platforms
    return extractGenericChat();
  }
}

function extractGeminiChat() {
  const messages = [];
  
  try {
    // Look for Gemini chat message containers
    const messageElements = document.querySelectorAll('[data-testid="chat-message"], [class*="message"], [class*="conversation"]');
    
    if (messageElements.length === 0) {
      // Alternative selectors for Gemini
      messageElements = document.querySelectorAll('.chat-message, .message-container, [role="list"] [role="listitem"]');
    }
    
    messageElements.forEach((element, index) => {
      const userElement = element.querySelector('[data-testid="user-message"], .user-content, [class*="user"]');
      const aiElement = element.querySelector('[data-testid="model-message"], .model-content, [class*="model"], [class*="assistant"]');
      
      if (userElement) {
        const content = extractTextFromElement(userElement);
        messages.push({
          role: 'user',
          content: content,
          timestamp: new Date().toISOString()
        });
      }
      
      if (aiElement) {
        const content = extractTextFromElement(aiElement);
        messages.push({
          role: 'assistant',
          content: content,
          timestamp: new Date().toISOString()
        });
      }
    });
  } catch (error) {
    console.error('Error extracting Gemini chat:', error);
  }
  
  return messages;
}

function extractChatGPTChat() {
  const messages = [];
  
  try {
    // ChatGPT specific selectors
    const conversationElements = document.querySelectorAll('[data-message-author-role]');
    
    conversationElements.forEach(element => {
      const role = element.getAttribute('data-message-author-role');
      const contentElement = element.querySelector('[class*="text"], [class*="content"], p, div');
      
      if (role && contentElement) {
        const content = extractTextFromElement(contentElement);
        messages.push({
          role: role,
          content: content,
          timestamp: new Date().toISOString()
        });
      }
    });
  } catch (error) {
    console.error('Error extracting ChatGPT chat:', error);
  }
  
  return messages;
}

function extractClaudeChat() {
  const messages = [];
  
  try {
    // Claude specific selectors
    const messageContainers = document.querySelectorAll('[data-is-streaming], [class*="message"], [class*="conversation"]');
    
    messageContainers.forEach(container => {
      const senderElement = container.querySelector('[class*="sender"], [class*="role"]');
      const contentElement = container.querySelector('[class*="content"], [class*="text"], [class*="message"]');
      
      let role = 'assistant';
      if (senderElement) {
        const senderText = senderElement.textContent.toLowerCase();
        if (senderText.includes('you') || senderText.includes('human')) {
          role = 'user';
        }
      }
      
      if (contentElement) {
        const content = extractTextFromElement(contentElement);
        messages.push({
          role: role,
          content: content,
          timestamp: new Date().toISOString()
        });
      }
    });
  } catch (error) {
    console.error('Error extracting Claude chat:', error);
  }
  
  return messages;
}

function extractGenericChat() {
  const messages = [];
  
  try {
    // Generic extraction looking for common chat patterns
    const possibleMessageElements = document.querySelectorAll(
      '[class*="message"], [class*="chat"], [class*="conversation"], .chat-message, .message-bubble'
    );
    
    possibleMessageElements.forEach(element => {
      // Try to determine if this is a user or assistant message
      const elementText = element.textContent.toLowerCase();
      const parentClasses = element.parentElement ? element.parentElement.className.toLowerCase() : '';
      
      let role = 'assistant';
      if (elementText.includes('you') || parentClasses.includes('user') || parentClasses.includes('human')) {
        role = 'user';
      }
      
      const content = extractTextFromElement(element);
      
      if (content.trim().length > 20) { // Avoid very short or empty messages
        messages.push({
          role: role,
          content: content,
          timestamp: new Date().toISOString()
        });
      }
    });
  } catch (error) {
    console.error('Error extracting generic chat:', error);
  }
  
  return messages;
}

function extractTextFromElement(element) {
  if (!element) return '';
  
  // Remove any code blocks, images, or other non-text elements from extraction
  const clone = element.cloneNode(true);
  const codeBlocks = clone.querySelectorAll('pre, code, [class*="code"], [class*="terminal"]');
  codeBlocks.forEach(cb => cb.remove());
  
  // Extract text content and clean it up
  let text = clone.textContent || clone.innerText || '';
  text = text.trim();
  
  // Remove extra whitespace and clean up
  text = text.replace(/\s+/g, ' ').trim();
  
  return text;
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    console.log('ECE Browser Bridge content script loaded for chat extraction');
  });
} else {
  console.log('ECE Browser Bridge content script loaded for chat extraction');
}

// Also listen for dynamic content (in case of single-page applications)
const observer = new MutationObserver((mutations) => {
  // Could add logic here to detect when new chat messages appear
  // and potentially auto-extract them or notify the popup
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});