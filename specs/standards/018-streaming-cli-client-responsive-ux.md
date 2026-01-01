# Standard 018: Streaming CLI Client for Responsive UX

## What Happened?
The anchor.py CLI client was using `stream=False` for API requests, causing the terminal to hang during long responses from 7B models. This created a poor user experience where the terminal would freeze for 10-20 seconds during long answers, breaking the "fluid" feeling of a memory assistant.

## The Cost
- Poor user experience with hanging terminal during long responses
- 1+ hours spent updating anchor.py to use streaming for better UX
- Users experiencing "frozen" terminal during model responses
- Break in the conversational flow of the memory assistant

## The Rule
1. **Enable Streaming**: Always use `stream=True` when making chat completion requests from CLI clients:
   ```python
   response = requests.post(
       f"{BRIDGE_URL}/v1/chat/completions",
       json={
           "messages": history,
           "stream": True  # Enable streaming for better UX
       },
       stream=True,  # Enable streaming at request level
       timeout=120
   )
   ```

2. **Process Streaming Response**: Handle the streaming response line by line to provide immediate feedback:
   ```python
   for line in response.iter_lines(decode_unicode=True):
       if line and line.startswith("data: "):
           data_str = line[6:]  # Remove "data: " prefix
           if data_str.strip() == "[DONE]":
               break
           # Process and display content as it arrives
   ```

3. **Real-time Character Display**: Print characters as they arrive to provide immediate feedback:
   ```python
   print(content, end="", flush=True)
   ```

4. **Maintain Conversation Context**: Properly accumulate streamed content to maintain conversation history:
   ```python
   ai_text += content  # Accumulate content for history
   history.append({"role": "assistant", "content": ai_text})
   ```

This standard ensures CLI clients provide responsive feedback during long model responses while maintaining proper conversation context.