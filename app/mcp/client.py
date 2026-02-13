import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.logging_config import logger

class MCPClient:
    def __init__(self, name: str, command: str, args: List[str] = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.session: Optional[ClientSession] = None
        self._ctx = None

    async def connect(self, exit_stack) -> ClientSession:
        """Connect to the MCP server and register with the provided exit stack."""
        logger.info(f"Connecting to MCP server: {self.name} via {self.command} {self.args}")
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=None
        )
        
        # We enter the context manager and add it to the stack
        read, write = await exit_stack.enter_async_context(stdio_client(server_params))
        session = await exit_stack.enter_async_context(ClientSession(read, write))
        
        await session.initialize()
        self.session = session
        return session

    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self.session:
            logger.warning(f"MCP Client {self.name} is not connected.")
            return []
        result = await self.session.list_tools()
        # Add server name to tools to help with routing later
        tools = []
        for tool in result.tools:
            tool_dict = tool.model_dump()
            tool_dict["server_name"] = self.name
            tools.append(tool_dict)
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self.session:
            raise Exception(f"MCP Client {self.name} not connected")
        result = await self.session.call_tool(name, arguments)
        return result.content
