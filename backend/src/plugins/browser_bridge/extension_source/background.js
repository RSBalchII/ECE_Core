// Background script for ECE Browser Bridge

// Handle extension installation and setup
chrome.runtime.onInstalled.addListener(() => {
  console.log('ECE Browser Bridge extension installed');
  
  // Create context menu items if desired
  chrome.contextMenus.create({
    id: 'saveCurrentChat',
    title: 'Save Chat to ECE',
    contexts: ['page', 'selection']
  });
  
  chrome.contextMenus.create({
    id: 'getContext',
    title: 'Get ECE Context',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'saveCurrentChat') {
    chrome.tabs.sendMessage(tab.id, {action: 'extractChat'}, (response) => {
      if (response && response.success) {
        // Save the extracted chat to ECE
        saveChatToECE(response.messages, tab.url);
      }
    });
  } else if (info.menuItemId === 'getContext') {
    // Get context for selected text
    getContextForText(info.selectionText);
  }
});

// Function to save chat data to ECE server
async function saveChatToECE(messages, sourceUrl) {
  try {
    const response = await fetch('http://localhost:8000/v1/browser/ingest', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: messages,
        source_url: sourceUrl,
        session_id: `browser_${new Date().getTime()}`
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log(`Successfully saved ${result.processed_count} messages to ECE`);
      
      // Show notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'Chat Saved to ECE',
        message: result.message
      });
    } else {
      console.error('Failed to save chat:', result);
    }
  } catch (error) {
    console.error('Error saving chat to ECE:', error);
  }
}

// Function to get context for selected text
async function getContextForText(selectedText) {
  try {
    const response = await fetch('http://localhost:8000/v1/browser/context', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        draft_prompt: selectedText,
        max_results: 5
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('Retrieved context from ECE:', result.context);
      
      // Copy context to clipboard or show in notification
      navigator.clipboard.writeText(result.context).then(() => {
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Context Retrieved',
          message: `Copied ${result.retrieved_count} relevant memories to clipboard`
        });
      });
    }
  } catch (error) {
    console.error('Error getting context from ECE:', error);
  }
}

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getContext') {
    fetch('http://localhost:8000/v1/browser/context', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(request)
    })
    .then(response => response.json())
    .then(data => sendResponse(data))
    .catch(error => sendResponse({success: false, error: error.toString()}));
    
    return true; // Keep message channel open for async response
  }
  
  if (request.action === 'saveChat') {
    saveChatToECE(request.messages, request.source_url);
    sendResponse({success: true});
    return true;
  }
  
  return false;
});

// Periodic health check to ECE server
setInterval(async () => {
  try {
    const response = await fetch('http://localhost:8000/v1/browser/health');
    const data = await response.json();
    console.log('ECE Browser Bridge health check:', data);
  } catch (error) {
    console.warn('ECE server not reachable:', error);
    // Could show a warning to the user
  }
}, 30000); // Check every 30 seconds