from fastapi import APIRouter, Request, Depends, HTTPException
from src.bootstrap import get_components
from src.security import verify_api_key
from pydantic import BaseModel
from typing import Any, Dict
import time
from src.api.chat import ChatRequest, chat, chat_stream

router = APIRouter()


@router.post('/v1/chat/completions')
async def openai_chat_completions(request_obj: Request, body: Dict[str, Any], authenticated: bool = Depends(verify_api_key)):
    # very small adapter that maps old OpenAI payload to our ChatRequest
    model = body.get('model')
    messages = body.get('messages', [])
    stream = body.get('stream', False)
    system_prompt = None
    session_id = body.get('session_id') or body.get('conversation_id') or 'openai-adapter-session'
    user_message = None
    conversation_buffer = []
    for m in messages:
        role = m.get('role')
        content = m.get('content')
        if role == 'system':
            system_prompt = (system_prompt or '') + (content or '')
        elif role == 'user':
            conversation_buffer.append(f"User: {content}")
            user_message = content
        elif role == 'assistant':
            conversation_buffer.append(f"Assistant: {content}")

    if user_message is None:
        raise HTTPException(status_code=400, detail='No user message supplied')

    full_message = '\n'.join([m for m in conversation_buffer]) + f"\nUser: {user_message}"
    req = ChatRequest(session_id=session_id, message=full_message, system_prompt=system_prompt)
    if stream:
        return await chat_stream(request_obj, req, authenticated)
    else:
        chat_response = await chat(request_obj, req, authenticated)
        return {
            'id': f"chatcmpl-{int(time.time()*1000)}",
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': model or 'ece-core',
            'choices': [{
                'index': 0,
                'message': {'role': 'assistant', 'content': chat_response.response},
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': chat_response.context_tokens,
                'completion_tokens': len(chat_response.response.split()),
                'total_tokens': chat_response.context_tokens + len(chat_response.response.split())
            }
        }
