from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service
from app.dependencies import get_mcp_client
from typing import Any, Dict

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/")
async def chat_v1(request: ChatRequest):
    """
    Version 1 of the chat endpoint.
    """
    try:
        response = await chat_service.generate_response(request.messages)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
