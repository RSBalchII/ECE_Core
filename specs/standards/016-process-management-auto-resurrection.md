# Standard 016: Process Management and Auto-Resurrection for Browser Engines

## What Happened?
The Ghost Engine (headless browser) would sometimes crash or hang, leaving zombie processes that would prevent new browser instances from starting. When the ResurrectionManager tried to launch a new browser, it would fail because the previous process was still holding onto resources like the remote debugging port (9222).

## The Cost
- 2+ hours spent debugging "Zombie Process" risk where browser resurrection would fail
- Multiple failed attempts to restart the Ghost Engine
- System becoming unresponsive when browser processes hung
- Users experiencing "Total System Failure" when new browsers couldn't start due to port conflicts

## The Rule
1. **Process Cleanup First**: Before launching a new browser process, always kill any existing browser processes:
   ```python
   async def kill_existing_browsers(self):
       import psutil
       for proc in psutil.process_iter(['pid', 'name']):
           if proc.info['name'].lower() in ['msedge.exe', 'chrome.exe', 'chromium-browser']:
               proc.kill()
   ```

2. **Explicit Port Assignment**: Always specify a consistent remote debugging port to avoid conflicts:
   ```python
   # Add to browser launch command
   "--remote-debugging-port=9222"
   ```

3. **Wait for Full Initialization**: Increase wait time after launching browser to ensure full initialization before checking connection:
   ```python
   await asyncio.sleep(5)  # Increased from 3 seconds
   ```

4. **Proper Process Termination**: Ensure browser processes are fully terminated before launching new ones:
   ```python
   # Always call terminate() then wait() or kill() if needed
   process.terminate()
   process.wait(timeout=5)
   ```

This standard ensures that browser resurrection works reliably by preventing port conflicts and zombie processes.