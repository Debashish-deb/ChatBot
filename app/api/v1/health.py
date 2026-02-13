from fastapi import APIRouter
from typing import Dict

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
