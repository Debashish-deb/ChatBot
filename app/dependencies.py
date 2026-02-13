from typing import AsyncGenerator
from app.mcp.client import MCPClient
from app.services.mcp_orchestrator import mcp_orchestrator

async def get_mcp_client() -> AsyncGenerator[MCPClient, None]:
    client = mcp_orchestrator.get_client()
    if not client:
        raise Exception("MCP Client not initialized")
    yield client
