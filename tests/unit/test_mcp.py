import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.mcp.client import MCPClient

@pytest.mark.asyncio
async def test_mcp_client_initialization():
    client = MCPClient(name="test", command="python", args=["--version"])
    assert client.name == "test"
    assert client.session is None

@pytest.mark.asyncio
async def test_mcp_client_list_tools_not_connected():
    client = MCPClient(name="test", command="python")
    tools = await client.list_tools()
    assert tools == []
