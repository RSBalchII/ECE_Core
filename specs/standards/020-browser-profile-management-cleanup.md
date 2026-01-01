# Standard 020: Browser Profile Management and Cleanup

## What Happened?
Repeatedly launching and killing modern browsers (Edge/Chrome) could leave orphaned child processes or fill up the temporary directory with user data profiles. This created a "Memory Leak" risk where temporary browser profiles could accumulate over time and crash the host OS.

## The Cost
- Potential disk space issues from accumulated temporary browser profiles
- Risk of system instability from orphaned processes
- 1 hour spent implementing proper browser profile management and cleanup

## The Rule
1. **Unique Profile Directories**: Use unique temporary directories for each browser instance:
   ```python
   import tempfile
   temp_dir = tempfile.gettempdir()
   f"--user-data-dir={temp_dir}/anchor_ghost_{int(time.time())}"
   ```

2. **Performance Optimization Flags**: Include performance optimization flags to reduce resource usage:
   ```python
   # Add these flags to browser launch command
   "--disable-background-timer-throttling",
   "--disable-backgrounding-occluded-windows", 
   "--disable-renderer-backgrounding",
   "--disable-ipc-flooding-protection",
   "--disable-background-media-suspend"
   ```

3. **Cleanup Old Profiles**: Implement automatic cleanup of old temporary profiles:
   ```python
   async def _cleanup_old_profiles(self):
       # Remove directories older than 1 day
       cutoff_time = datetime.now() - timedelta(days=1)
       # Implementation to remove old temporary directories
   ```

4. **Proper Process Termination**: Ensure browser processes are fully terminated before launching new ones

This standard prevents disk space issues and system instability from temporary browser profiles.