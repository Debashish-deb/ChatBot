import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.logging_config import logger
import time
from app.middleware.monitoring import mcp_tool_calls_total, mcp_tool_duration_seconds

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

    async def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Any:
        if not self.session:
            raise Exception(f"MCP Client {self.name} not connected")
        
        start_time = time.time()
        status = "success"
        try:
            # Add timeout support
            result = await asyncio.wait_for(
                self.session.call_tool(name, arguments),
                timeout=timeout
            )
            return result.content
        except asyncio.TimeoutError:
            status = "timeout"
            logger.error(f"MCP Tool call timeout: {self.name}.{name}")
            raise
        except Exception as e:
            status = "error"
            logger.error(f"MCP Tool call error: {self.name}.{name} - {str(e)}")
            raise
        finally:
            duration = time.time() - start_time
            # Record metrics
            mcp_tool_calls_total.labels(
                tool_name=name,
                server_name=self.name,
                status=status
            ).inc()
            mcp_tool_duration_seconds.labels(
                tool_name=name,
                server_name=self.name
            ).observe(duration)
