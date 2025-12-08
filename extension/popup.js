document.getElementById('connectBtn').addEventListener('click', async () => {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = "Connecting...";
  
  try {
    // Simple health check or chat request
    const response = await fetch("http://localhost:8000/chat/health", { // Assuming a health endpoint or just checking connectivity
        method: "GET"
    }).catch(err => null); // Catch network errors

    // Since we don't have a dedicated health endpoint in the recipe yet, we might just try to hit the root or expect a 405 on GET /chat if it's POST only.
    // Let's just try to reach the server.
    
    if (response || (await fetch("http://localhost:8000/docs")).ok) {
        statusDiv.textContent = "✅ Connected to Coda Core";
        statusDiv.style.color = "green";
    } else {
        throw new Error("Network error");
    }
  } catch (error) {
    statusDiv.textContent = "❌ Connection Failed: " + error.message;
    statusDiv.style.color = "red";
  }
});
