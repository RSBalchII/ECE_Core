# Standard 002: Cache API Security Policy

## What Happened?
Browser AI engines were blocked by strict security policies when trying to load models. The Cache API was preventing models from being treated as "data in RAM" rather than "persistent storage", causing initialization failures.

## The Cost
- Multiple failed model loading attempts
- Browser security errors preventing WebGPU initialization
- "Stealth Mode" required to bypass strict policies
- Significant debugging time to understand browser security model

## The Rule
1. **NoCacheStaticFiles Class:** Always implement custom StaticFiles class with proper headers:
   ```python
   class NoCacheStaticFiles(StaticFiles):
       async def __call__(self, scope, receive, send):
           async def send_wrapper(message):
               if message['type'] == 'http.response.start':
                   headers = message.get('headers', [])
                   headers.extend([
                       (b"Cache-Control", b"no-store, no-cache, must-revalidate, proxy-revalidate"),
                       (b"Pragma", b"no-cache"),
                       (b"Expires", b"0"),
                   ])
                   message['headers'] = headers
               await send(message)
           await super().__call__(scope, receive, send_wrapper)
   ```

2. **Force RAM Storage:** Configure headers to force browser to treat models as in-memory data, bypassing strict security policies.

3. **Security Bypass Protocol:** When browser AI engines fail to initialize, first check Cache API policies before debugging other components.