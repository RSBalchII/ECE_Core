chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'queryMemories') {
    queryMemoriesFromCozoDB(request.query)
      .then(memories => ({
        success: true,
        memories: memories,
        summary: generateSummary(memories)
      }))
      .then(result => sendResponse(result))
      .catch(err => {
        console.error('[Sovereign] Error querying memories:', err);
        sendResponse({
          success: false,
          error: err.message,
          summary: null
        });
      });
    return true; // Keep channel open for async response
  }
});

async function queryMemoriesFromCozoDB(userInput) {
  try {
    // Attempt to hit the Local Bridge (webgpu_bridge.py)
    // The bridge runs on port 8080 if using start-bridge.bat, or random port 9000-9999
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    // Try ports for the bridge (8080 is the default when using start-bridge.bat, others are random)
    const commonPorts = [8080, 9000, 9001, 9002, 9003, 9004, 9005, 9006, 9007, 9008, 9009, 9010, 9011, 9012, 9013, 9014, 9015];
    let response = null;
    let lastError = null;

    for (const port of commonPorts) {
      try {
        // First, try to ping the health endpoint to see if there's a bridge running
        const healthUrl = `http://localhost:${port}/health`;
        let healthResponse;

        try {
          healthResponse = await fetch(healthUrl, {
            method: 'GET',
            signal: controller.signal
          });
        } catch (healthError) {
          console.log(`[Sovereign] Health check failed for port ${port}:`, healthError.message);
          continue; // Try next port
        }

        if (!healthResponse.ok) {
          console.log(`[Sovereign] Health check failed for port ${port}, status: ${healthResponse.status}`);
          continue; // Try next port
        }

        console.log(`[Sovereign] Bridge detected on port ${port}, testing memory search...`);

        // Now try the memory search endpoint
        const searchUrl = `http://localhost:${port}/memories/search`;

        // Try with the default token first
        response = await fetch(searchUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer sovereign-secret'  // Default token from start-bridge.bat
          },
          body: JSON.stringify({ query: userInput }),
          signal: controller.signal
        });

        if (response.ok) {
          console.log(`[Sovereign] Successfully connected to bridge at port ${port}`);
          clearTimeout(timeoutId);
          return response.json();
        } else if (response.status === 401) {
          // If unauthorized, try without token (some configurations might not require it)
          console.log(`[Sovereign] Trying without auth token for port ${port}`);
          response = await fetch(searchUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: userInput }),
            signal: controller.signal
          });

          if (response.ok) {
            console.log(`[Sovereign] Successfully connected to bridge at port ${port} (no auth)`);
            clearTimeout(timeoutId);
            return response.json();
          }
        }
      } catch (e) {
        lastError = e;
        console.log(`[Sovereign] Trying bridge port ${port} failed:`, e.message);
        continue;
      }
    }

    // If all ports failed, use the last error
    clearTimeout(timeoutId);
    throw lastError || new Error(`All bridge ports failed. No connection to WebGPU bridge available. Is the bridge running?`);
  } catch (e) {
    console.warn('[Sovereign] Backend unavailable, falling back to simulated response...', e.message);
    // In the future, this can connect directly to IndexedDB via shared worker
    // For now, return simulated data
    return [
      {
        content: "This is a simulated memory based on your input: " + userInput.substring(0, 100) + "...",
        timestamp: new Date().toISOString(),
        relevance: 0.8
      }
    ];
  }
}

function generateSummary(memories) {
  if (!memories || memories.length === 0) return null;

  const maxMemories = 3;
  const relevant = memories.slice(0, maxMemories);

  return relevant
    .map((m, idx) => `[Memory ${idx + 1}] ${m.content.substring(0, 150)}...`)
    .join('\n');
}