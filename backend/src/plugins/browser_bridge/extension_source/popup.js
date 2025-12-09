// Browser Bridge Popup Logic

class BrowserBridge {
  constructor() {
    this.eceUrl = 'http://localhost:8000';
    this.init();
  }

  init() {
    // Get DOM elements
    this.draftPrompt = document.getElementById('draftPrompt');
    this.getContextBtn = document.getElementById('getContextBtn');
    this.contextResult = document.getElementById('contextResult');
    this.scrapeCurrentBtn = document.getElementById('scrapeCurrentBtn');
    this.saveChatBtn = document.getElementById('saveChatBtn');
    this.statusMessage = document.getElementById('statusMessage');

    // Add event listeners
    this.getContextBtn.addEventListener('click', () => this.getContext());
    this.scrapeCurrentBtn.addEventListener('click', () => this.scrapeCurrentPage());
    this.saveChatBtn.addEventListener('click', () => this.saveCurrentChat());

    // Load any saved settings
    this.loadSettings();
  }

  showStatus(message, type = 'success') {
    this.statusMessage.textContent = message;
    this.statusMessage.className = `status ${type}`;
    setTimeout(() => {
      this.statusMessage.style.display = 'none';
    }, 3000);
  }

  async getContext() {
    const prompt = this.draftPrompt.value.trim();
    if (!prompt) {
      this.showStatus('Please enter a draft prompt', 'error');
      return;
    }

    try {
      this.getContextBtn.textContent = 'Getting Context...';
      this.getContextBtn.disabled = true;

      const response = await fetch(`${this.eceUrl}/v1/browser/context`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          draft_prompt: prompt,
          max_results: 10
        })
      });

      const data = await response.json();

      if (data.success) {
        this.contextResult.textContent = data.context;
        this.contextResult.style.display = 'block';
        this.showStatus(`Retrieved ${data.retrieved_count} context items`);
      } else {
        this.showStatus('Failed to retrieve context', 'error');
      }
    } catch (error) {
      console.error('Error getting context:', error);
      this.showStatus('Error connecting to ECE server', 'error');
    } finally {
      this.getContextBtn.textContent = 'Get Context';
      this.getContextBtn.disabled = false;
    }
  }

  async scrapeCurrentPage() {
    try {
      // Execute content script to extract chat data from current page
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      
      // Send message to content script to extract data
      const result = await chrome.tabs.sendMessage(tab.id, {action: 'extractChat'});
      
      if (result.success && result.messages) {
        this.showStatus(`Scraped ${result.messages.length} messages from page`);
        // Store the scraped data temporarily for saving
        await chrome.storage.local.set({scrapedChat: result});
      } else {
        this.showStatus('No chat data found on page', 'error');
      }
    } catch (error) {
      console.error('Error scraping page:', error);
      this.showStatus('Error scraping current page', 'error');
    }
  }

  async saveCurrentChat() {
    // First try to get scraped data from storage
    const {scrapedChat} = await chrome.storage.local.get(['scrapedChat']);
    
    if (!scrapedChat || !scrapedChat.messages) {
      // If no scraped data, try to scrape current page
      await this.scrapeCurrentPage();
      const {scrapedChat: updatedScraped} = await chrome.storage.local.get(['scrapedChat']);
      if (!updatedScraped || !updatedScraped.messages) {
        this.showStatus('No chat data to save', 'error');
        return;
      }
    }

    try {
      this.saveChatBtn.textContent = 'Saving...';
      this.saveChatBtn.disabled = true;

      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      
      const response = await fetch(`${this.eceUrl}/v1/browser/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: scrapedChat.messages,
          source_url: tab.url,
          session_id: `browser_${new Date().getTime()}`
        })
      });

      const data = await response.json();

      if (data.success) {
        this.showStatus(data.message);
        // Clear the scraped data after successful save
        await chrome.storage.local.remove('scrapedChat');
      } else {
        this.showStatus('Failed to save chat', 'error');
      }
    } catch (error) {
      console.error('Error saving chat:', error);
      this.showStatus('Error saving to ECE server', 'error');
    } finally {
      this.saveChatBtn.textContent = 'Save Current Chat';
      this.saveChatBtn.disabled = false;
    }
  }

  async loadSettings() {
    // Load saved settings like ECE URL
    const settings = await chrome.storage.sync.get(['eceUrl']);
    if (settings.eceUrl) {
      this.eceUrl = settings.eceUrl;
    }
  }

  async saveSettings() {
    // Save settings like ECE URL
    await chrome.storage.sync.set({eceUrl: this.eceUrl});
  }
}

// Initialize the browser bridge when popup loads
document.addEventListener('DOMContentLoaded', () => {
  new BrowserBridge();
});

// Background script placeholder
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getContext') {
    // Handle context requests from other parts of the extension
    fetch(`${this.eceUrl}/v1/browser/context`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(request)
    })
    .then(response => response.json())
    .then(data => sendResponse(data))
    .catch(error => sendResponse({success: false, error: error.toString()}));
    
    return true; // Keep message channel open for async response
  }
  return false;
});