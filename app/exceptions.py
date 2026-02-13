from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional

class ChatBotException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class MCPConnectionError(ChatBotException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE, details)

async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, ChatBotException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "details": exc.details}
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected error occurred.", "details": str(exc)}
    )
