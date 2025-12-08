// Coda Bridge - Background Service Worker
// Handles communication between the browser and the Coda API

const API_URL = "http://localhost:8000/chat";

chrome.runtime.onInstalled.addListener(() => {
  console.log("Coda Bridge installed.");
});

// Example: Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    sendResponse({ status: "alive" });
  }
  return true;
});
