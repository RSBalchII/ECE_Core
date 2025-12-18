document.getElementById('connectBtn').addEventListener('click', async () => {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = "Connecting...";
  
  try {
    // Simple health check
    const response = await fetch("http://localhost:8000/health", {
        method: "GET"
    }).catch(err => null); // Catch network errors

    if (response && response.ok) {
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
