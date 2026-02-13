# app/api/v1/chat_streaming.py
"""
Streaming Chat Endpoints
Server-Sent Events (SSE) for real-time token delivery
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, StreamChatRequest
from app.services.chat_service import chat_service
from app.middleware.auth import get_current_active_user
from app.models.database import User
from app.logging_config import logger
import json
import asyncio
from typing import AsyncGenerator

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream")
async def chat_stream(
    request: StreamChatRequest,
    user: User = Depends(get_current_active_user)
):
    """
    Streaming chat endpoint using Server-Sent Events (SSE)
    
    Returns tokens as they are generated in real-time.
    
    Event Types:
    - token: Individual token from LLM
    - tool_call: Tool is being called
    - tool_result: Tool execution result
    - done: Stream complete
    - error: An error occurred
    
    Example client code:
    ```javascript
    const eventSource = new EventSource('/api/v1/chat/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'token') {
            console.log(data.content);
        }
    };
    ```
    """
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Yield connection established
            yield f"data: {json.dumps({'type': 'connected', 'conversation_id': request.conversation_id})}\n\n"
            
            # Stream response from chat service
            async for chunk in chat_service.generate_response_stream(
                messages=request.messages,
                user_id=user.id,
                conversation_id=request.conversation_id,
                model=request.model,
                temperature=request.temperature
            ):
                # Send chunk as SSE
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            error_chunk = {
                "type": "error",
                "error": str(e),
                "code": "STREAM_ERROR"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@router.post("/")
async def chat_blocking(
    request: ChatRequest,
    user: User = Depends(get_current_active_user)
):
    """
    Blocking (non-streaming) chat endpoint
    
    Returns complete response after generation is finished.
    Use this for simple integrations or batch processing.
    """
    try:
        response = await chat_service.generate_response(
            messages=request.messages,
            user_id=user.id,
            conversation_id=request.conversation_id,
            model=request.model,
            temperature=request.temperature
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/regenerate")
async def regenerate_response(
    request: ChatRequest,
    user: User = Depends(get_current_active_user)
):
    """
    Regenerate the last assistant message in a conversation
    """
    try:
        response = await chat_service.regenerate_last_response(
            conversation_id=request.conversation_id,
            user_id=user.id,
            model=request.model,
            temperature=request.temperature
        )
        return response
    except Exception as e:
        logger.error(f"Regenerate error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/continue")
async def continue_conversation(
    request: ChatRequest,
    user: User = Depends(get_current_active_user)
):
    """
    Continue a conversation from where it left off
    Useful for resuming long-running conversations
    """
    try:
        response = await chat_service.continue_conversation(
            conversation_id=request.conversation_id,
            user_id=user.id,
            model=request.model
        )
        return response
    except Exception as e:
        logger.error(f"Continue error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WEBSOCKET ALTERNATIVE ====================

from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: str  # Pass as query parameter: /ws?token=xxx
):
    """
    WebSocket endpoint for bidirectional streaming
    
    Allows client to send messages and receive responses in real-time
    
    Example client code:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/chat/ws?token=xxx');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data);
    };
    ws.send(JSON.stringify({
        type: 'message',
        content: 'Hello!'
    }));
    ```
    """
    await websocket.accept()
    
    try:
        # Verify token
        from app.services.auth_service import auth_service
        from app.database import get_db_context
        
        async with get_db_context() as db:
            # For WebSocket, extract user from token
            payload = auth_service.verify_token(token)
            user_id = payload.get("sub")
            
            # Send welcome message
            await websocket.send_json({
                "type": "connected",
                "user_id": user_id
            })
            
            # Handle incoming messages
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                
                if data.get("type") == "message":
                    # Stream response
                    async for chunk in chat_service.generate_response_stream(
                        messages=[{"role": "user", "content": data.get("content")}],
                        user_id=user_id,
                        conversation_id=data.get("conversation_id")
                    ):
                        await websocket.send_json(chunk)
                        await asyncio.sleep(0.01)
                    
                    # Send done signal
                    await websocket.send_json({"type": "done"})
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
        await websocket.close()
