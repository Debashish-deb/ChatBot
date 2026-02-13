from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from app.mcp.client import MCPClient
from app.mcp.server_config import MCP_SERVERS
from app.logging_config import logger

class MCPOrchestrator:
    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._exit_stack = AsyncExitStack()

    async def initialize(self):
        logger.info("Initializing MCP Orchestrator and connecting to servers...")
        for name, config in MCP_SERVERS.items():
            client = MCPClient(
                name=name,
                command=config["command"],
                args=config.get("args", [])
            )
            try:
                await client.connect(self._exit_stack)
                self._clients[name] = client
                logger.info(f"Successfully connected to MCP server: {name}")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {name}: {str(e)}")

    async def shutdown(self):
        logger.info("Shutting down MCP Orchestrator and closing sessions...")
        await self._exit_stack.aclose()
        self._clients = {}

    async def list_all_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        for client in self._clients.values():
            tools = await client.list_tools()
            all_tools.extend(tools)
        return all_tools

    async def call_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        client = self._clients.get(server_name)
        if not client:
            raise Exception(f"MCP Server {server_name} not found or not connected")
        return await client.call_tool(tool_name, arguments)

mcp_orchestrator = MCPOrchestrator()
